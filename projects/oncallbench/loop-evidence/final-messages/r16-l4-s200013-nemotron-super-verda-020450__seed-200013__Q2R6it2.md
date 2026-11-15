# r16-l4-s200013-nemotron-super-verda-020450/seed-200013__Q2R6it2

Level 4, seed 200013, nemotron-super-verda, score as run 0.0107. The agent's closing message, verbatim:

The shift is over. Here's a summary of the incident and actions taken:

## Incident Summary

**Root causes found (4 cascading faults):**

| Service | Fault | Mitigation | Result |
|---------|-------|------------|--------|
| `cart-svc` | Bad deploy `v93` (memory bloat) | `rollback` at min 46 | 84% → 40% error (stuck in retry storm) |
| `ledger-svc` | Bad deploy `v87` + config `cfg-43` at min 45 | `revert_config` + `rollback` at min 84-95 | 95% → 43% error (stuck in retry storm) |
| `limits-svc` | Over capacity from retry storm (caused by ledger-svc) | `scale` to 32 at min 47 | CPU 0.99→0.35, error 95%→41% once ledger-svc improved |
| `sitemap-svc` | Bad config `cfg-31` (rate limit) | `revert_config` at min 46 | Reverted but error persisted at 4.3% |

**Cascading impact:**
- `limits-svc` → `web-storefront`, `mobile-api`
- `cart-svc` → `mobile-api`, `admin-portal`
- `ledger-svc` → `limits-svc` → `web-storefront`
- `sitemap-svc` → `subscriptions-svc` → `partner-api` (biggest revenue loss at $23,800/min)

**Final state at minute 120:**
- `web-storefront`: 40% error
- `mobile-api`: 64% error  
- `partner-api`: 4% error (unfixed — sitemap-svc revert didn't take effect)
- `admin-portal`: 42% error

**Key lesson:** The retry storms on `cart-svc` and `ledger-svc` persisted after root-cause fixes because I didn't scale them early enough to break the storm. The scales I initiated at minutes 116-117 completed too late to help. `sitemap-svc`'s config revert didn't resolve its 4% error, leaving `partner-api` as the largest ongoing loss.
