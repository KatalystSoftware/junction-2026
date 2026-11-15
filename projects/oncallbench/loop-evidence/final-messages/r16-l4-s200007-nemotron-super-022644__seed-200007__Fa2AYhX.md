# r16-l4-s200007-nemotron-super-022644/seed-200007__Fa2AYhX

Level 4, seed 200007, nemotron-super, score as run 0.0. The agent's closing message, verbatim:

The shift is complete. Here's a summary of what was found and fixed:

**Root causes identified and fixed:**

1. **loyalty-svc** — Bad config `cfg-27` set `rpc_budget_ms: 500 → 50`, causing 85% errors that cascaded to pricing-svc → limits-svc → mobile-api. Fixed with `revert_config`.

2. **export-svc** — Bad deploy `v42` reduced cache TTL by 600x (`ttl_s // 600`), causing "StaleEntry" errors that affected geo-svc → web-storefront (18500/min revenue) and partner-api. Fixed with `rollback`.

3. **catalog-svc** — Bad deploy `v51` changed `row.get("currency", "EUR")` to `row["currency"]`, causing KeyError on 94% of requests, affecting mobile-api and admin-portal. Fixed with `rollback`.

**Retry storms broken** (export-svc, loyalty-svc, catalog-svc each entered self-sustaining retry storms) using temporary `throttle` at 50%, then removed once CPU and retry_share normalized.

**Wasted mitigation:** `revert_config` on geo-svc (cfg-30) — the real cause of geo-svc's 4% error was export-svc's deploy, not geo-svc's own config.

**Final state:** All edge services at 0–0.34% error rate (web-storefront 0%, partner-api 0%, admin-portal 0%, mobile-api 0.34%).
