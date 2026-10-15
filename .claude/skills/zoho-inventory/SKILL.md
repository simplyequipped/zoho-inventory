---
name: zoho-inventory
description: Use the `zoho` CLI to read and change Zoho Inventory (items, composite items, stock) from this machine. Use when asked about stock, parts, costs, SKUs, assemblies, or anything in Zoho Inventory.
---

# zoho-inventory

`zoho` is installed on this box and already authenticated. Do not ask for credentials.

## Rules

- Run commands in bash. Output is JSON when piped, which is what you get.
- Read before you write: `zoho items get <sku>` before `zoho items update <sku> ...`.
- Use `--dry-run` first for any write you have not done before in this session.
- Deletes need `--yes`. Prefer `deactivate` over `delete`.
- SKU matching is exact. If a SKU is not found, list with `--sku-contains` and ask.
- Do not loop over many items with one call each when a list call will do.
- Never call the Zoho API directly with curl. Everything goes through `zoho`.

## Commands

```
zoho items list [--sku X | --sku-contains X | --name-contains X | --search X] [--status active]
zoho items get <id|sku>
zoho items create --name N --sku S --purchase-rate R [--rate R] [--unit pcs] [--json file]
zoho items update <id|sku> [--purchase-rate R] [--rate R] [--name N] [--json file]
zoho items activate|deactivate <id|sku>
zoho org list
zoho auth status
zoho api GET|POST|PUT|DELETE <path> [--param k=v] [--json file | --data '{...}'] [--all]
```

Endpoints without a typed command go through `zoho api`. Paths are relative to
`/inventory/v1`; see https://www.zoho.com/inventory/api/v1/ for request bodies.

## Field names

Zoho field names are used as-is. The ones that matter here:

- `sku` is what the Shopify sync matches on. Do not change it on synced items.
- `purchase_rate` is cost. `rate` is selling price.
- `stock_on_hand`, `available_stock` are read-only on items; change stock with
  an inventory adjustment or by assembling a composite item.

## Exit codes

0 ok, 1 Zoho/API error (message on stderr), 2 usage or config, 3 daily request budget hit.
