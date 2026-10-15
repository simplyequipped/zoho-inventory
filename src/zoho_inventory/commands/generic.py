"""Command group factory for modules described in modules.py.

Every generic group gets the same shape:

```
zoho <module> list [--search X] [--status X] [--param k=v ...] [--limit N] [--columns a,b]
zoho <module> get <id>
zoho <module> create --json file | --data '{...}' [--param k=v]
zoho <module> update <id> --json file | --data '{...}'
zoho <module> delete <id> --yes
zoho <module> do <id> <action>          POST /{path}/{id}/{action}, e.g. confirmed, void
zoho <module> fields                     notable request fields and the doc link
```

Request bodies are Zoho's own JSON; see `zoho docs <module>`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer

from ..modules import Module
from ..output import emit


def _body(json_file: Path | None, data: str | None) -> dict:
    if json_file and data:
        raise typer.BadParameter("use --json or --data, not both")
    if json_file:
        return json.loads(json_file.read_text())
    if data:
        return json.loads(data)
    raise typer.BadParameter("--json or --data is required")


def _params(param: list[str] | None) -> dict:
    out = {}
    for kv in param or []:
        if "=" not in kv:
            raise typer.BadParameter(f"--param expects k=v, got {kv!r}")
        k, v = kv.split("=", 1)
        out[k] = v
    return out


def build(m: Module) -> typer.Typer:
    app = typer.Typer(help=f"{m.summary}\n\nReference: {m.doc}", no_args_is_help=True)

    @app.command("list")
    def list_(
        ctx: typer.Context,
        search: str = typer.Option(None, help="search_text"),
        status: str = typer.Option(None),
        param: list[str] = typer.Option(None, "--param", "-p", help="extra filter k=v; see `fields`"),
        limit: int = typer.Option(None),
        columns: str = typer.Option(None, help="comma-separated"),
    ):
        c = ctx.obj.client()
        params = _params(param)
        if search: params["search_text"] = search
        if status: params["status"] = status
        rows = []
        for r in c.paginate("/" + m.path, m.list_key, **params):
            rows.append(r)
            if limit and len(rows) >= limit:
                break
        emit(rows, ctx.obj.fmt, columns.split(",") if columns else m.columns)

    @app.command("get")
    def get(ctx: typer.Context, id: str = typer.Argument(..., metavar="ID")):
        c = ctx.obj.client()
        emit(c.get(f"/{m.path}/{id}").get(m.single_key, {}), ctx.obj.fmt or "json")

    @app.command("create")
    def create(
        ctx: typer.Context,
        json_file: Path = typer.Option(None, "--json"),
        data: str = typer.Option(None, "--data", "-d"),
        param: list[str] = typer.Option(None, "--param", "-p", help="query params some creates need, e.g. purchaseorder_id=..."),
    ):
        c = ctx.obj.client()
        res = c.request("POST", "/" + m.path, params=_params(param), json_body=_body(json_file, data))
        emit(res.get(m.single_key, res), ctx.obj.fmt or "json")

    @app.command("update")
    def update(
        ctx: typer.Context,
        id: str = typer.Argument(..., metavar="ID"),
        json_file: Path = typer.Option(None, "--json"),
        data: str = typer.Option(None, "--data", "-d"),
    ):
        c = ctx.obj.client()
        res = c.put(f"/{m.path}/{id}", _body(json_file, data))
        emit(res.get(m.single_key, res), ctx.obj.fmt or "json")

    @app.command("delete")
    def delete(ctx: typer.Context, id: str = typer.Argument(..., metavar="ID"), yes: bool = typer.Option(False, "--yes")):
        if not yes:
            print("zoho-inventory: delete requires --yes", file=sys.stderr)
            raise typer.Exit(2)
        c = ctx.obj.client()
        emit(c.delete(f"/{m.path}/{id}"), ctx.obj.fmt or "json")

    @app.command("do")
    def do(ctx: typer.Context, id: str = typer.Argument(..., metavar="ID"), action: str = typer.Argument(..., help="|".join(m.actions) or "see docs")):
        """Status change: POST /{path}/{id}/{action}."""
        c = ctx.obj.client()
        emit(c.post(f"/{m.path}/{id}/{action}"), ctx.obj.fmt or "json")

    @app.command("fields")
    def fields(ctx: typer.Context):
        """Notable request fields, list filters, actions, and the doc link."""
        typer.echo(f"{m.name}: {m.summary}")
        typer.echo(f"path: /{m.path}   list key: {m.list_key}   object key: {m.single_key}   id: {m.id_field}")
        if m.fields:
            typer.echo("fields (* required):")
            for f in m.fields:
                typer.echo(f"  {f}")
        if m.search_params:
            typer.echo("list filters: " + ", ".join(m.search_params))
        if m.actions:
            typer.echo("actions (zoho {} do ID ACTION): ".format(m.name) + ", ".join(m.actions))
        typer.echo(f"reference: {m.doc}")

    return app
