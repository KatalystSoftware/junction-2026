# r16-l4-s200003-nemotron-super-verda-014314/seed-200003__bREC99q

Level 4, seed 200003, nemotron-super-verda, score as run 0.0. The agent's closing message, verbatim:

The shift has ended (minute 120). Here's the incident summary:

## Root causes & actions

| # | Service | Root cause | Fix | Result |
|---|---------|-----------|-----|--------|
| 1 | `bundles-svc` | Deploy v37 (min −14) changed `expires = now + ttl_s // 600` → entries expired too fast → `StaleEntry` | `rollback` (min 60–66) | `search-svc` → `admin-portal` recovered to **0.0%** (biggest revenue save, $19,400/min) |
| 2 | `import-svc` | OOM / bloated process (heap 95%, OOM kills) | `restart` (min 61–64) | Recovered to 0.0013; broke `geo-svc`→`sessions-svc` chain |
| 3 | `risk-svc` | New fault at min 59: deploy v17 shrank DB pool `Pool(size=4)` → `pool.acquire` timeouts → retry storm | `rollback` (min 103–109) | `geo-svc`→`sessions-svc` recovering (0.86→0.42) at shift end |
| 4 | `seo-svc` | Retry-storm overload (intrinsically healthy at normal load) | `scale` to 12 (min 62–66) | Error dropped 0.87→0.68 but storm persisted; still driving `web-storefront` |

## Edge state at shift end (min 115)
- `admin-portal`: **0.0%** ✓
- `mobile-api`: 0.0% ✓
- `partner-api`: 0.43% (recovering from risk-svc chain)
- `web-storefront`: 0.82% (seo-svc storm + sessions-svc tail)

## What remained
The `seo-svc` retry storm never fully broke (scale to 12 helped but wasn't enough to overcome the self-sustaining retry load), and `risk-svc`/``geo-svc`/``sessions-svc` were still draining when the shift ended. `web-storefront` and `partner-api` were the remaining losses.

Key lesson: `rollback`/`revert_config` remove the cause (permanent fix), while `restart`/`scale` only address symptoms — the retry storms on `bundles-svc`, `seo-svc`, and `risk-svc` needed their root bad changes reverted plus time (or more capacity) to drain.
