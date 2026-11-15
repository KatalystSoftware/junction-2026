# r16-l4-s200013-nemotron-super-023230/seed-200013__iuk7QfV

Level 4, seed 200013, nemotron-super, score as run 0.0. The agent's closing message, verbatim:

The shift has ended (minute 120). Here's the incident summary:

## Root causes found & actions taken

| # | Service | Root cause | Action | Result |
|---|---------|-----------|--------|--------|
| 1 | `cart-svc` | v93 deploy (dependency bump) → memory leak / OOM | `rollback v93` (completed m59) | Recovering (error 0.84→0.40) |
| 2 | `limits-svc` | Overload at capacity (cpu 0.99 at normal load) | `scale → 32 replicas` (completed m58) | Internally healthy (cpu 0.35) |
| 3 | `ledger-svc` | v87 deploy ("refactor request handlers") + cfg-43 config ("tune connection pool") at m45 | `rollback v87` (completed m89) | ❌ Did not fix — wasted mitigation |
| 4 | `ledger-svc` | cfg-43 config was the actual cause (PermissionDenied scope error) | `revert_config cfg-43` (completed m106) | ✅ Fixed — error 95%→46%, recovering |
| 5 | `sitemap-svc` | 4.2% steady error (drives `partner-api` 4%) | `revert_config cfg-31` (completed m54) | ❌ Did not fix — `partner-api` still 4% |

## Edge service state at shift end (minute 110-120)

| Service | Error rate | Revenue/min | Loss/min | Trend |
|---------|-----------|-------------|----------|-------|
| web-storefront | 0.46 | $500 | $228 | ↓ improving (was 0.95) |
| mobile-api | 0.67 | $500 | $337 | ↓ improving (was 0.97) |
| partner-api | 0.04 | $23,800 | $952 | ↔ unresolved (sitemap-svc chain) |
| admin-portal | 0.42 | $400 | $170 | ↓ improving (was 0.85) |

Total edge loss reduced from ~$2,166/min at page to ~$1,687/min at shift end.

## Key lessons
- `ledger-svc` had **two concurrent changes** at minute 45; reverting the deploy didn't fix it — the config change (`cfg-43`) was the real cause (confirmed by the `PermissionDenied` scope error in logs and the rollback failing).
- `sitemap-svc`'s 4% error persisted after `revert_config cfg-31` — its actual cause was not identified in time (the deploy `v131` couldn't be inspected before shift end).
- `limits-svc`'s overload was internal (cpu 0.99 at normal load, healthy deps), resolved by scaling — the retry storm cleared once capacity was added.

The `partner-api` 4% loss ($952/min, the largest single contributor) remained unresolved at shift end because `sitemap-svc`'s root cause wasn't pinned down.
