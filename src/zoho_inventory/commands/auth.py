"""One-time setup and status.

```
zoho auth init        interactive: client id, secret, grant code -> credentials file
zoho auth status      token expiry, organization, rate-limit usage
zoho auth refresh     force a new access token now
```

Setup, step by step
-------------------
1. https://api-console.zoho.com, Add Client, Self Client, Create.
2. Client Secret tab: copy Client ID and Client Secret.
3. Generate Code tab: scope, e.g.
       ZohoInventory.items.ALL,ZohoInventory.compositeitems.ALL,
       ZohoInventory.inventoryadjustments.ALL,ZohoInventory.settings.READ
   duration 10 minutes, any description. Create, then copy the code.
4. Run `zoho auth init` within those 10 minutes and paste all three.

The command exchanges the code, stores the refresh token (mode 600), then
calls /organizations and stores the organization_id. If more than one
organization is visible it lists them and asks which to use.
"""

from __future__ import annotations

import time

import typer

from .. import auth as _auth
from ..client import ZohoClient
from ..config import Credentials, Settings, credentials_path, DEFAULT_ACCOUNTS_URL
from ..output import emit
from ..ratelimit import RateLimiter

app = typer.Typer(help=__doc__, no_args_is_help=True)


@app.command("init")
def init(
    ctx: typer.Context,
    client_id: str = typer.Option(None, prompt="Client ID"),
    client_secret: str = typer.Option(None, prompt="Client Secret", hide_input=True),
    grant_code: str = typer.Option(None, prompt="Grant code (from Generate Code tab)"),
    accounts_url: str = typer.Option(DEFAULT_ACCOUNTS_URL, help="Change for .eu/.in/.com.au data centers"),
    organization_id: str = typer.Option(None, help="Skip the lookup and use this organization"),
):
    """Exchange a Self Client grant code and write the credentials file."""
    creds = _auth.exchange_grant(client_id.strip(), client_secret.strip(), grant_code.strip(), accounts_url)
    creds.save()
    typer.echo(f"Refresh token stored in {credentials_path()}")

    if organization_id:
        creds.organization_id = organization_id
    else:
        client = ZohoClient(creds=creds)
        orgs = client.get("/organizations").get("organizations", [])
        if not orgs:
            typer.echo("No organizations visible to this client; set one with --organization-id", err=True)
            raise typer.Exit(2)
        if len(orgs) == 1:
            creds.organization_id = str(orgs[0]["organization_id"])
            typer.echo(f"Organization: {orgs[0]['name']} ({creds.organization_id})")
        else:
            for i, o in enumerate(orgs, 1):
                typer.echo(f"  {i}. {o['name']} ({o['organization_id']})")
            n = typer.prompt("Which organization?", type=int)
            creds.organization_id = str(orgs[n - 1]["organization_id"])
    creds.save()
    Settings.load().save()  # write settings.json with defaults so the budgets are visible/editable
    typer.echo("Done. Try: zoho items list")


@app.command("status")
def status(ctx: typer.Context):
    """Show token state, organization, and rate-limit usage."""
    creds = Credentials.load()
    s = Settings.load()
    ttl = int(creds.access_expires_at - time.time())
    limiter = RateLimiter(rpm=s.requests_per_minute, daily=s.requests_per_day)
    emit(
        {
            "organization_id": creds.organization_id,
            "api_domain": creds.api_domain,
            "access_token_valid_for_s": max(ttl, 0),
            "access_token_cached": bool(creds.access_token),
            **limiter.status(),
            "credentials_file": str(credentials_path()),
        },
        ctx.obj.fmt,
    )


@app.command("refresh")
def refresh(ctx: typer.Context):
    """Force a new access token now."""
    creds = Credentials.load()
    _auth.ensure_access_token(creds, force=True)
    typer.echo(f"New access token valid for {int(creds.access_expires_at - time.time())}s")
