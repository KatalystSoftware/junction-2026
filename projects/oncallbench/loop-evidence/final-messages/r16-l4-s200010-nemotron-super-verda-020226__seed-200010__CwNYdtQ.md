# r16-l4-s200010-nemotron-super-verda-020226/seed-200010__CwNYdtQ

Level 4, seed 200010, nemotron-super-verda, score as run 0.0. The agent's closing message, verbatim:

The shift is over. Here's my incident summary:

## Root Causes Found

| Service | Problem | Change | Fix Needed |
|---------|---------|--------|------------|
| **inventory-db** (data) | Rate limit cut 100x (`5000 → 50`), 82% errors, 99% CPU | `cfg-6` at minute 61 | `revert_config cfg-6` (not applied) |
| **ledger-db** (data) | TTL divided by 600, "StaleEntry" errors | `v95` at minute -25 | `rollback v95` (not applied) |
| **vouchers-svc** (app) | KeyError from `row["currency"]` missing key | `v56` deploy at -25 | `rollback v56` ✅ applied |
| **bundles-svc** (app) | `token_scope` write permission removed | `cfg-42` config at -20 | `revert_config cfg-42` ✅ applied |

## Cascade Chains

- **inventory-db** → seo-svc (82% errors) → mobile-api (89% errors, $600/min revenue)
- **ledger-db** → labels-svc (4.5%) → audit-svc (4.5%) → catalog-svc (4.5%) → web-storefront (4.4%, $11,600/min) & partner-api (4.4%, $300/min)

## What Was Applied

- `rollback vouchers-svc v56` — reduced vouchers-svc from 98% → 41% errors (still recovering from retry overload)
- `revert_config bundles-svc cfg-42` — reduced bundles-svc from 95% → 41% errors (still overloaded at 99% CPU)
- `rollback labels-svc v41` — **wasted** ($10,000) — v41 wasn't the cause; ledger-db was
- `rollback audit-svc v79` — **wasted** ($10,000) — v79 wasn't the cause; ledger-db was through labels-svc

## What Was Missed (Shift Ended Before Applying)

- `revert_config inventory-db cfg-6` — would restore rate limit to 5000/s, fixing seo-svc and mobile-api
- `rollback ledger-db v95` — would restore TTL calculation, fixing the 4.4% error chain on web-storefront and partner-api

## Final State

- web-storefront: 4.4% errors ($11,600/min revenue) — still broken
- mobile-api: 89% errors ($600/min revenue) — still broken
- partner-api: 4.4% errors ($300/min revenue) — still broken
- admin-portal: healthy

The two most impactful fixes (inventory-db rate limit, ledger-db TTL) were identified but not applied before the shift ended, plus two wasted mitigations on labels-svc and audit-svc.
