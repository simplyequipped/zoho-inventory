---
name: zoho-inventory
description: Use the `zoho` CLI to read and change Zoho Inventory (items, composite items, stock, orders) from this machine. Use when asked about stock, parts, costs, SKUs, assemblies, orders, or anything in Zoho Inventory.
---

# zoho-inventory

`zoho` is installed on this box and already authenticated. Do not ask for credentials.
Run `zoho docs` for the module list and `zoho docs <module>` or `zoho <module> --help`
for details. docs/reference.md in the repo has the same content.

## Rules

- Run commands in bash. Output is JSON when piped, which is what you get.
- Read before you write: `zoho items get <sku>` before `zoho items update <sku> ...`.
- Use `--dry-run` first for any write you have not done before in this session.
- Deletes need `--yes`. Prefer `deactivate` over `delete`.
- SKU matching is exact. If a SKU is not found, list with `--sku-contains` and ask.
- Do not loop over many items with one call each when a list call will do.
  The daily request budget is shared with everything else on the box.
- Never call the Zoho API directly with curl. Everything goes through `zoho`.
- `composite assemble` changes stock. Confirm the quantity with the user before running it.

## Commands

```
zoho items list|get|create|update|activate|deactivate|delete
zoho composite list|get|parts|create|update|assemble|bundles|bundle|unassemble
zoho adjustments list|get|create|delete
zoho salesorders|purchaseorders|purchasereceives|contacts|itemgroups|locations|
     packages|shipmentorders|invoices|bills|pricelists|users  list|get|create|update|delete|do|fields
zoho org list
zoho auth status
zoho api GET|POST|PUT|DELETE <path> [--param k=v] [--json file | --data '{...}'] [--all]
```

## Field names

Zoho field names are used as-is. The ones that matter here:

- `sku` is what the Shopify sync matches on. Do not change it on synced items.
- `purchase_rate` is cost. `rate` is selling price.
- `stock_on_hand` and `available_stock` are read-only; change stock with
  `adjustments create` (corrections) or `composite assemble` (building product).
- A composite item's `mapped_items` is the parts list; `--part SKU:QTY` on
  `composite update` replaces the whole list.

## Exit codes

0 ok, 1 Zoho/API error (message on stderr), 2 usage or config, 3 daily request budget hit.
