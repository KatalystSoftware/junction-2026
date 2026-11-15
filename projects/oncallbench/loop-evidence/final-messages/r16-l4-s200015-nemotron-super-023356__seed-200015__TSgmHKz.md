# r16-l4-s200015-nemotron-super-023356/seed-200015__TSgmHKz

Level 4, seed 200015, nemotron-super, score as run 0.0. The agent's closing message, verbatim:

Shift complete. Here's the incident summary:

## Root causes & actions

| # | Service | Cause | Fix | Result |
|---|---------|-------|-----|--------|
| 1 | **checkout-svc** | Bad deploy v85 (removed `orders.write` scope) → 83% errors, cascaded to recommendations-svc → cart-svc → partner-api (95%) | `rollback` + `scale to 8` (broke overload/retry loop) | Healthy (0.1%) |
| 2 | **banners-svc** | Bad config cfg-44 (removed `currency` from price_fields) → 51% errors | `revert_config` | Healthy (partner-api 74%→47%) |
| 3 | **cart-svc** | Stuck in overload from cascade (dep now healthy) | Scaled to 8, but stuck at 47% | Still 47% at shift end |
| 4 | **ranking-svc** | Intrinsic 4% fault (no bad deploy/config found; healthy deps) | Tried `revert_config` (wrong, $10k wasted), `restart` (caused overload, fixed with scale to 6) | Still 4% at shift end |

## Mistakes
- `revert_config` on ranking-svc was wrong → **$10,000 wasted**.
- `restart` on ranking-svc triggered an overload loop (required a `scale` to recover).

## Final state (minute 120)
- web-storefront: 4% (ranking-svc), admin-portal: 4% (ranking-svc), partner-api: 47% (cart-svc), mobile-api: 0%

With ~3 minutes remaining, no mitigation could complete before the shift ended (restart would've caused 50% failure during the final minutes). Cart-svc and ranking-svc remained degraded, capping the score. The avoidable cost from checkout-svc and banners-svc was recovered; ranking-svc and cart-svc losses ran to the end.
