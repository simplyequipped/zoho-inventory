# Live smoke test

Manual. Runs against the real organization. Never automate this.

## Read side

```bash
zoho auth status
zoho org list
zoho items list --limit 5
zoho composite list --limit 5
zoho composite parts <an existing composite sku>
zoho adjustments list --limit 3
zoho salesorders list --limit 3
```

## Write side, with throwaway records

```bash
zoho items create --name "ZZ-TEST part A" --sku ZZ-A --purchase-rate 1 --rate 2 --unit pcs --initial-stock 10 --initial-stock-rate 1
zoho items create --name "ZZ-TEST part B" --sku ZZ-B --purchase-rate 1 --rate 2 --unit pcs --initial-stock 10 --initial-stock-rate 1
zoho items update ZZ-A --purchase-rate 1.5
zoho items get ZZ-A | grep purchase_rate                    # expect 1.5

zoho composite create --name "ZZ-TEST assembly" --sku ZZ-ASM --rate 10 --part ZZ-A:1 --part ZZ-B:2
zoho composite parts ZZ-ASM

zoho --dry-run composite assemble ZZ-ASM --qty 1           # inspect the body
zoho composite assemble ZZ-ASM --qty 1                      # the first real bundle call
zoho composite get ZZ-ASM | grep stock_on_hand              # expect 1
zoho items get ZZ-B | grep stock_on_hand                    # expect 8
```

If the assemble call fails with a message about line items, set
`"bundle_qty_key": "quantity"` in `~/.config/zoho-inventory/settings.json` and retry.
Note which key worked in README under Known unknowns.

```bash
zoho adjustments create --reason "smoke test" --line ZZ-A:-1
zoho items get ZZ-A | grep stock_on_hand                    # expect 8
```

## Cleanup

```bash
zoho composite bundles ZZ-ASM                               # note the bundle_id
zoho composite unassemble <bundle_id> --yes
zoho composite delete ZZ-ASM --yes
zoho adjustments list --limit 1                             # note the id, delete it
zoho adjustments delete <id> --yes
zoho items delete ZZ-A --yes
zoho items delete ZZ-B --yes
zoho auth status                                            # request counts moved
```

If delete refuses because of transactions, deactivate instead.
