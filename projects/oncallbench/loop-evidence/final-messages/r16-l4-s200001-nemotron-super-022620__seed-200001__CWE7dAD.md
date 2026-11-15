# r16-l4-s200001-nemotron-super-022620/seed-200001__CWE7dAD

Level 4, seed 200001, nemotron-super, score as run 0.0. The agent's closing message, verbatim:

Shift over. Final state:

| Edge Service | Error Rate | Revenue/Min | Status |
|---|---|---|---|
| web-storefront | 0.0 | $450 | Healthy |
| mobile-api | 0.04 | $18,300 | Degraded (shipping-svc baseline) |
| partner-api | 0.92 | $850 | Still failing (improved from 0.99) |
| admin-portal | 0.0 | $500 | Healthy |

**Root causes found and actions taken:**

1. **partner-api chain (99% → 0.92%):** `ranking-svc` overload (cpu 0.99, rps 15,300) triggered a retry storm cascading through `giftcards-svc` → `identity-svc` → `address-svc` → `push-svc` → `partner-api`. All were hard dependencies, so the 0.86 error propagated unchanged. Fixed by scaling: `ranking-svc` 4→16 (broke its storm), `identity-svc` 3→12, `push-svc` 4→8. The scales for identity-svc and push-svc landed at minutes 117-118, too late to fully recover before shift end.

2. **mobile-api (0.04%):** `shipping-svc` steady 0.04% error with healthy deps and fine cpu. I rolled back `shipping-svc` v127 (deploy at -26 matched error onset), but this **triggered a retry storm** via `quotes-svc` (callers_retry=3) retrying the rollback's 30% failures — spiking mobile-api to 0.45%. The rollback was likely unnecessary (0.04% persisted after rollback, so v127 wasn't the cause) and cost a wasted mitigation + storm. Scaling `shipping-svc` 8→12 broke that storm, returning to 0.04%.

**Key lesson:** retry storms are self-sustaining; adding capacity (scale) breaks them, but the first scale must be large enough (ranking-svc needed 16, not 8). And rolling back a service whose callers retry can turn a small fault into a storm.

The shift is complete — no further actions possible.
