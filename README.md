# zoho-inventory

Command-line client for the [Zoho Inventory API](https://www.zoho.com/inventory/api/v1/).
Usable from a terminal or from scripts and agents on the same box.

- Every endpoint is reachable through `zoho api <METHOD> <path>`.
- Typed commands for items, composite items (assemblies), and adjustments.
- Generic list/get/create/update/delete/do groups for sales orders, purchase orders,
  purchase receives, contacts, item groups, locations, packages, shipments, invoices,
  bills, price lists, and users. Adding a module is one entry in `modules.py`.
- Self Client OAuth: one grant exchange, refresh token stored locally, access token
  cached and renewed hourly. No browser flow, nothing hosted.
- Cross-process rate limiter keeps you under Zoho's 100 req/min and your plan's daily cap.
- `--dry-run` on every write; `--yes` required for deletes; JSON output when piped.

## Install

Python 3.11+. No pipx needed.

```bash
git clone https://github.com/simplyequipped/zoho-inventory.git
cd zoho-inventory
python3 -m venv .venv
.venv/bin/pip install -e .
ln -s "$PWD/.venv/bin/zoho" ~/.local/bin/zoho      # or add .venv/bin to PATH
```

For development add the test deps: `.venv/bin/pip install -e ".[dev]"`.

To update later: `git pull` (editable install picks it up).

## One-time setup

1. Open https://api-console.zoho.com, click Add Client, choose Self Client, Create.
2. Client Secret tab: note the Client ID and Client Secret.
3. Generate Code tab. Scope (comma-separated, no spaces):

   ```
   ZohoInventory.items.ALL,ZohoInventory.compositeitems.ALL,ZohoInventory.inventoryadjustments.ALL,ZohoInventory.settings.READ
   ```

   Add `ZohoInventory.salesorders.ALL,ZohoInventory.purchaseorders.ALL,ZohoInventory.purchasereceives.ALL,ZohoInventory.contacts.ALL`
   and so on for the other groups as you need them. Duration 10 minutes. Create, copy the code.
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
zoho items get RNODE-T3S3-BLK                     # id or SKU everywhere
zoho items update BAT-2000 --purchase-rate 5.75
zoho items create --name "LilyGo T3S3 915" --sku T3S3-915 --purchase-rate 21.27 --unit pcs

zoho composite create --name "RNode T3S3 Black" --sku RNODE-T3S3-BLK --rate 150 \
    --part T3S3-915:1 --part BAT-2000:1 --part ANT-915:1 --part CASE-T3S3-BLK:1
zoho composite parts RNODE-T3S3-BLK
zoho composite assemble RNODE-T3S3-BLK --qty 10 --ref "batch 2026-10"
zoho composite bundles RNODE-T3S3-BLK

zoho adjustments create --reason "cycle count" --line BAT-2000:-2 --line ANT-915:+5

zoho salesorders list --status confirmed
zoho purchaseorders fields
zoho api GET /compositeitems --all
zoho api PUT /items/123456000000012345 --data '{"reorder_level": 5}'

zoho docs                 # module overview
zoho docs composite       # one module
```

Global options go before the subcommand: `--format table|json|csv`, `--dry-run`, `--force`, `--verbose`.

Exit codes: 0 ok, 1 Zoho/API error, 2 usage or config error, 3 daily budget exceeded.

Full command reference: [docs/reference.md](docs/reference.md) (regenerate with
`zoho docs --markdown > docs/reference.md`).

## Rate limiting

State lives in `~/.cache/zoho-inventory/ratelimit.json`, locked with `flock`, so concurrent
`zoho` processes share one budget. Defaults: 60 requests/minute (Zoho allows 100 per
org), 1000/day, warning at 80%. A 429 from Zoho still triggers a short backoff, but
the limiter is meant to make that never happen.

## Known unknowns

Zoho's public docs do not show the request body for creating an assembly
(`POST /bundles`). `composite assemble` sends `composite_item_id`, `quantity_to_bundle`,
`date`, `is_completed`, and `line_items[]{item_id, quantity_consumed}`, which is what
third-party connectors use. If Zoho rejects `quantity_consumed`, add
`"bundle_qty_key": "quantity"` to `settings.json`. First live run should be with
`--dry-run` and then `--qty 1`.

## Layout

```
src/zoho_inventory/
  config.py      paths, credentials, settings
  auth.py        grant exchange, token refresh
  ratelimit.py   file-locked sliding window + daily counter
  client.py      request, pagination, error mapping
  output.py      table / json / csv
  modules.py     descriptors for the generic command groups
  cli.py         typer root
  commands/      items, composite, adjustments, api, auth, org, docs, generic
tests/           offline tests (respx mocks); no network
docs/reference.md
.claude/skills/zoho-inventory/SKILL.md   usage notes for coding agents
```

## Tests

```bash
.venv/bin/pytest
```

All tests are offline. A live smoke test against your org is a manual step
(see `tests/live_smoke.md`).
