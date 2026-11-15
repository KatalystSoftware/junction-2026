# r16-l4-s200021-nemotron-super-023742/seed-200021__Pgxx53Q

Level 4, seed 200021, nemotron-super, score as run 0.0. The agent's closing message, verbatim:

The shift is ending (3 minutes left). Final state:

- **mobile-api**: 0.0 ✓
- **admin-portal**: 0.0 ✓
- **web-storefront**: 0.087 (recovering)
- **partner-api**: 0.087 (recovering)

web-storefront/partner-api are down from 0.57 to 0.087 as the loyalty-svc v164 rollback (completed minute 116) unwinds the final retry storm.

## Root causes found and fixed

| Service | Cause | Fix |
|---------|-------|-----|
| **loyalty-svc** | v164 memory leak (bloated process, mem 0.89→0.99, OOM restarts) → took down web-storefront + partner-api | `restart` (temp) then `rollback v164` (permanent) |
| **export-svc** | cfg-18 cut `db_pool_size 40→4` → 50% errors → took down mobile-api | `revert_config cfg-18` |
| **subscriptions-svc** | v118 removed `orders.write` scope → PermissionDenied → ranking-svc → admin-portal | `rollback v118` |
| **translations-svc** | v176 `KeyError: 'currency'` → retry storm → web-storefront + partner-api | `rollback v176` |

Retry storms (loyalty-svc, subscriptions-svc) were broken with `scale` (loyalty-svc→12, subscriptions-svc→9) to add headroom so errors could drain.

All four root causes addressed; no wasted mitigations. The remaining 0.087 on web-storefront/partner-api is the last of the loyalty-svc retry storm unwinding as the shift ends.
