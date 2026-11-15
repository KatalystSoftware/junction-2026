# r16-l4-s200019-nemotron-lightning-015011/seed-200019__C5kPKrn

Level 4, seed 200019, nemotron-lightning, score as run 0.0. The agent's closing message, verbatim:

**Incident Summary**

Two independent fault cascades occurred during the 120-minute shift:

**Incident 1** (~minute -12): currency-svc deploy/config → auth-svc → mobile-api + admin-portal
- Mitigation: `ops_revert_config` on currency-svc at minute 0
- Result: currency-svc, auth-svc, admin-portal recovered from ~0.91 to ~0.86 error_rate
- mobile-api remained severe at ~0.995

**Incident 2** (minute 48): giftcards-svc deploy+config → web-storefront + promotions-svc
- Root cause: deploy "dependency bump" removed `row.get("currency","EUR")` default; config rotated vault creds
- Mitigation: `ops_revert_config` at minute 109 (ineffective - code change remained); then `ops_rollback` at minute 119 (shift ended before take effect at minute 124)
- web-storefront remained broken at ~0.9655, promotions-svc at ~0.9506

**Final state at minute 120:**
| Service | Error Rate | Revenue/Min | Status |
|---------|-----------|-------------|--------|
| web-storefront | 0.9655 | $400 | Broken (since min 48) |
| mobile-api | 0.9954 | $800 | Broken (entire shift) |
| partner-api | 0.04 | $29100 | Slightly degraded |
| admin-portal | 0.8622 | $550 | Recovered (from incident 1) |

**Actions taken:** 3 mitigations (2 `revert_config`, 1 `rollback`). The giftcards-svc rollback was started too late (minute 119) to take effect before the shift ended at minute 120.

The key lesson: a second independent fault started at minute 48 that wasn't related to the first cascade. Checking all alert tiers and service metrics regularly would have identified the giftcards-svc issue sooner.
