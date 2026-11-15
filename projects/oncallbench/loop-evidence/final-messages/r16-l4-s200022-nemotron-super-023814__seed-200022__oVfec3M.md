# r16-l4-s200022-nemotron-super-023814/seed-200022__oVfec3M

Level 4, seed 200022, nemotron-super, score as run 0.0. The agent's closing message, verbatim:

The shift is over and no further actions are possible. Here's the incident summary:

## Root causes found & mitigations applied

| # | Chain (edge → root) | Root cause | Mitigation | Result |
|---|---|---|---|---|
| 1 | partner-api ← bundles-svc ← **profile-db** | primary node unreachable (data service) | `failover` profile-db, then `scale` to 8 (broke retry storm) | profile-db 0.82 → 0.004 |
| 2 | partner-api ← **emails-svc** | bad config `cfg-52` "tune connection pool" (minute 53) causing pool/rate-limit storm | `revert_config` emails-svc | emails-svc 0.55 → 0.002 |
| 3 | partner-api ← **bundles-svc** | retry storm stuck after profile-db fixed | `scale` bundles-svc to 12 | 0.77 → 0.52 (not fully cleared by shift end) |
| 4 | admin-portal ← notifications-svc ← **currency-svc** | bad deploy (minute -44) | *none* — `rollback` would cost ~$30k (hard-dep 30% fail) with <5 min left, net negative | admin-portal stayed at 0.04 |

## Final state (minute 120)
- **web-storefront**: 0.0 (healthy)
- **mobile-api**: 0.0 (healthy)
- **partner-api**: 0.52 (was 0.96 for most of the shift)
- **admin-portal**: 0.04 (steady, unaffordable to fix late in shift)

## Key judgment calls
- **profile-db failover** fixed the primary, but the retry storm needed `scale` to break — failover alone left it at 0.40 error / cpu 0.99.
- **emails-svc** storm was caused by a config change, not a deploy — `revert_config` (no impact) was the right, cheap fix; `scale` alone hadn't broken it.
- **currency-svc / admin-portal**: deliberately left alone. Rolling back would fail 30% of admin-portal's traffic for 6 minutes (~$30k lost) with only minutes to recoup — worse than the steady 4% (~$672/min).

Biggest avoided cost: partner-api dropping from 96% to 52% errors, and emails-svc fully recovering.
