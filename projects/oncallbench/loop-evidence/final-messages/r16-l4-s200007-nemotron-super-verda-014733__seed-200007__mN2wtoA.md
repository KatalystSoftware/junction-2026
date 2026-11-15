# r16-l4-s200007-nemotron-super-verda-014733/seed-200007__mN2wtoA

Level 4, seed 200007, nemotron-super-verda, score as run 0.0. The agent's closing message, verbatim:

Shift complete. 

**Result:** The shift ended at minute 120. I mitigated the major revenue-losing faults:

- **`loyalty-svc`** (root of mobile-api surge): reverted bad config `cfg-27` (`rpc_budget_ms 500→50`) — fully recovered.
- **`catalog-svc`** (root of mobile-api + admin-portal surge from minute 61): rolled back bad deploy `v51` (`KeyError: 'currency'`), then scaled to break the retry storm — admin-portal recovered to 0.0, mobile-api dropped from 0.96 to 0.34.
- **`geo-svc`** (web-storefront 0.04): config revert, rollback, and restart all failed; correctly left alone since a restart's 3-minute 50% failure would cost more than the remaining shift could save.

Left unresolved: `web-storefront` (0.04, geo-svc), `mobile-api` residual 0.34 (pricing/limits tail), `partner-api` 0.04 (minor).
