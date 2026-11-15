# r16-l4-s200021-nemotron-super-023700/seed-200021__A5CVr6g

Level 4, seed 200021, nemotron-super, score as run 0.3001. The agent's closing message, verbatim:

Shift over. Final results:

**Resolved (3 of 4 edge services at 0.0 error):**
- `web-storefront` — fixed by rolling back `loyalty-svc` v164 (memory leak) and `translations-svc` v176 (KeyError bug)
- `mobile-api` — fixed by reverting `export-svc` cfg-18 (db_pool_size 40→4 causing pool timeouts)
- `partner-api` — fixed by the same loyalty-svc and translations-svc rollbacks

**Still broken:**
- `admin-portal` at 0.045 error — caused by `ranking-svc` getting `PermissionDenied: scope 'orders.write' missing` when calling `subscriptions-svc`. Likely from subscriptions-svc config change `cfg-15` or deploy `v118` at minute -20. I identified the root cause but ran out of time to apply a mitigation (revert_config on subscriptions-svc).

**Mitigations applied:** revert_config(export-svc), rollback(loyalty-svc), rollback(translations-svc), scale(loyalty-svc→12), scale(couriers-svc→20)
