# r16-l4-s200012-nemotron-super-023216/seed-200012__S4UrM9N

Level 4, seed 200012, nemotron-super, score as run 0.0. The agent's closing message, verbatim:

Shift over. Here's the incident summary:

**Root causes found and fixed:**

| # | Service | Fault | Change | Mitigation |
|---|---------|-------|--------|------------|
| 1 | `experiments-svc` | 90% errors (auth) | `cfg-26` config: removed `orders.write` scope + rotated DB password | `revert_config` |
| 2 | `events-queue` | schema `v3` → giftcards DecodeError | `v145` deploy "add tracing spans" | `rollback` |
| 3 | `experiments-svc` + `events-queue` | retry storms (CPU 99%) after root-cause fixes | — | `scale` to 2× replicas |
| 4 | `payments-svc` | 38% errors (pool exhaustion) | `v48` deploy: hardcoded `Pool(size=4)` | `rollback` |
| 5 | `ledger-svc` | 76% errors (cache TTL collapse) | `cfg-45` config: `entry_ttl_s 600→1` | `revert_config` (completes at min 121, just after shift end) |

**Causality chains cleared:**
- `experiments-svc` → `payments-svc` (hard) → `admin-portal` (hard), and via `seo-svc` (soft ~30%) → `web-storefront`
- `events-queue` → `giftcards-svc` (hard) → `mobile-api`
- `payments-svc` → `admin-portal` (hard) and `seo-svc` → `web-storefront`
- `ledger-svc` → `admin-portal` (hard)

**Final state at minute 120:** `web-storefront`, `mobile-api`, `partner-api` at 0% errors; `admin-portal` still 76% because the `ledger-svc` revert finishes at minute 121, just after the shift ended.

No throttles were used and no services were scaled down (extra replicas on `experiments-svc` 4→8 and `events-queue` 8→16 remain, costing $3/replica/minute, but that's far cheaper than the ongoing revenue loss they prevented).
