# r16-l4-s200004-nemotron-super-022632/seed-200004__kUihvFW

Level 4, seed 200004, nemotron-super, score as run 0.0. The agent's closing message, verbatim:

The shift has ended. Here's a summary of the incident and response:

## Root Causes Identified

1. **payouts-svc v67 deploy** (minute -25): Changed `deadline = budget_ms / 1000` → `/ 10000` (10× shorter), causing 45% error rate. **Fixed** with rollback (completed ~minute 103, payouts-svc recovered to 0.002).

2. **labels-svc v26 deploy** (minute 58): "query tuning" caused CPU to spike to 0.99 and error rate to 0.80. Rolled back at minute 102, but the service was stuck in a retry death spiral — needed scaling to break the cycle, but time ran out.

3. **bundles-svc cfg-50 config** (minute -10): Rate limit dropped 5000→50, causing CPU 0.99 overload. Reverted at minute 68, improved error rate from 0.93→0.40, but retry storm persisted.

4. **limits-svc v46 deploy** (minute -25): urllib3 bump causing 4% error rate. Rolled back + restarted, service back at 0.04 but not fully resolved.

## Cascading Impact

- payouts-svc → labels-svc (soft, 30%) → address-svc → experiments/pricing → **mobile-api** (0.87)
- payouts-svc → stock-svc (soft, 30%) → disputes-svc → **web-storefront** (0.23)
- bundles-svc (overload) → **mobile-api** (0.87)
- limits-svc (0.04) → **admin-portal** (0.04)

## Final State (minute 120)

| Service | Error Rate | Revenue/Min | Loss/Min |
|---------|-----------|-------------|----------|
| mobile-api | 0.867 | $550 | ~$477 |
| admin-portal | 0.04 | $12,400 | ~$496 |
| web-storefront | 0.23 | $450 | ~$104 |
| partner-api | 0.0 | $450 | $0 |

The labels-svc retry storm was the critical miss — rolling back the bad deploy wasn't enough; the service needed capacity (scale) to drain the retry backlog, but the shift ended before I could apply it.
