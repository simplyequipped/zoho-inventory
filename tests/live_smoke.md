# Live smoke test

Manual. Runs against the real organization. Never automate this.

```bash
zoho auth status
zoho org list
zoho items list --limit 5
zoho items create --name "ZZ-TEST delete me" --sku ZZ-TEST --purchase-rate 1 --unit pcs
zoho items get ZZ-TEST
zoho items update ZZ-TEST --purchase-rate 2
zoho items get ZZ-TEST | grep purchase_rate       # expect 2
zoho items delete ZZ-TEST --yes
zoho auth status                                  # check request counts moved
```

Then record a few real responses (scrubbed of ids you care about) under
tests/fixtures/ if the shapes differ from what the offline tests assume.
