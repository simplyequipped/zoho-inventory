import pytest

from zoho_inventory.ratelimit import RateLimiter, DailyBudgetExceeded


class Clock:
    def __init__(self, t=1_760_000_000.0):
        self.t = t
        self.slept = []

    def now(self):
        return self.t

    def sleep(self, s):
        self.slept.append(s)
        self.t += s


def make(tmp_path, clock, **kw):
    kw.setdefault("rpm", 3)
    kw.setdefault("daily", 10)
    return RateLimiter(state_path=tmp_path / "rl.json", sleep=clock.sleep, now=clock.now, **kw)


def test_under_budget_does_not_sleep(tmp_path):
    clock = Clock()
    rl = make(tmp_path, clock)
    for _ in range(3):
        rl.acquire()
    assert clock.slept == []
    assert rl.status()["minute_used"] == 3


def test_fourth_request_waits_for_window(tmp_path):
    clock = Clock()
    rl = make(tmp_path, clock)
    rl.acquire(); clock.t += 1
    rl.acquire(); clock.t += 1
    rl.acquire(); clock.t += 1
    rl.acquire()  # window has 3 in the last 60s; must wait ~57s
    assert len(clock.slept) == 1
    assert 56.5 < clock.slept[0] < 58


def test_state_shared_across_instances(tmp_path):
    clock = Clock()
    a = make(tmp_path, clock)
    b = make(tmp_path, clock)
    a.acquire(); a.acquire(); a.acquire()
    b.acquire()  # separate "process" sees the same window
    assert clock.slept


def test_daily_budget_refuses_then_force(tmp_path):
    clock = Clock()
    rl = make(tmp_path, clock, rpm=1000, daily=2)
    rl.acquire(); rl.acquire()
    with pytest.raises(DailyBudgetExceeded):
        rl.acquire()
    rl.acquire(force=True)
    assert rl.status()["day_used"] == 3


def test_daily_counter_resets_next_utc_day(tmp_path):
    clock = Clock()
    rl = make(tmp_path, clock, rpm=1000, daily=2)
    rl.acquire(); rl.acquire()
    clock.t += 86400
    rl.acquire()  # new day, no exception
    assert rl.status()["day_used"] == 1


def test_warning_once_at_fraction(tmp_path, capsys):
    clock = Clock()
    rl = make(tmp_path, clock, rpm=1000, daily=10, warn_fraction=0.5)
    for _ in range(7):
        rl.acquire()
    err = capsys.readouterr().err
    assert err.count("warning") == 1
