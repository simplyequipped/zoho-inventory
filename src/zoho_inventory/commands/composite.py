"""Composite items (assemblies) and their bundles.

A composite item is a sellable SKU made from other items. Assembling it
("bundling" in Zoho's API) consumes the mapped parts and adds finished units
to stock. This is what ties a Shopify SKU to the parts that go into it.

```
zoho composite list [--sku X | --sku-contains X | --search X] [--status active]
zoho composite get <id|sku>                       full record incl. mapped_items
zoho composite parts <id|sku>                     just the parts table
zoho composite create --name N --sku S --rate R --part SKU:QTY [--part ...] [--json file]
zoho composite update <id|sku> [--rate R] [--purchase-rate R] [--part SKU:QTY ...] [--json file]
zoho composite activate|deactivate <id|sku>
zoho composite delete <id|sku> --yes

zoho composite assemble <id|sku> --qty N [--date YYYY-MM-DD] [--ref X] [--note X]
zoho composite bundles [<id|sku>]                 assembly history
zoho composite bundle <bundle_id>                 one assembly
zoho composite unassemble <bundle_id> --yes       delete an assembly (returns parts to stock)
```

--part takes SKU:QTY or ITEM_ID:QTY and may repeat. On update, passing any
--part replaces the whole parts list, so pass all of them.

assemble builds the line_items from the composite's mapped_items times --qty.
Zoho's docs do not show the bundle request body; the field names used here
(quantity_to_bundle, line_items[].item_id, quantity_consumed, is_completed)
are from third-party connectors and the Books API. If Zoho rejects the
request, set settings.bundle_qty_key to "quantity" and try again.

Reference: https://www.zoho.com/inventory/api/v1/compositeitems/
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import typer

from ..client import ZohoClient, ZohoError
from ..output import emit
from .items import resolve_item_id

app = typer.Typer(help=__doc__, no_args_is_help=True)

LIST_KEY = "composite_items"
LIST_COLUMNS = ["composite_item_id", "sku", "name", "status", "rate", "purchase_rate", "stock_on_hand", "available_stock", "unit"]


def resolve_composite_id(c: ZohoClient, ident: str, fuzzy: bool = False) -> str:
    if ident.isdigit() and len(ident) >= 12:
        return ident
    fuzzy = fuzzy or c.settings.sku_match == "fuzzy"
    params = {"sku_contains": ident} if fuzzy else {"sku": ident}
    rows = list(c.paginate("/compositeitems", LIST_KEY, **params))
    if not fuzzy:
        rows = [r for r in rows if r.get("sku") == ident]
    if len(rows) == 1:
        return str(rows[0]["composite_item_id"])
    if not rows:
        raise ZohoError(404, None, f"no composite item with SKU {ident!r}" + ("" if fuzzy else " (try --fuzzy)"))
    raise ZohoError(409, None, f"{len(rows)} composite items match {ident!r}: " + ", ".join(r.get("sku", "?") for r in rows[:10]))


def _parse_parts(c: ZohoClient, parts: list[str] | None) -> list[dict]:
    out = []
    for p in parts or []:
        if ":" not in p:
            raise typer.BadParameter(f"--part expects SKU:QTY, got {p!r}")
        ident, qty = p.rsplit(":", 1)
        out.append({"item_id": resolve_item_id(c, ident), "quantity": float(qty)})
    return out


def _merge_body(json_file: Path | None, **fields) -> dict:
    body = json.loads(json_file.read_text()) if json_file else {}
    for k, v in fields.items():
        if v is not None:
            body[k] = v
    return body


@app.command("list")
def list_(
    ctx: typer.Context,
    sku: str = typer.Option(None),
    sku_contains: str = typer.Option(None, "--sku-contains"),
    search: str = typer.Option(None, help="search_text"),
    status: str = typer.Option(None, help="active | inactive"),
    limit: int = typer.Option(None),
    columns: str = typer.Option(None),
):
    """List composite items."""
    c = ctx.obj.client()
    params = {}
    if sku: params["sku"] = sku
    if sku_contains: params["sku_contains"] = sku_contains
    if search: params["search_text"] = search
    if status: params["status"] = status
    rows = []
    for r in c.paginate("/compositeitems", LIST_KEY, **params):
        rows.append(r)
        if limit and len(rows) >= limit:
            break
    emit(rows, ctx.obj.fmt, columns.split(",") if columns else LIST_COLUMNS)


@app.command("get")
def get(ctx: typer.Context, ident: str = typer.Argument(..., metavar="ID|SKU"), fuzzy: bool = False):
    """Show one composite item including mapped_items."""
    c = ctx.obj.client()
    cid = resolve_composite_id(c, ident, fuzzy)
    emit(c.get(f"/compositeitems/{cid}").get("composite_item", {}), ctx.obj.fmt or "json")


@app.command("parts")
def parts(ctx: typer.Context, ident: str = typer.Argument(..., metavar="ID|SKU"), fuzzy: bool = False):
    """Show the parts list of a composite item."""
    c = ctx.obj.client()
    cid = resolve_composite_id(c, ident, fuzzy)
    item = c.get(f"/compositeitems/{cid}").get("composite_item", {})
    rows = item.get("mapped_items", [])
    emit(rows, ctx.obj.fmt, ["item_id", "sku", "name", "quantity", "purchase_rate", "stock_on_hand", "unit"])


@app.command("create")
def create(
    ctx: typer.Context,
    name: str = typer.Option(None),
    sku: str = typer.Option(None),
    rate: float = typer.Option(None, help="selling price (required by Zoho)"),
    purchase_rate: float = typer.Option(None, "--purchase-rate"),
    unit: str = typer.Option(None),
    description: str = typer.Option(None),
    part: list[str] = typer.Option(None, "--part", help="SKU:QTY, repeatable"),
    combo_type: str = typer.Option("assembly", "--combo-type", help="assembly | kit"),
    json_file: Path = typer.Option(None, "--json"),
):
    """Create a composite item from parts."""
    c = ctx.obj.client()
    body = _merge_body(
        json_file,
        name=name, sku=sku, rate=rate, purchase_rate=purchase_rate, unit=unit,
        description=description, combo_type=combo_type,
    )
    body.setdefault("item_type", "inventory")
    body.setdefault("product_type", "goods")
    if part:
        body["mapped_items"] = _parse_parts(c, part)
    for req in ("name", "sku", "rate", "mapped_items"):
        if req not in body:
            raise typer.BadParameter(f"{req} is required (flag or --json)")
    res = c.post("/compositeitems", body)
    emit(res.get("composite_item", res), ctx.obj.fmt or "json")


@app.command("update")
def update(
    ctx: typer.Context,
    ident: str = typer.Argument(..., metavar="ID|SKU"),
    name: str = typer.Option(None),
    sku: str = typer.Option(None),
    rate: float = typer.Option(None),
    purchase_rate: float = typer.Option(None, "--purchase-rate"),
    unit: str = typer.Option(None),
    description: str = typer.Option(None),
    part: list[str] = typer.Option(None, "--part", help="SKU:QTY, repeatable; replaces the full parts list"),
    json_file: Path = typer.Option(None, "--json"),
    fuzzy: bool = False,
):
    """Update a composite item."""
    c = ctx.obj.client()
    body = _merge_body(json_file, name=name, sku=sku, rate=rate, purchase_rate=purchase_rate, unit=unit, description=description)
    if part:
        body["mapped_items"] = _parse_parts(c, part)
    if not body:
        raise typer.BadParameter("nothing to update")
    cid = resolve_composite_id(c, ident, fuzzy)
    res = c.put(f"/compositeitems/{cid}", body)
    emit(res.get("composite_item", res), ctx.obj.fmt or "json")


@app.command("activate")
def activate(ctx: typer.Context, ident: str = typer.Argument(..., metavar="ID|SKU"), fuzzy: bool = False):
    c = ctx.obj.client()
    emit(c.post(f"/compositeitems/{resolve_composite_id(c, ident, fuzzy)}/active"), ctx.obj.fmt or "json")


@app.command("deactivate")
def deactivate(ctx: typer.Context, ident: str = typer.Argument(..., metavar="ID|SKU"), fuzzy: bool = False):
    c = ctx.obj.client()
    emit(c.post(f"/compositeitems/{resolve_composite_id(c, ident, fuzzy)}/inactive"), ctx.obj.fmt or "json")


@app.command("delete")
def delete(ctx: typer.Context, ident: str = typer.Argument(..., metavar="ID|SKU"), yes: bool = typer.Option(False, "--yes"), fuzzy: bool = False):
    """Delete a composite item."""
    if not yes:
        print("zoho-inventory: delete requires --yes", file=sys.stderr)
        raise typer.Exit(2)
    c = ctx.obj.client()
    emit(c.delete(f"/compositeitems/{resolve_composite_id(c, ident, fuzzy)}"), ctx.obj.fmt or "json")


# -- assemblies ------------------------------------------------------------
@app.command("assemble")
def assemble(
    ctx: typer.Context,
    ident: str = typer.Argument(..., metavar="ID|SKU"),
    qty: int = typer.Option(..., "--qty", help="units to assemble"),
    date: str = typer.Option(None, help="YYYY-MM-DD, default today"),
    ref: str = typer.Option(None, help="reference_number"),
    note: str = typer.Option(None, help="description"),
    fuzzy: bool = False,
):
    """Assemble N units: consumes parts, adds finished units to stock."""
    c = ctx.obj.client()
    cid = resolve_composite_id(c, ident, fuzzy)
    item = c.get(f"/compositeitems/{cid}").get("composite_item", {})
    qty_key = c.settings.extra.get("bundle_qty_key", "quantity_consumed")
    line_items = [
        {"item_id": m["item_id"], qty_key: float(m.get("quantity", 1)) * qty}
        for m in item.get("mapped_items", [])
    ]
    body = {
        "composite_item_id": cid,
        "quantity_to_bundle": qty,
        "date": date or dt.date.today().isoformat(),
        "is_completed": True,
        "line_items": line_items,
    }
    if ref: body["reference_number"] = ref
    if note: body["description"] = note
    res = c.post("/bundles", body)
    emit(res.get("bundle", res), ctx.obj.fmt or "json")


@app.command("bundles")
def bundles(ctx: typer.Context, ident: str = typer.Argument(None, metavar="ID|SKU"), limit: int = typer.Option(None), fuzzy: bool = False):
    """Assembly history, optionally for one composite item."""
    c = ctx.obj.client()
    params = {}
    if ident:
        params["composite_item_id"] = resolve_composite_id(c, ident, fuzzy)
    rows = []
    for r in c.paginate("/bundles", "bundles", **params):
        rows.append(r)
        if limit and len(rows) >= limit:
            break
    emit(rows, ctx.obj.fmt, ["bundle_id", "date", "composite_item_name", "composite_item_sku", "quantity_to_bundle", "reference_number", "is_completed"])


@app.command("bundle")
def bundle(ctx: typer.Context, bundle_id: str):
    """Show one assembly."""
    c = ctx.obj.client()
    emit(c.get(f"/bundles/{bundle_id}").get("bundle", {}), ctx.obj.fmt or "json")


@app.command("unassemble")
def unassemble(ctx: typer.Context, bundle_id: str, yes: bool = typer.Option(False, "--yes")):
    """Delete an assembly. Zoho reverses the stock movement."""
    if not yes:
        print("zoho-inventory: unassemble requires --yes", file=sys.stderr)
        raise typer.Exit(2)
    c = ctx.obj.client()
    emit(c.delete(f"/bundles/{bundle_id}"), ctx.obj.fmt or "json")
