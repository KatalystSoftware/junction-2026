# r16-l4-s200017-nemotron-super-023456/seed-200017__bxPuWv4

Level 4, seed 200017, nemotron-super, score as run 0.0. The agent's closing message, verbatim:

The shift is over. All edge services are recovered except `admin-portal` at 4% error rate (852/min lost). Let me provide a summary.

## Incident Summary

**Root causes identified and mitigated:**

| # | Service | Issue | Mitigation | Result |
|---|---------|-------|------------|--------|
| 1 | `ledger-svc` | Bad deploy v80 (deadline /1000→/10000) + bad config cfg-51 | revert_config + rollback | Recovered |
| 2 | `ledger-svc` | Retry storm (cpu 0.99, 3x rps) | scale 3→9 replicas | Recovered |
| 3 | `suggest-svc` | Stuck in overload loop (cpu/mem 0.99, 10 restarts) | restart + scale 6→12 | Recovered |
| 4 | `labels-svc` | Bad config cfg-44 (rate_limit 5000→50, causing 429s) | revert_config | Recovered |
| 5 | `recommendations-svc` | Bad deploy v108 (new endpoint) | rollback | Partially fixed |

**Cascading chains fixed:**
- `ledger-svc` → `push-svc` → `suggest-svc` → `checkout-svc` → `labels-svc` → `mobile-api`
- `ledger-svc` → `media-svc` → `couriers-svc` → `web-storefront`
- `ledger-svc` → `push-svc` (soft via `returns-svc`) → `partner-api`
- `recommendations-svc` → `disputes-svc` → `admin-portal`

**Final state:**
- `web-storefront`: 0% ✓
- `mobile-api`: 0% ✓
- `partner-api`: 0% ✓
- `admin-portal`: 4% ✗ (unresolved — `recommendations-svc` still at ~4% after rollback)

**Mitigations applied:** 7 (all on services that needed them — no wasted mitigations). Extra replicas: ledger-svc +6, suggest-svc +6.
