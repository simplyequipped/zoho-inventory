"""Organizations visible to this client."""

from __future__ import annotations

import typer

from ..output import emit

app = typer.Typer(help=__doc__, no_args_is_help=True)


@app.command("list")
def list_(ctx: typer.Context):
    """List organizations and which one is configured."""
    c = ctx.obj.client()
    rows = c.get("/organizations").get("organizations", [])
    for r in rows:
        r["configured"] = str(r.get("organization_id")) == c.creds.organization_id
    emit(rows, ctx.obj.fmt, ["organization_id", "name", "currency_code", "time_zone", "plan_name", "configured"])


@app.command("get")
def get(ctx: typer.Context, organization_id: str = typer.Argument(None)):
    """Show one organization (default: the configured one)."""
    c = ctx.obj.client()
    oid = organization_id or c.creds.organization_id
    emit(c.get(f"/organizations/{oid}").get("organization", {}), ctx.obj.fmt)
