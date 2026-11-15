# r16-l4-s200008-nemotron-super-verda-014805/seed-200008__eAwdaWE

Level 4, seed 200008, nemotron-super-verda, score as run 0.0. The agent's closing message, verbatim:

Shift complete. Here's a summary of what was found and fixed:

**Root causes identified and mitigated:**

1. **sitemap-svc** (→ partner-api, 77% errors): Reverted `cfg-48` config change ("update allowlist" at minute -19). Fixed partner-api from 77% → 4%.

2. **profile-db** (→ risk-svc → couriers-svc → mobile-api, plus ledger-svc, giftcards-svc, sessions-svc, export-svc, all ~84%): Reverted `cfg-32` config change at minute 45 that removed `orders.write` from `token_scope`, causing "PermissionDenied" errors. Fixed mobile-api from 84% → 0% and resolved the entire cascade.

**Unresolved:**
- **wishlist-svc** (steady 4% errors → admin-portal, web-storefront, partner-api): Tried config revert (`cfg-26`, connection pool), restart, and deploy rollback (`v89`). None resolved it. The `pool.acquire()` timeout to promo-cache persists despite promo-cache being healthy.

**Final edge service error rates:**
| Service | Error Rate | Revenue/min |
|---------|-----------|-------------|
| mobile-api | 0.0% ✅ | $750 |
| partner-api | 4% | $350 |
| admin-portal | 4% | $15,600 |
| web-storefront | 4% | $550 |
