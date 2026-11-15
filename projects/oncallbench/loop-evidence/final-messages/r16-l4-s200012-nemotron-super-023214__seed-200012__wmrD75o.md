# r16-l4-s200012-nemotron-super-023214/seed-200012__wmrD75o

Level 4, seed 200012, nemotron-super, score as run 0.0. The agent's closing message, verbatim:

The shift is over. Here's a summary of the incident and actions taken:

## Root Causes Identified

1. **experiments-svc** — Config change `cfg-26` narrowed `token_scope` from `[orders.read, orders.write]` to `[orders.read]`, causing `PermissionDenied` errors (90% error rate). Cascaded: payments-svc → admin-portal (~91%), and payments-svc → seo-svc → web-storefront (~28%).

2. **events-queue** — Deploy `v145` changed wire schema v2→v3, causing `DecodeError` in giftcards-svc (~4.4%), cascading to mobile-api (~4.2% at $8700/min = ~$365/min lost).

## Actions Taken

| Minute | Action | Result |
|--------|--------|--------|
| ~71 | `revert_config` experiments-svc (cfg-26) | ✅ Fixed PermissionDenied; admin-portal improved 98%→91%, web-storefront 28%→19% |
| ~72 | `rollback` events-queue (v145) | ❌ Triggered retry storm: 30% rollback failures + caller retries pushed events-queue to 99% cpu, 55% retry share, shedding 503s |
| ~109 | `throttle` events-queue 50% | ✅ Broke retry storm (cpu 0.99→0.4, retry_share 0.55→0.02), but rejected 50% of traffic |
| ~117 | `throttle` events-queue 0% | ❌ Shift ended before lift could complete |

## Final State (minute 120)

| Service | Error Rate | Revenue/min | Loss/min |
|---------|-----------|-------------|----------|
| web-storefront | 18.8% | $300 | ~$56 |
| mobile-api | 50% | $8,700 | ~$4,350 (throttle active) |
| partner-api | 0% | $750 | $0 |
| admin-portal | 91% | $350 | ~$319 |

The events-queue rollback's retry storm was the critical misstep — I should have throttled events-queue *before* rolling back to prevent caller retries from overloading it. The throttle broke the storm but the shift ended before I could lift it and confirm recovery.
