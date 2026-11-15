# r16-l4-s200001-nemotron-super-verda-014310/seed-200001__meZQroP

Level 4, seed 200001, nemotron-super-verda, score as run 0.0. The agent's closing message, verbatim:

The shift is over (minute 120). Final state:

| Service | Error Rate | Revenue/Min | Loss/Min |
|---|---|---|---|
| web-storefront | 0.0% | $450 | $0 |
| mobile-api | 4.0% | $18,300 | ~$732 |
| partner-api | 96.3% | $850 | ~$819 |
| admin-portal | 0.0% | $500 | $0 |

## What happened

**Two independent root causes:**

1. **`ranking-svc` overload/retry storm** → cascaded through `giftcards-svc` → `identity-svc` → `address-svc` → `push-svc` → `partner-api` (99% errors). 
   - Scaled `ranking-svc` 4→16: fully recovered (storm broke).
   - Scaled `identity-svc` 3→8: partially broke the secondary storm, but it hadn't fully converged by shift end (partner-api still at 96.3%).

2. **`shipping-svc`** (4% errors → `mobile-api` 4%).
   - Rolled back deploy v127 (didn't resolve the 4% — likely a wasted mitigation), which triggered a retry storm. Scaled `shipping-svc` 8→16 to break the storm. `mobile-api` remained at its 4% baseline — the root cause was never found (possibly `catalog-db` at 87% CPU, never investigated).

## Lessons for next time
- Replay storms from rollbacks/restarts can be worse than the original fault — scale first to give headroom before disruptive mitigations.
- `identity-svc` needed more replicas (or earlier action) to fully converge before the shift ended.
- `shipping-svc`'s 4% root cause was never identified — `catalog-db`'s sustained 87% CPU was a lead worth pursuing.
