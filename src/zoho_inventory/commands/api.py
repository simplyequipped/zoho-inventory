"""Call any Zoho Inventory endpoint.

This is the escape hatch that makes every endpoint in the API reachable even
before it has a typed command. organization_id and auth are added for you.

```
zoho api GET /compositeitems
zoho api GET /items --param sku=RNODE-T3S3 --param status=active
zoho api GET /items --all                       # follow pagination, list key auto-detected
zoho api POST /items --json item.json
zoho api POST /items --data '{"name": "Battery 2000mAh", "sku": "BAT-2000"}'
zoho api PUT /items/123456000000012345 --data '{"purchase_rate": 5.75}'
zoho api DELETE /items/123456000000012345 --yes
```

Paths are relative to /inventory/v1. Write methods honor --dry-run and print
the request before sending when --verbose is set. DELETE requires --yes.

Reference: https://www.zoho.com/inventory/api/v1/
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer

from ..output import emit


def api(
    ctx: typer.Context,
    method: str = typer.Argument(..., help="GET | POST | PUT | DELETE"),
    path: str = typer.Argument(..., help="e.g. /items or /compositeitems/{id}/bundles"),
    param: list[str] = typer.Option(None, "--param", "-p", help="query parameter k=v (repeatable)"),
    json_file: Path = typer.Option(None, "--json", help="file containing the JSON request body"),
    data: str = typer.Option(None, "--data", "-d", help="inline JSON request body"),
    all_pages: bool = typer.Option(False, "--all", help="GET only: follow pagination and return every row"),
    list_key: str = typer.Option(None, "--list-key", help="with --all: response key holding the rows (auto-detected)"),
    yes: bool = typer.Option(False, "--yes", help="required for DELETE"),
):
    method = method.upper()
    if method not in ("GET", "POST", "PUT", "DELETE"):
        raise typer.BadParameter("method must be GET, POST, PUT or DELETE")
    if method == "DELETE" and not yes:
        print("zoho-inventory: DELETE requires --yes", file=sys.stderr)
        raise typer.Exit(2)

    params = {}
    for kv in param or []:
        if "=" not in kv:
            raise typer.BadParameter(f"--param expects k=v, got {kv!r}")
        k, v = kv.split("=", 1)
        params[k] = v

    body = None
    if json_file and data:
        raise typer.BadParameter("use --json or --data, not both")
    if json_file:
        body = json.loads(json_file.read_text())
    elif data:
        body = json.loads(data)

    c = ctx.obj.client()
    if ctx.obj.verbose and method != "GET":
        print(f"{method} {path} params={params} body={json.dumps(body)}", file=sys.stderr)

    if method == "GET" and all_pages:
        key = list_key or _guess_list_key(path)
        rows = list(c.paginate(path, key, **params))
        emit(rows, ctx.obj.fmt)
        return

    res = c.request(method, path, params=params, json_body=body)
    emit(res, ctx.obj.fmt or "json")


def _guess_list_key(path: str) -> str:
    # /items -> items ; /compositeitems -> composite_items ; /salesorders -> salesorders
    seg = path.strip("/").split("/")[0].split("?")[0]
    return {"compositeitems": "composite_items", "itemgroups": "itemgroups"}.get(seg, seg)
