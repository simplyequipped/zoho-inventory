"""Cross-process rate limiter.

Each CLI invocation is its own process, so the limiter keeps its state in a
file under the cache dir and takes an fcntl lock around every decision:

    state.json
    {
      "window": [t1, t2, ...],        # epoch seconds of requests in the last 60 s
      "day": "2026-10-15",            # UTC date the daily counter belongs to
      "day_count": 123
    }

Policy
------
* Sliding window: at most `rpm` requests in any 60 s. If full, sleep until the
  oldest entry ages out. Default 60/min against Zoho's 100/min per org, leaving
  headroom for the Shopify sync and anything else in the org.
* Daily budget: counts requests per UTC day. Warn (to stderr) once past
  `warn_fraction`; refuse past the cap unless `force=True`.
* Concurrency: the lock is held for the whole acquire() so overlapping CLI
  processes serialize. Requests within a process are sequential anyway.

Zoho limits (docs, Inventory API introduction): 100 requests/minute per
organization; daily cap by plan (Free 1000, Standard 2000, Professional 5000,
Premium/Enterprise 10000); concurrent 5 (Free) / 10 (paid).
"""

from __future__ import annotations

import fcntl
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from .config import cache_dir

WINDOW = 60.0


class DailyBudgetExceeded(Exception):
    pass


class RateLimiter:
    def __init__(
        self,
        rpm: int = 60,
        daily: int = 1000,
        warn_fraction: float = 0.8,
        state_path: Path | None = None,
        sleep=time.sleep,
        now=time.time,
    ):
        self.rpm = rpm
        self.daily = daily
        self.warn_fraction = warn_fraction
        self.state_path = state_path or (cache_dir() / "ratelimit.json")
        self._sleep = sleep
        self._now = now
        self._warned = False

    # -- state ---------------------------------------------------------------
    def _load(self, fh) -> dict:
        fh.seek(0)
        raw = fh.read()
        if not raw:
            return {"window": [], "day": "", "day_count": 0}
        try:
            return json.loads(raw)
        except ValueError:
            return {"window": [], "day": "", "day_count": 0}

    def _store(self, fh, state: dict) -> None:
        fh.seek(0)
        fh.truncate()
        fh.write(json.dumps(state))
        fh.flush()

    def _today(self) -> str:
        return datetime.fromtimestamp(self._now(), tz=timezone.utc).strftime("%Y-%m-%d")

    # -- public --------------------------------------------------------------
    def acquire(self, force: bool = False) -> None:
        """Block until a request may be sent, then record it."""
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_path, "a+") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX)
            try:
                state = self._load(fh)
                today = self._today()
                if state.get("day") != today:
                    state["day"] = today
                    state["day_count"] = 0

                if state["day_count"] >= self.daily and not force:
                    raise DailyBudgetExceeded(
                        f"Daily budget of {self.daily} requests reached (UTC day {today}). "
                        "Use --force to override or raise ZOHO_INVENTORY_DAILY."
                    )
                if (
                    not self._warned
                    and state["day_count"] >= int(self.daily * self.warn_fraction)
                ):
                    self._warned = True
                    print(
                        f"zoho-inventory: warning: {state['day_count']}/{self.daily} daily requests used",
                        file=sys.stderr,
                    )

                now = self._now()
                window = [t for t in state.get("window", []) if now - t < WINDOW]
                if len(window) >= self.rpm:
                    wait = WINDOW - (now - window[0]) + 0.05
                    self._sleep(max(wait, 0))
                    now = self._now()
                    window = [t for t in window if now - t < WINDOW]

                window.append(now)
                state["window"] = window
                state["day_count"] += 1
                self._store(fh, state)
            finally:
                fcntl.flock(fh, fcntl.LOCK_UN)

    def status(self) -> dict:
        if not self.state_path.exists():
            return {"minute_used": 0, "minute_budget": self.rpm, "day_used": 0, "day_budget": self.daily}
        with open(self.state_path, "a+") as fh:
            fcntl.flock(fh, fcntl.LOCK_SH)
            try:
                state = self._load(fh)
            finally:
                fcntl.flock(fh, fcntl.LOCK_UN)
        now = self._now()
        used = len([t for t in state.get("window", []) if now - t < WINDOW])
        day_used = state.get("day_count", 0) if state.get("day") == self._today() else 0
        return {
            "minute_used": used,
            "minute_budget": self.rpm,
            "day_used": day_used,
            "day_budget": self.daily,
        }
