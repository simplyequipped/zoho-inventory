"""HTTP client for the Zoho Inventory API.

All requests go through ZohoClient.request, which takes the rate limiter,
adds organization_id and the bearer token, maps the {"code", "message"}
envelope to ZohoError, refreshes once on 401, and backs off on 429.

Pagination: list endpoints take page/per_page and return page_context with
has_more_page. `paginate()` walks pages at the max per_page (200) and yields
items from the named list key. If Zoho omits page_context, it stops when a
page comes back shorter than per_page.

Dry-run: when `dry_run=True`, write methods print the request and return a
stub instead of sending. GET is always sent.
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass
from typing import Any, Iterator

import httpx

from . import auth
from .config import API_PREFIX, Credentials, Settings
from .ratelimit import RateLimiter

WRITE_METHODS = {"POST", "PUT", "DELETE", "PATCH"}
RETRY_429 = (2, 5, 15)  # seconds


@dataclass
class ZohoError(Exception):
    status: int
    code: int | None
    message: str
    body: Any = None

    def __str__(self) -> str:
        c = f" (code {self.code})" if self.code is not None else ""
        return f"HTTP {self.status}{c}: {self.message}"


class ZohoClient:
    def __init__(
        self,
        creds: Credentials | None = None,
        settings: Settings | None = None,
        limiter: RateLimiter | None = None,
        http: httpx.Client | None = None,
        dry_run: bool = False,
        force: bool = False,
    ):
        self.creds = creds or Credentials.load()
        self.settings = settings or Settings.load()
        self.limiter = limiter or RateLimiter(
            rpm=self.settings.requests_per_minute,
            daily=self.settings.requests_per_day,
            warn_fraction=self.settings.daily_warn_fraction,
        )
        self.http = http or httpx.Client(timeout=60)
        self.dry_run = dry_run
        self.force = force

    # -- low level -----------------------------------------------------------
    def _url(self, path: str) -> str:
        if path.startswith("http"):
            return path
        if not path.startswith("/"):
            path = "/" + path
        return self.creds.api_domain.rstrip("/") + API_PREFIX + path

    def request(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        json_body: dict | None = None,
        data: dict | None = None,
    ) -> dict:
        method = method.upper()
        params = dict(params or {})
        params.setdefault("organization_id", self.creds.organization_id)

        if self.dry_run and method in WRITE_METHODS:
            print(
                f"[dry-run] {method} {self._url(path)}\n"
                f"  params: {json.dumps(params)}\n"
                f"  body:   {json.dumps(json_body or data, indent=2)}",
                file=sys.stderr,
            )
            return {"code": 0, "message": "dry-run", "dry_run": True}

        refreshed = False
        for attempt in range(len(RETRY_429) + 1):
            self.limiter.acquire(force=self.force)
            token = auth.ensure_access_token(self.creds, self.http)
            headers = {"Authorization": f"Zoho-oauthtoken {token}"}
            kwargs: dict[str, Any] = {"params": params, "headers": headers}
            if json_body is not None:
                # Zoho accepts JSON bodies on most endpoints; some older ones
                # want JSONString form data. We send JSON by default and the
                # `data=` path exists for the exceptions.
                kwargs["json"] = json_body
            elif data is not None:
                kwargs["data"] = data
            r = self.http.request(method, self._url(path), **kwargs)

            if r.status_code == 401 and not refreshed:
                refreshed = True
                auth.ensure_access_token(self.creds, self.http, force=True)
                continue
            if r.status_code == 429 and attempt < len(RETRY_429):
                wait = RETRY_429[attempt]
                print(f"zoho-inventory: 429 from Zoho, backing off {wait}s", file=sys.stderr)
                time.sleep(wait)
                continue
            return self._parse(r)
        raise ZohoError(429, None, "rate limited after retries")

    def _parse(self, r: httpx.Response) -> dict:
        try:
            body = r.json()
        except ValueError:
            if r.is_success:
                return {"code": 0, "message": "", "raw": r.text}
            raise ZohoError(r.status_code, None, r.text[:500])
        code = body.get("code") if isinstance(body, dict) else None
        if not r.is_success or (code not in (0, None)):
            msg = body.get("message", "") if isinstance(body, dict) else str(body)
            raise ZohoError(r.status_code, code, msg, body)
        return body

    # -- convenience ---------------------------------------------------------
    def get(self, path: str, **params) -> dict:
        return self.request("GET", path, params=params)

    def post(self, path: str, body: dict | None = None, **params) -> dict:
        return self.request("POST", path, params=params, json_body=body)

    def put(self, path: str, body: dict | None = None, **params) -> dict:
        return self.request("PUT", path, params=params, json_body=body)

    def delete(self, path: str, **params) -> dict:
        return self.request("DELETE", path, params=params)

    def paginate(self, path: str, list_key: str, per_page: int | None = None, **params) -> Iterator[dict]:
        per_page = per_page or self.settings.default_per_page
        page = 1
        while True:
            body = self.get(path, page=page, per_page=per_page, **params)
            rows = body.get(list_key, []) or []
            yield from rows
            ctx = body.get("page_context") or {}
            if "has_more_page" in ctx:
                if not ctx["has_more_page"]:
                    return
            elif len(rows) < per_page:
                return
            page += 1
