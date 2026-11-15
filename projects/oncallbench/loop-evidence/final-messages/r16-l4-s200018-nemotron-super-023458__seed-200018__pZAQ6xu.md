# r16-l4-s200018-nemotron-super-023458/seed-200018__pZAQ6xu

Level 4, seed 200018, nemotron-super, score as run 0.0. The agent's closing message, verbatim:

Shift complete. Here's a summary of the incident response:

## Root causes found and fixed

| # | Service | Cause | Mitigation | Result |
|---|---------|-------|------------|--------|
| 1 | `stock-svc` | Bad deploy `v25`: cache TTL `ttl_s // 600` caused a cache stampede hammering `payouts-svc` | `rollback` (reverted v25) | stock-svc recovered; broke the chain to web-storefront/admin-portal |
| 2 | `payouts-svc` | Self-sustaining retry spiral (stock-svc retries kept it at 0.99 CPU, 4958 rps) | `scale` to 24 replicas | Broke the cycle; payouts-svc healthy at 0.001 error |
| 3 | `emails-svc` | Bad config `cfg-58`: removed `orders.write` token scope | `revert_config` (reverted cfg-58) | emails-svc recovered; web-storefront back to 0.0 |
| 4 | `checkout-svc` | Overload spiral triggered by the v77 rollback's 30% failure window | `scale` to 12 replicas | checkout-svc back to baseline |

## Actions attempted but not effective
- `rollback checkout-svc v77`: did not fix checkout-svc's pre-existing 0.04 baseline (v77 wasn't the cause); it triggered a transient overload that I then fixed with scale.
- `rollback emails-svc v176`: wrong cause (the SQL query change wasn't the culprit); `cfg-58` config was.

## Remaining at shift end
- `mobile-api` 0.04 → `checkout-svc` baseline 0.0414 (no recent bad deploy/config to revert; ~$496/min)
- `partner-api` 0.04 → `push-svc` 0.042 (no recent fixable change; ~$26/min)
- `payouts-svc` running 16 replicas (right-sized from 24; minor extra replica cost)

The largest revenue bleeds (web-storefront via stock-svc/payouts-svc/emails-svc, and admin-portal) were stopped.
