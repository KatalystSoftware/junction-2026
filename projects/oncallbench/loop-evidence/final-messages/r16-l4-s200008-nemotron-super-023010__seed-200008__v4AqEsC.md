# r16-l4-s200008-nemotron-super-023010/seed-200008__v4AqEsC

Level 4, seed 200008, nemotron-super, score as run 0.2901. The agent's closing message, verbatim:

Shift complete. Here's the incident summary:

## Root causes and actions

| # | Service | Issue | Fix | Result |
|---|---------|-------|-----|--------|
| 1 | **sitemap-svc** | Config `cfg-48` removed `currency` from `price_fields` → `KeyError` | `revert_config` (min 41) | partner-api: 77% → 0.04% |
| 2 | **profile-db** | Config `cfg-32` dropped `orders.write` scope → `PermissionDenied` | `revert_config` (min 81) | Fixed cascade: profile-db → risk-svc → couriers-svc → mobile-api |
| 3 | **couriers-svc** | Self-sustaining retry storm (72% retries, queue full) since min -13 | `scale` to 12 replicas (min 82) | mobile-api: 97.6% → 0% |
| 4 | **wishlist-svc** | Connection pool timeout to promo-cache (4% error) | Reverted `cfg-26` + scaled promo-cache | Unresolved — revert didn't take effect, restart too costly for remaining time |

## Final state (minute 120)

| Edge service | Error rate | Revenue/min | Loss/min |
|---|---|---|---|
| mobile-api | 0% | 750 | $0 |
| partner-api | 0.04% | 350 | negligible |
| web-storefront | 4% | 550 | $22/min |
| admin-portal | 4% | 15,600 | $624/min |

Three of four major faults were extinguished. The remaining wishlist-svc connection pool issue (~$646/min) persisted because the config revert didn't take effect at runtime and a restart would have cost more than the remaining shift loss.
