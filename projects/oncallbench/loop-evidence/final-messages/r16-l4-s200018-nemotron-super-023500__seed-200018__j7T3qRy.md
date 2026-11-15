# r16-l4-s200018-nemotron-super-023500/seed-200018__j7T3qRy

Level 4, seed 200018, nemotron-super, score as run 0.0. The agent's closing message, verbatim:

The shift is over (minute 120). No further actions possible.

## Final state

| Edge service | Error rate | Revenue/min | Lost/min |
|---|---|---|---|
| web-storefront | 0.51 | $600 | $306 |
| mobile-api | 0.04 | $12,400 | $496 |
| partner-api | 0.04 | $650 | $26 |
| admin-portal | 0.00 | $550 | $0 |

## What was fixed
- **stock-svc** — bad deploy v25 (`ttl_s // 600` cache bug) → rolled back. This collapsed the stock-svc ↔ payouts-svc retry storm.
- **payouts-svc** — self-sustaining retry storm (stock-svc retrying shed load) → scaled to 24 replicas to absorb load and break the storm. Recovered admin-portal to 0.0.
- **checkout-svc** — retry storm (cart-svc retries) triggered by rollback disruption → scaled to 8 to break it. Recovered mobile-api from 0.46 → 0.04.
- **media-svc** — slow (p99 ~192ms) causing push-svc/checkout-svc timeouts → scaled to 10 (cpu down, but p99 didn't improve enough to clear the 50ms timeout baseline).

## What remained
- **emails-svc** at 0.51 error (healthy deps, no overload, p99 851ms) — emails-svc's own fault, masked earlier by stock-svc's higher failure. Discovered at the very end with no time left to diagnose/apply a mitigation. This is why web-storefront is still at 0.51.
- mobile-api/partner-api sit at the 0.04 media-svc timeout baseline (above the <1% normal, but small bleed).

The shift ended with web-storefront still failing due to the undiscovered emails-svc fault. If I had more time, I'd check emails-svc's changes/logs to identify whether it's a bad deploy (rollback), bad config (revert_config), or stuck process (restart).
