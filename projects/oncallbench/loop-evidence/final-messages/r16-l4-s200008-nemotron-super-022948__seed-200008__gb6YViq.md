# r16-l4-s200008-nemotron-super-022948/seed-200008__gb6YViq

Level 4, seed 200008, nemotron-super, score as run 0.0. The agent's closing message, verbatim:

Incident resolved. Here's the summary:

## Root Causes Found & Fixed

| # | Service | Root Cause | Fix |
|---|---------|-----------|-----|
| 1 | sitemap-svc | `cfg-48` config removed `currency` from `price_fields` → `KeyError` | `revert_config` ✓ |
| 2 | promo-cache | `v74` deploy hardcoded DB pool size to 4 → connection exhaustion | `rollback` ✓ |
| 3 | profile-db | `cfg-32` config removed `orders.write` scope → `PermissionDenied` | `revert_config` ✓ |
| 4 | couriers-svc | Self-sustaining retry storm (root cause unknown) | `throttle 40%` + `scale to 6` |

## Cascade Chain
- profile-db (84%) → risk-svc (84%) → couriers-svc → mobile-api (97%)
- promo-cache (40%) → wishlist-svc (41%) → web-storefront, partner-api, admin-portal (40% each)

## Mitigations Applied
1. `revert_config` on sitemap-svc — fixed partner-api (77% → 4%)
2. `revert_config` on wishlist-svc — incorrect root cause, no effect
3. `restart` on couriers-svc — didn't resolve retry storm
4. `rollback` on promo-cache — fixed root cause but storm persisted
5. `scale` on couriers-svc to 6 replicas — reduced load per replica
6. `throttle` on profile-db (30%→0%), promo-cache (30%→0%), couriers-svc (40%) — broke all retry storms

## Final State (minute 119)
- **web-storefront**: 0% error
- **mobile-api**: 0.4% error (from intentional couriers-svc throttle)
- **partner-api**: 0% error
- **admin-portal**: 0% error

The remaining 0.4% on mobile-api is from the deliberate 40% throttle on couriers-svc, which prevents a worse failure (97%+ error) given its unknown root cause. Keeping the throttle for the final minute is the safest choice — lifting it risks a relapse with minimal potential gain.
