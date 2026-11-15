# r16-l4-s200020-nemotron-super-023526/seed-200020__2gsqLCL

Level 4, seed 200020, nemotron-super, score as run 0.0. The agent's closing message, verbatim:

Incident resolved. All four edge services at 0.0% error with 6 minutes remaining.

## Summary

**Root causes found and fixed:**

| Service | Root Cause | Fix |
|---|---|---|
| **push-svc** | `cfg-16` set `rate_limit_per_s: 5000→50` (93% error), then stuck in retry-storm overload | `revert_config` + `scale` to 8, then back to 4 |
| **mobile-api** (22500/min — biggest loss) | suggest-svc `v39` deploy made it slow (200ms p99 > 50ms rpc budget) | `rollback suggest-svc v39` |
| **fraud-svc** | OOM from retry storm, then risk-db dependency failure | `restart`, then fixed via risk-db |
| **risk-db** | `cfg-11` removed `'currency'` from `price_fields` → `KeyError` | `revert_config risk-db cfg-11` |

**Dependency chain:** push-svc → fraud-svc → web-storefront/admin-portal, and risk-db → fraud-svc → web-storefront/admin-portal. Fixing the leaf causes (push-svc, risk-db) resolved everything upstream.

**Actions:** revert_config push-svc, rollback mobile-api (wasted — wrong cause), restart fraud-svc, scale suggest-svc (wasted — wrong cause), rollback push-svc, rollback suggest-svc (the real mobile-api fix), scale push-svc to 8 (broke overload cycle), revert_config risk-db (the real fraud-svc fix), then scaled push-svc and suggest-svc back to normal replica counts.

**Final state:** All edge services 0% error, no operations in progress, no throttles.
