"""`zoho` command root.

Global options apply to every subcommand and are read from the typer context:

    --format table|json|csv   output format (default: table on a TTY, else json)
    --dry-run                 print write requests instead of sending them
    --force                   ignore the daily request budget
    --verbose                 log each HTTP request to stderr

Exit codes: 0 ok, 1 Zoho/API error, 2 usage or config error, 3 budget exceeded
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

import typer

from . import __version__
from .client import ZohoClient, ZohoError
from .config import ConfigError
from .output import FORMATS
from .ratelimit import DailyBudgetExceeded

app = typer.Typer(
    name="zoho",
    help="Zoho Inventory from the command line. Run `zoho <group> --help` for each API module.",
    no_args_is_help=True,
    rich_markup_mode="markdown",
)


@dataclass
class Ctx:
    fmt: str | None
    dry_run: bool
    force: bool
    verbose: bool
    _client: ZohoClient | None = None

    def client(self) -> ZohoClient:
        if self._client is None:
            self._client = ZohoClient(dry_run=self.dry_run, force=self.force)
        return self._client


def _version(v: bool):
    if v:
        print(f"zoho-inventory {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    fmt: str = typer.Option(None, "--format", "-f", help="Output: " + "|".join(FORMATS)),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print write requests instead of sending"),
    force: bool = typer.Option(False, "--force", help="Ignore the daily request budget"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    version: bool = typer.Option(False, "--version", callback=_version, is_eager=True),
):
    if fmt and fmt not in FORMATS:
        raise typer.BadParameter(f"--format must be one of {', '.join(FORMATS)}")
    ctx.obj = Ctx(fmt=fmt, dry_run=dry_run, force=force, verbose=verbose)


def run():
    """Entry point with error mapping to exit codes."""
    try:
        app()
    except ZohoError as e:
        print(f"zoho-inventory: {e}", file=sys.stderr)
        sys.exit(1)
    except ConfigError as e:
        print(f"zoho-inventory: {e}", file=sys.stderr)
        sys.exit(2)
    except DailyBudgetExceeded as e:
        print(f"zoho-inventory: {e}", file=sys.stderr)
        sys.exit(3)


# command groups
from .commands import (  # noqa: E402
    auth as _auth, api as _api, items as _items, organizations as _org,
    composite as _composite, adjustments as _adjustments, docs as _docs, generic as _generic,
)
from .modules import MODULES  # noqa: E402

app.add_typer(_auth.app, name="auth")
app.add_typer(_org.app, name="org")
app.add_typer(_items.app, name="items")
app.add_typer(_composite.app, name="composite")
app.add_typer(_adjustments.app, name="adjustments")
for _name, _m in MODULES.items():
    app.add_typer(_generic.build(_m), name=_name)
app.command("api", help=_api.__doc__)(_api.api)
app.command("docs", help=_docs.__doc__)(_docs.docs)

if __name__ == "__main__":
    run()
