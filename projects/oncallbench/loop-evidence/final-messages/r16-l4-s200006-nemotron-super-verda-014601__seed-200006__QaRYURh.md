# r16-l4-s200006-nemotron-super-verda-014601/seed-200006__QaRYURh

Level 4, seed 200006, nemotron-super-verda, score as run 0.0. The agent's closing message, verbatim:

The shift is over. Here's the incident summary:

## Root causes found & fixed

| # | Service | Root cause | Fix | Time |
|---|---------|-----------|-----|------|
| 1 | `payments-db` | Config `cfg-20` cut `db_pool_size 40→4` | `revert_config` | min 35 |
| 2 | `import-svc` | Deploy `v129` changed wire schema `v2→v3` (DecodeError) | `rollback v129` | min 83 |
| 3 | `identity-svc` | Deploy `v153` `row["currency"]` KeyError | `rollback v153` | min 90 |

## Retry storms broken with `scale`
After the config/build fixes, `payments-db`, `import-svc`, and `identity-svc` were stuck in retry storms (cpu 0.99, retry_share ~0.55–0.74, error ~0.4) and not self-recovering. Scaling each to 2× normal replicas gave headroom, cleared the backlog, and drove all three to ~0.002 error.

- `payments-db` 4→8 (min 91)
- `import-svc` 6→12 (min 106)
- `identity-svc` 8→16 (min 107)

## Misstep
`rollback notifications-svc (v55)` at min 36 was wrong — its deps were healthy; the real root was `import-svc` (a caller sees import-svc's bad responses). That was a wasted mitigation ($10,000). The logs (`DecodeError: unknown wire schema 'v3'`) revealed the true cause.

## Final state (shift end)
- `partner-api`: **0.0** — the $23,300/min bleed stopped
- All root-cause and downstream services recovered to ~0.002 error
- Edge services (`web-storefront`, `mobile-api`, `admin-portal`) were catching up as downstream storms cleared

All customer-facing services' dependencies are healthy; remaining edge errors in the final minutes were residual drain from the cleared storms.
