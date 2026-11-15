# r16-l4-s200018-nemotron-super-verda-020941/seed-200018__SvuCjmM

Level 4, seed 200018, nemotron-super-verda, score as run 0.0. The agent's closing message, verbatim:

The shift is over. Here's a summary of the incident and what I did.

## Root causes found

| Service | Problem | Root cause | Fix |
|---|---|---|---|
| **stock-svc** | cpu 0.99, error 0.95, overload | Bad deploy `v25`: cache TTL changed to `ttl_s // 600` (expires 600× faster) | `rollback` (reverted v25) |
| **payouts-svc** | cpu 0.99, error 0.87, retry storm | Self-sustaining retry loop from stock-svc's retries (hard dep) | `scale` 6→12→24 replicas |
| **checkout-svc** | error 0.043, then overload storm | Bad deploy `v77` (rollback didn't clear the 0.043 baseline); rollback disruption triggered cart-svc retry storm | `rollback`, then `scale` 3→6 to clear storm, then `scale` back to 3 (free) |
| **push-svc** | error 0.04 steady | Not resolved (small loss, partner-api) | — |

## Cascade fixed
- stock-svc → payouts-svc retry storm was driving **web-storefront** (0.95) and **admin-portal** (via disputes-svc, 0.28)
- checkout-svc overload was driving **mobile-api** (spiked to 0.47)

## Final state at minute 120
| Edge service | Error rate | Revenue/min | Status |
|---|---|---|---|
| web-storefront | 0.51 | 600 | Improved (0.95→0.51), not fully resolved — likely another dep (limits-svc/emails-svc) I didn't get to |
| mobile-api | 0.04 | 12400 | Back to baseline (was 0.47 during checkout storm) |
| partner-api | 0.04 | 650 | Unchanged baseline (push-svc not addressed) |
| admin-portal | 0.00 | 550 | Fully resolved |

## Lessons / missteps
- `restart` on payouts and checkout did nothing (restart "does not remove the cause" — these were overload storms, not stuck processes).
- The `checkout-svc` rollback didn't clear its 0.043 error baseline and triggered an overload storm that I then had to scale out of — a costly misstep.
- web-storefront is still at 0.51 at shift end, meaning there's at least one more failing dependency I didn't have time to trace (likely limits-svc or emails-svc).
