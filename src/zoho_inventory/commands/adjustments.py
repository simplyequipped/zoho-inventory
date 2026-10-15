"""Inventory adjustments: correct stock on hand outside of sales and purchases.

```
zoho adjustments list [--limit N]
zoho adjustments get <adjustment_id>
zoho adjustments create --reason "text" --line SKU:+N [--line SKU:-N ...] [--date D] [--ref X] [--note X]
zoho adjustments delete <adjustment_id> --yes
```

--line is SKU:DELTA or ITEM_ID:DELTA. DELTA is the change, signed: +3 adds
three, -2 removes two. Zoho calls this quantity_adjusted. Quantity
adjustments only; value adjustments go through `zoho api`.

Reference: https://www.zoho.com/inventory/api/v1/inventoryadjustments/
"""

from __future__ import annotations

import datetime as dt
import sys

import typer

from ..output import emit
from .items import resolve_item_id

app = typer.Typer(help=__doc__, no_args_is_help=True)

LIST_KEY = "inventory_adjustments"
LIST_COLUMNS = ["inventory_adjustment_id", "date", "reason", "adjustment_type", "reference_number", "description", "total"]


@app.command("list")
def list_(ctx: typer.Context, limit: int = typer.Option(None)):
    """List adjustments, newest first as Zoho returns them."""
    c = ctx.obj.client()
    rows = []
    for r in c.paginate("/inventoryadjustments", LIST_KEY):
        rows.append(r)
        if limit and len(rows) >= limit:
            break
    emit(rows, ctx.obj.fmt, LIST_COLUMNS)


@app.command("get")
def get(ctx: typer.Context, adjustment_id: str):
    c = ctx.obj.client()
    emit(c.get(f"/inventoryadjustments/{adjustment_id}").get("inventory_adjustment", {}), ctx.obj.fmt or "json")


@app.command("create")
def create(
    ctx: typer.Context,
    reason: str = typer.Option(..., help="required by Zoho, free text"),
    line: list[str] = typer.Option(..., "--line", help="SKU:DELTA, repeatable"),
    date: str = typer.Option(None, help="YYYY-MM-DD, default today"),
    ref: str = typer.Option(None, help="reference_number"),
    note: str = typer.Option(None, help="description"),
):
    """Create a quantity adjustment."""
    c = ctx.obj.client()
    line_items = []
    for l in line:
        if ":" not in l:
            raise typer.BadParameter(f"--line expects SKU:DELTA, got {l!r}")
        ident, delta = l.rsplit(":", 1)
        line_items.append({"item_id": resolve_item_id(c, ident), "quantity_adjusted": float(delta)})
    body = {
        "date": date or dt.date.today().isoformat(),
        "reason": reason,
        "adjustment_type": "quantity",
        "line_items": line_items,
    }
    if ref: body["reference_number"] = ref
    if note: body["description"] = note
    res = c.post("/inventoryadjustments", body)
    emit(res.get("inventory_adjustment", res), ctx.obj.fmt or "json")


@app.command("delete")
def delete(ctx: typer.Context, adjustment_id: str, yes: bool = typer.Option(False, "--yes")):
    if not yes:
        print("zoho-inventory: delete requires --yes", file=sys.stderr)
        raise typer.Exit(2)
    c = ctx.obj.client()
    emit(c.delete(f"/inventoryadjustments/{adjustment_id}"), ctx.obj.fmt or "json")
