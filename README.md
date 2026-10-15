# zoho-inventory

Command-line client for the [Zoho Inventory API](https://www.zoho.com/inventory/api/v1/).
Usable from a terminal or from scripts and agents on the same box.

- Every endpoint is reachable from day one through `zoho api <METHOD> <path>`.
- Typed commands for the modules in daily use (`items` now; `composite`, `adjustments`,
  `salesorders`, `purchaseorders`, `contacts` to follow).
- Self Client OAuth: one grant exchange, refresh token stored locally, access token
  cached and renewed hourly. No browser flow, nothing hosted.
- Cross-process rate limiter keeps you under Zoho's 100 req/min and your plan's daily cap.
- `--dry-run` on every write; `--yes` required for deletes; JSON output when piped.

## Install

```bash
pipx install git+https://github.com/simplyequipped/zoho-inventory.git
# or, for development:
git clone https://github.com/simplyequipped/zoho-inventory.git && cd zoho-inventory
pip install -e ".[dev]"
```

Python 3.11+.

## One-time setup

1. Open https://api-console.zoho.com, click Add Client, choose Self Client, Create.
2. **Client Secret** tab: note the Client ID and Client Secret.
3. **Generate Code** tab. Scope (comma-separated, no spaces):

   ```
   ZohoInventory.items.ALL,ZohoInventory.compositeitems.ALL,ZohoInventory.inventoryadjustments.ALL,ZohoInventory.settings.READ
   ```

   Add `ZohoInventory.salesorders.ALL,ZohoInventory.purchaseorders.ALL,ZohoInventory.contacts.ALL`
   when you want those modules. Duration 10 minutes. Create, copy the code.
4. Within those 10 minutes:

   ```bash
   zoho auth init
   ```

   It exchanges the code, writes `~/.config/zoho-inventory/credentials.json` (mode 600),
   looks up your organization, and writes `settings.json` with the default budgets.

5. Set the daily budget to your plan (Free 1000, Standard 2000, Professional 5000,
   Premium 10000) in `~/.config/zoho-inventory/settings.json` or `ZOHO_INVENTORY_DAILY`.

Check with `zoho auth status`.

## Use

```bash
zoho items list                                   # table on a TTY, JSON when piped
zoho items list --sku-contains RNODE --format csv
zoho items get RNODE-T3S3-BLK                     # id or SKU
zoho items update RNODE-T3S3-BLK --purchase-rate 21.27
zoho items create --name "LilyGo T3S3" --sku T3S3-915 --purchase-rate 21.27 --unit pcs
zoho --dry-run items update BAT-2000 --purchase-rate 5.75

zoho api GET /compositeitems --all
zoho api POST /compositeitems --json composite.json
zoho api PUT /items/123456000000012345 --data '{"reorder_level": 5}'
```

Global options go before the subcommand: `--format table|json|csv`, `--dry-run`, `--force`, `--verbose`.

Exit codes: 0 ok, 1 Zoho/API error, 2 usage or config error, 3 daily budget exceeded.

## Rate limiting

State lives in `~/.cache/zoho-inventory/ratelimit.json`, locked with `flock`, so concurrent
`zoho` processes share one budget. Defaults: 60 requests/minute (Zoho allows 100 per
org), 1000/day, warning at 80%. A 429 from Zoho still triggers a short backoff, but
the limiter is meant to make that never happen.

## Layout

```
src/zoho_inventory/
  config.py      paths, credentials, settings
  auth.py        grant exchange, token refresh
  ratelimit.py   file-locked sliding window + daily counter
  client.py      request, pagination, error mapping
  output.py      table / json / csv
  cli.py         typer root
  commands/      one file per API module
tests/           offline tests (respx mocks); no network
.claude/skills/zoho-inventory/SKILL.md   usage notes for coding agents
```

## Tests

```bash
pytest
```

All tests are offline. A live smoke test against your org is a manual step
(see `tests/live_smoke.md`).
