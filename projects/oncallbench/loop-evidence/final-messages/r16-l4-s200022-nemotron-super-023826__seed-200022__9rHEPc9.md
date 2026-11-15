# r16-l4-s200022-nemotron-super-023826/seed-200022__9rHEPc9

Level 4, seed 200022, nemotron-super, score as run 0.0. The agent's closing message, verbatim:

The shift is over. Here's a summary of the incident and actions taken:

## Incident Summary

**Two root causes were identified and mitigated:**

### 1. `profile-db` primary node failure (cascading to partner-api)
- **Symptom**: `partner-api` at 96% error, `bundles-svc` at 96% error
- **Root cause**: `profile-db` primary node unreachable ("primary node unreachable, write rejected")
- **Actions**: `failover` on profile-db (minute 45), then `scale` 4→8 replicas (minute 99) to drain the retry storm
- **Result**: profile-db fully recovered to 0.002% error at minute 105. But `bundles-svc` remained stuck at 77% due to memory bloat/OOM loop — a restart was started at minute 119 but didn't complete before shift end.

### 2. `currency-svc` bad deploy (cascading to admin-portal)
- **Symptom**: `admin-portal` at 4% error, `notifications-svc` at 4.3%
- **Root cause**: `currency-svc` deploy v39 at minute -44 caused connection pool timeouts to `promo-cache`
- **Action**: `rollback` on currency-svc (minute 46) — reverted v39, currency-svc back to 0.04% error by minute 55
- **Result**: `notifications-svc` remained at 4.4% despite healthy dependencies and a restart — the exact cause was not determined before shift end.

### 3. `emails-svc` bad config (affecting partner-api)
- **Symptom**: `emails-svc` at 76% error ("429 Too Many Requests")
- **Root cause**: Config change `cfg-52` at minute 53 slashed `rate_limit_per_s: 5000 → 50`
- **Action**: `revert_config` on emails-svc (minute 87) — rate limit restored to 5000
- **Result**: emails-svc improved from 76% → 40% but was still in a retry storm at shift end. A scale (8→12) was started at minute 120 but didn't complete.

## Final State (minute 120)

| Service | Error Rate | Revenue/min | Loss/min |
|---------|-----------|-------------|----------|
| web-storefront | 0% | $800 | $0 |
| mobile-api | 0% | $700 | $0 |
| partner-api | 94% | $850 | ~$799 |
| admin-portal | 4% | $16,800 | ~$672 |

**Total ongoing loss: ~$1,471/min** — both mitigations for the remaining issues (bundles-svc restart, emails-svc scale) were in progress when the shift ended and will complete after minute 120.
