# r16-l4-s200014-nemotron-super-023232/seed-200014__ggYTcSY

Level 4, seed 200014, nemotron-super, score as run 0.0. The agent's closing message, verbatim:

The shift is over (minute 120). Here's a summary of the incident and actions taken:

## Root Causes Identified

1. **suggest-svc** (root of web-storefront + mobile-api outages): Bad deploy `v52` at minute -9 changed the rate limiter refill to `rate * elapsed / 1000` (1000x slower), causing 429 errors and a retry storm. Also `cfg-8` (DB password rotation) may have contributed.
2. **address-svc** (root of admin-portal's new 0.77 failure): Bad config `cfg-59` at minute 52 removed `currency` from `price_fields` → `KeyError: 'currency' in price formatter`. inventory-db was healthy.
3. **flags-svc** (root of partner-api's steady 0.04): TLS handshake failures to events-queue, possibly from `cfg-30` (beta_cohort_pct: 0 → 1).

## Actions Taken

| Time | Service | Action | Result |
|------|---------|--------|--------|
| min 33 | suggest-svc | rollback v52 | Error dropped 0.94 → 0.40, but retry storm persisted |
| min 78 | suggest-svc | revert_config cfg-8 | No clear improvement (still 0.40) |
| min 114 | suggest-svc | restart | Completing at min 116, shift ended before verification |

## Actions Not Yet Applied (shift ended)

- **address-svc**: `revert_config cfg-59` — would fix admin-portal (0.77 error, $850/min revenue at stake)
- **flags-svc**: Investigate/revert `cfg-30` — would fix partner-api (0.04 error, $18,700/min revenue at stake, largest revenue impact)

## Final Edge State
- web-storefront: 0.916 error (improved from 0.991)
- mobile-api: 0.135 error (improved from 0.282)
- partner-api: 0.04 error (unfixed — highest revenue impact at $748/min lost)
- admin-portal: 0.767 error (new, unfixed — $653/min lost)

The suggest-svc restart was in progress when the shift ended; if it cleared the retry storm, web-storefront and mobile-api would have continued recovering. The two remaining unfixed issues (address-svc config, flags-svc TLS) were the highest-value targets left.
