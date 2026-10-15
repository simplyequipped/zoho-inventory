"""Item catalog.

```
zoho items list [--sku X] [--name X] [--search X] [--status active|inactive] [--type inventory|service]
zoho items get <id|sku>
zoho items create --name N --sku S [--purchase-rate R] [--rate R] [--unit pcs] [--json file]
zoho items update <id|sku> [--purchase-rate R] [--rate R] [--name N] [--json file]
zoho items activate <id|sku> | deactivate <id|sku>
zoho items delete <id|sku> --yes
```

Identifiers: anything that takes an <id|sku> accepts a Zoho item_id (long
number) or a SKU. SKU matching is exact unless --fuzzy or settings.sku_match
is "fuzzy", in which case Zoho's sku_contains filter is used and exactly one
hit is required.

Fields (Zoho names, passed straight through in --json):

```
  name*             display name
  sku               your SKU; what Shopify sync matches on
  rate              selling price
  purchase_rate     cost (unit cost in the pricing sheet)
  unit              e.g. "pcs"
  item_type         inventory | sales | purchases | sales_and_purchases
  product_type      goods | service
  description, purchase_description
  reorder_level, vendor_id, brand, manufacturer
  initial_stock, initial_stock_rate   (create only)
```

Reference: https://www.zoho.com/inventory/api/v1/items/
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer

from ..client import ZohoClient, ZohoError
from ..output import emit

app = typer.Typer(help=__doc__, no_args_is_help=True)

LIST_COLUMNS = ["item_id", "sku", "name", "status", "purchase_rate", "rate", "stock_on_hand", "available_stock", "unit", "item_type"]


# -- helpers ---------------------------------------------------------------
def resolve_item_id(c: ZohoClient, ident: str, fuzzy: bool = False) -> str:
    """Return a Zoho item_id for an id-or-SKU."""
    if ident.isdigit() and len(ident) >= 12:
        return ident
    fuzzy = fuzzy or c.settings.sku_match == "fuzzy"
    params = {"sku_contains": ident} if fuzzy else {"sku": ident}
    rows = list(c.paginate("/items", "items", **params))
    if not fuzzy:
        rows = [r for r in rows if r.get("sku") == ident]
    if len(rows) == 1:
        return str(rows[0]["item_id"])
    if not rows:
        raise ZohoError(404, None, f"no item with SKU {ident!r}" + ("" if fuzzy else " (try --fuzzy)"))
    skus = ", ".join(r.get("sku", "?") for r in rows[:10])
    raise ZohoError(409, None, f"{len(rows)} items match {ident!r}: {skus}")


def _merge_body(json_file: Path | None, **fields) -> dict:
    body = json.loads(json_file.read_text()) if json_file else {}
    for k, v in fields.items():
        if v is not None:
            body[k] = v
    return body


# -- commands --------------------------------------------------------------
@app.command("list")
def list_(
    ctx: typer.Context,
    sku: str = typer.Option(None, help="exact SKU"),
    sku_contains: str = typer.Option(None, "--sku-contains"),
    name: str = typer.Option(None, help="exact name"),
    name_contains: str = typer.Option(None, "--name-contains"),
    search: str = typer.Option(None, help="Zoho search_text across fields"),
    status: str = typer.Option(None, help="active | inactive"),
    item_type: str = typer.Option(None, "--type", help="inventory | service (filter_by)"),
    limit: int = typer.Option(None, help="stop after N rows"),
    columns: str = typer.Option(None, help="comma-separated columns for table/csv"),
):
    """List items (follows pagination)."""
    c = ctx.obj.client()
    params = {}
    if sku: params["sku"] = sku
    if sku_contains: params["sku_contains"] = sku_contains
    if name: params["name"] = name
    if name_contains: params["name_contains"] = name_contains
    if search: params["search_text"] = search
    if status: params["status"] = status
    if item_type: params["filter_by"] = f"ItemType.{item_type.capitalize()}"
    rows = []
    for r in c.paginate("/items", "items", **params):
        rows.append(r)
        if limit and len(rows) >= limit:
            break
    emit(rows, ctx.obj.fmt, columns.split(",") if columns else LIST_COLUMNS)


@app.command("get")
def get(ctx: typer.Context, ident: str = typer.Argument(..., metavar="ID|SKU"), fuzzy: bool = False):
    """Show one item in full."""
    c = ctx.obj.client()
    iid = resolve_item_id(c, ident, fuzzy)
    emit(c.get(f"/items/{iid}").get("item", {}), ctx.obj.fmt or "json")


@app.command("create")
def create(
    ctx: typer.Context,
    name: str = typer.Option(None, help="required unless in --json"),
    sku: str = typer.Option(None),
    purchase_rate: float = typer.Option(None, "--purchase-rate", help="cost"),
    rate: float = typer.Option(None, help="selling price"),
    unit: str = typer.Option(None),
    item_type: str = typer.Option("inventory", "--item-type", help="inventory|sales|purchases|sales_and_purchases"),
    product_type: str = typer.Option("goods", "--product-type"),
    description: str = typer.Option(None),
    purchase_description: str = typer.Option(None, "--purchase-description"),
    reorder_level: float = typer.Option(None, "--reorder-level"),
    initial_stock: float = typer.Option(None, "--initial-stock"),
    initial_stock_rate: float = typer.Option(None, "--initial-stock-rate"),
    json_file: Path = typer.Option(None, "--json", help="full/partial body; flags override"),
):
    """Create an item. Prints the created item."""
    body = _merge_body(
        json_file,
        name=name, sku=sku, purchase_rate=purchase_rate, rate=rate, unit=unit,
        item_type=item_type, product_type=product_type, description=description,
        purchase_description=purchase_description, reorder_level=reorder_level,
        initial_stock=initial_stock, initial_stock_rate=initial_stock_rate,
    )
    if "name" not in body:
        raise typer.BadParameter("--name is required")
    c = ctx.obj.client()
    res = c.post("/items", body)
    emit(res.get("item", res), ctx.obj.fmt or "json")


@app.command("update")
def update(
    ctx: typer.Context,
    ident: str = typer.Argument(..., metavar="ID|SKU"),
    name: str = typer.Option(None),
    sku: str = typer.Option(None, help="new SKU"),
    purchase_rate: float = typer.Option(None, "--purchase-rate", help="cost"),
    rate: float = typer.Option(None, help="selling price"),
    unit: str = typer.Option(None),
    description: str = typer.Option(None),
    purchase_description: str = typer.Option(None, "--purchase-description"),
    reorder_level: float = typer.Option(None, "--reorder-level"),
    json_file: Path = typer.Option(None, "--json"),
    fuzzy: bool = False,
):
    """Update fields on an item. Only the fields you pass are sent."""
    body = _merge_body(
        json_file,
        name=name, sku=sku, purchase_rate=purchase_rate, rate=rate, unit=unit,
        description=description, purchase_description=purchase_description,
        reorder_level=reorder_level,
    )
    if not body:
        raise typer.BadParameter("nothing to update")
    c = ctx.obj.client()
    iid = resolve_item_id(c, ident, fuzzy)
    res = c.put(f"/items/{iid}", body)
    emit(res.get("item", res), ctx.obj.fmt or "json")


@app.command("activate")
def activate(ctx: typer.Context, ident: str = typer.Argument(..., metavar="ID|SKU"), fuzzy: bool = False):
    c = ctx.obj.client()
    iid = resolve_item_id(c, ident, fuzzy)
    emit(c.post(f"/items/{iid}/active"), ctx.obj.fmt or "json")


@app.command("deactivate")
def deactivate(ctx: typer.Context, ident: str = typer.Argument(..., metavar="ID|SKU"), fuzzy: bool = False):
    c = ctx.obj.client()
    iid = resolve_item_id(c, ident, fuzzy)
    emit(c.post(f"/items/{iid}/inactive"), ctx.obj.fmt or "json")


@app.command("delete")
def delete(
    ctx: typer.Context,
    ident: str = typer.Argument(..., metavar="ID|SKU"),
    yes: bool = typer.Option(False, "--yes", help="required"),
    fuzzy: bool = False,
):
    """Delete an item. Zoho refuses if it has transactions; use deactivate instead."""
    if not yes:
        print("zoho-inventory: delete requires --yes", file=sys.stderr)
        raise typer.Exit(2)
    c = ctx.obj.client()
    iid = resolve_item_id(c, ident, fuzzy)
    emit(c.delete(f"/items/{iid}"), ctx.obj.fmt or "json")
