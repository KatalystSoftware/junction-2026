# r16-l4-s200000-nemotron-super-022618/seed-200000__wVYvrAW

Level 4, seed 200000, nemotron-super, score as run 0.2259. The agent's closing message, verbatim:

Shift over. Here's the incident summary and final state.

## What I found and fixed

**1. `audit-svc` — root cause of the main fire (web-storefront/mobile-api at 92%)**
- Deploy `v44` (minute -19) changed the rate-limiter to `refill = rate * elapsed / 1000` (1000× slower refill → request blocking → CPU 99%, 4× rps, retry storm).
- Fixed with `rollback audit-svc` (reverted v44), then `scale audit-svc 3→6` to break the self-sustaining retry storm. `audit-svc` → 0.003%.

**2. `checkout-svc` — new fault that started mid-shift (minute 54)**
- Config `cfg-52` (minute 50) changed `entry_ttl_s: 600 → 1`, smashing the cache TTL → 4× rps, CPU 99%, overload. This drove `mobile-api` to 97%.
- The `v132` deploy (urllib3 bump + harmless UI string) was the decoy.
- Fixed with `revert_config checkout-svc` (reverted cfg-52), then `scale checkout-svc 8→16` to break the storm. `checkout-svc` → 0.0017%.

**3. `limits-svc` — persistent connection-pool storm (couldn't fully break)**
- `pool.acquire()` timeouts under retry load from `web-storefront`/`mobile-api` (both retry it 3×). Self-sustaining: limits-svc fails 37% → they retry → pool exhausts → more failures.
- A 30% throttle *added* failures without breaking the storm, so I turned it off. Scale would have fixed it but takes 4 min and ran out of time. `limits-svc` stayed at ~37%.

**4. `consent-svc` — persistent 4% fault (unresolved)**
- Healthy deps (`stock-svc`), healthy CPU, no bad change (only a harmless log-level config). Cause unidentified. Drove `partner-api` to 4% (~$760/min lost).

## Final state (minute 120)
| Edge service | Error rate | Revenue/min |
|---|---|---|
| web-storefront | 37.8% | 600 |
| mobile-api | 37% | 500 |
| partner-api | 4% | 19000 |
| admin-portal | 0% | 450 |

Remaining cost drivers: `limits-svc` storm (web-storefront/mobile-api), `consent-svc` 4% (partner-api), plus extra replica costs for audit-svc/limits-svc/checkout-svc scaled up during the shift. Two things I'd do with more time: scale `limits-svc` to break its pool storm, and investigate/restart `consent-svc`.
