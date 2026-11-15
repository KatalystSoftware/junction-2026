# r16-l4-s200007-nemotron-super-022646/seed-200007__eRpezVt

Level 4, seed 200007, nemotron-super, score as run 0.0. The agent's closing message, verbatim:

The shift has ended automatically at minute 120.

## Incident Summary

**Root causes identified (too late for some):**

1. **loyalty-svc** — config `cfg-27` changed `rpc_budget_ms: 500→50` at minute -20, causing 85% error rate. ✅ **Fixed** via `revert_config` + scaled to 8 replicas to break the retry storm. Recovered to ~0%.

2. **export-svc** — deploy `v42` changed cache TTL from `now + ttl_s` to `now + ttl_s // 600` at minute -15, causing StaleEntry errors. This broke geo-svc (→ web-storefront at 4%) and partner-api (4%). ❌ Not fixed — rollback was deemed too costly with limited time remaining.

3. **catalog-svc** — deploy `v51` "weekly release" at minute 61 introduced a `KeyError: 'currency'` in the price formatter, causing 94% error. This broke admin-portal (94%) and mobile-api (96%, cascading from both catalog-svc and the recovering loyalty-svc chain). ❌ Not detected until the final minutes.

**Final edge service state at shift end:**
| Service | Error Rate | Revenue/min | Lost/min |
|---------|-----------|-------------|----------|
| web-storefront | 4% | $18,500 | $740 |
| mobile-api | 96% | $700 | $673 |
| partner-api | 4% | $450 | $18 |
| admin-portal | 94% | $450 | $423 |

The two config reverts (loyalty-svc, export-svc) and one scale (loyalty-svc) were applied, but the export-svc deploy rollback and catalog-svc deploy rollback were not executed in time.
