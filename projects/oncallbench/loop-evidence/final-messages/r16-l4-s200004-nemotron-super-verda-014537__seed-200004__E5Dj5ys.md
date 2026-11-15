# r16-l4-s200004-nemotron-super-verda-014537/seed-200004__E5Dj5ys

Level 4, seed 200004, nemotron-super-verda, score as run 0.0. The agent's closing message, verbatim:

The shift is over (minute 120). Here's a summary of the incident and actions taken:

## Root Causes Found & Fixed

1. **payouts-svc** (45% errors → fixed): Deploy v67 changed `deadline = budget_ms / 1000` → `/ 10000` (10x shorter deadlines causing timeouts). **Rollback v67** fixed it.

2. **bundles-svc** (92% errors → fixed): Config cfg-50 cut `rate_limit_per_s: 5000 → 50`. **Revert config cfg-50** + scaled to 16 replicas to break the retry-overload cascade.

3. **labels-svc cascade** (77% errors on 8 services → fixed): Config cfg-4 changed `entry_ttl_s: 600 → 1` (killing cache). **Revert config cfg-4** + scaled to 16 replicas. This affected address-svc, risk-svc, subscriptions-svc, pricing-svc, couriers-svc, experiments-svc, seo-svc.

4. **web-storefront** (4% → 0%): Recovered as part of the labels-svc fix (via disputes-svc → stock-svc → labels-svc soft dep chain).

## What Went Wrong

5. **limits-svc / feeds-svc** (4% → 51.9%): The original issue was `PermissionDenied: scope 'orders.write' missing` from feeds-svc v136 deploy ("new endpoint behind a flag"). I reverted feeds-svc cfg-4 (didn't help), then **rolled back v136**. The rollback's 30% failure during its 6-minute run triggered an overload cascade on feeds-svc (`callers_retry: 3`), which I attempted to fix with a scale at minute 120 — but it completes at minute 123, 3 minutes after shift end.

## Final Status (minute 120)
| Service | Error Rate | Revenue/min |
|---|---|---|
| web-storefront | 0% | $450 |
| mobile-api | 41.75% | $550 |
| partner-api | 0% | $450 |
| admin-portal | 41.75% | $12,400 |

The feeds-svc scale (to 12 replicas) is still in progress and should resolve the remaining overload, but those final minutes are charged. The key lesson: when rolling back a service with retrying callers, scale first to absorb the disruption, then roll back.
