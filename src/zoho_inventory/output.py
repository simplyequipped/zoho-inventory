"""Output rendering.

Default format is `table` on a TTY and `json` otherwise, so a human at a
terminal gets something readable and a pipe or script gets structured
data without having to pass --format every time.
"""

from __future__ import annotations

import csv
import json
import sys
from typing import Iterable

FORMATS = ("table", "json", "csv")


def default_format() -> str:
    return "table" if sys.stdout.isatty() else "json"


def emit(rows: Iterable[dict] | dict, fmt: str | None = None, columns: list[str] | None = None) -> None:
    fmt = fmt or default_format()
    single = isinstance(rows, dict)
    rows = [rows] if single else list(rows)
    if fmt == "json":
        print(json.dumps(rows[0] if single else rows, indent=2, default=str))
        return
    if not rows:
        print("(no results)", file=sys.stderr)
        return
    cols = columns or _columns(rows)
    if fmt == "csv":
        w = csv.DictWriter(sys.stdout, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({c: _cell(r.get(c)) for c in cols})
        return
    # table
    data = [[_cell(r.get(c)) for c in cols] for r in rows]
    widths = [max(len(c), *(len(d[i]) for d in data)) for i, c in enumerate(cols)]
    print("  ".join(c.ljust(w) for c, w in zip(cols, widths)))
    print("  ".join("-" * w for w in widths))
    for d in data:
        print("  ".join(v.ljust(w) for v, w in zip(d, widths)))


def _columns(rows: list[dict]) -> list[str]:
    seen: dict[str, None] = {}
    for r in rows:
        for k, v in r.items():
            if isinstance(v, (dict, list)):
                continue
            seen.setdefault(k, None)
    return list(seen)


def _cell(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float):
        return f"{v:.4f}".rstrip("0").rstrip(".")
    if isinstance(v, (dict, list)):
        return json.dumps(v)
    return str(v)
