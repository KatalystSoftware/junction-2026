# r16-l4-s200003-nemotron-super-022630/seed-200003__ZPvM5GV

Level 4, seed 200003, nemotron-super, score as run 0.0. The agent's closing message, verbatim:

Shift ending at minute 120. Here's the incident summary:

## Root causes found & fixed

| Fault | Root cause | Fix | Result |
|-------|-----------|-----|--------|
| `import-svc` OOM/memory leak (build `v144`) | Leaky build | `rollback v144` | Fixed `geo-svc`→`sessions-svc` chain |
| `seo-svc` overload (retry storm, cpu 0.99) | Stuck at capacity | `scale 6→24` | Recovered (cpu 0.54) |
| `bundles-svc` cache TTL bug (build `v37`: `ttl_s // 600`) | Bad build causing `StaleEntry` | `rollback v37` | Fixed `search-svc`→`admin-portal` |
| `bundles-svc` overload (2nd wave) | Retry storm | `scale 8→16` | Recovered |
| `risk-svc` overload (2nd wave, pool exhaustion) | Retry storm exhausting connection pool | `scale 4→12` | Partial (cpu 0.99→0.73, but stuck at 0.61 — needed more scale, no time left) |

## Wasted mitigation
- `rollback search-svc v113` — wrong cause (search-svc's errors came from `bundles-svc`, not its own deploy). $10,000 wasted.

## Final state (minute 119/120)
- `admin-portal`: **0.0** ✓ (was the biggest revenue loss, $834/min)
- `mobile-api`: 0.0 ✓
- `web-storefront`: 0.61 ✗ (still behind stuck `risk-svc`→`sessions-svc` chain)
- `partner-api`: 0.61 ✗ (same chain)

`risk-svc` needed a larger scale to clear connection-pool exhaustion from its retry storm, but the shift ended before it could complete. `web-storefront` and `partner-api` remain degraded (~$1,000/min) as the shift closes.
