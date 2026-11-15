# r16-l4-s200010-nemotron-super-023106/seed-200010__VuYWPu8

Level 4, seed 200010, nemotron-super, score as run 0.0. The agent's closing message, verbatim:

The shift is over (minute 120). Here's the incident summary:

## Root causes found & actions

1. **mobile-api → vouchers-svc → bundles-svc** (retry storm): bundles-svc overload from config `cfg-42` (minute -20). Fixed with `revert_config` on bundles-svc; then broke the downstream retry storms on bundles-svc and vouchers-svc with 90% throttles (rejected traffic isn't retried). Both recovered.

2. **mobile-api → seo-svc → inventory-db** (retry storm): inventory-db overload from config `cfg-6` (`rate_limit_per_s: 5000 → 50` at minute 61). Fixed with `revert_config` on inventory-db, then broke its retry storm with a 90% throttle.

3. **web-storefront / partner-api / catalog-svc** (~4.4%): rooted in **labels-svc** at a steady 4.5% with healthy dependencies and no config change. I rolled back labels-svc deploys `v41` and `v40` — neither helped (2 wasted mitigations, $20,000). The remaining deploy `v39` was never reverted before the shift ended.

## End state (minute 120)
- **web-storefront**: 0.044 error ($11,600/min) — unresolved
- **mobile-api**: 0.9701 error ($600/min) — still throttled via inventory-db (throttle still on at 90% when time ran out)
- **partner-api**: 0.044 error ($300/min) — unresolved
- **admin-portal**: healthy

The labels-svc 4.5% chain was the largest unresolved cost, and the inventory-db throttle was still active at shift end, keeping mobile-api elevated.
