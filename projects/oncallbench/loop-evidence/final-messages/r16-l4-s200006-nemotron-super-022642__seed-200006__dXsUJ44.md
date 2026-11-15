# r16-l4-s200006-nemotron-super-022642/seed-200006__dXsUJ44

Level 4, seed 200006, nemotron-super, score as run 0.0. The agent's closing message, verbatim:

The shift is over. Here's a summary of the incident and what was done:

## Root Causes Found & Fixed

| # | Service | Cause | Fix |
|---|---------|-------|-----|
| 1 | `payments-db` | Config `cfg-20` cut `db_pool_size` 40→4, causing pool exhaustion + retry storm | `revert_config` + `scale` 4→8 replicas |
| 2 | `identity-svc` | Deploy `v153` changed `row.get("currency","EUR")` → `row["currency"]`, causing `KeyError` | `rollback` v153 + `scale` 8→16 replicas |
| 3 | `import-svc` | Deploy `v129` changed wire schema `v2`→`v3`, causing `DecodeError` in `notifications-svc` | `rollback` v129 + `scale` 6→12 replicas |

## Causal Chains

- `payments-db` → `pricing-svc` → `thumbnails-svc`/`stock-svc` → `mobile-api`, and `thumbnails-svc` →(soft 30%) `auth-svc` → `web-storefront`/`admin-portal`
- `identity-svc` → `catalog-svc` → `web-storefront`/`mobile-api`
- `import-svc` → `notifications-svc` → `partner-api` (23300/min — largest revenue impact)

## Final State (minute 118)

| Service | Error Rate | Revenue/min |
|---------|-----------|-------------|
| `partner-api` | **0.0%** (was 4.2%) | 23300 |
| `web-storefront` | 12.7% (was 29.95%) | 350 |
| `admin-portal` | 12.7% (was 32.9%) | 400 |
| `mobile-api` | 42.5% (was 99.99%) | 700 |

All root causes were addressed. `partner-api` (the highest-revenue edge service) is fully recovered. The two retry storms (`payments-db`, `identity-svc`, `import-svc`) were broken by scaling after the underlying config/deploy fixes.
