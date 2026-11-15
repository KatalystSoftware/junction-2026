# r16-l4-s200020-nemotron-super-verda-021125/seed-200020__z8oERpY

Level 4, seed 200020, nemotron-super-verda, score as run 0.0775. The agent's closing message, verbatim:

Shift complete. All fixable root causes were mitigated; only mobile-api's 4.5% (unfixable latency mismatch: suggest-svc 211ms vs 50ms budget, driven by pricing-svc's chronic 180ms) remains for the final minutes.

**Actions taken:**
| Service | Issue | Mitigation | Result |
|---------|-------|------------|--------|
| push-svc | rate_limit 5000→50 (cfg-16) | `revert_config` | Fixed 93% errors |
| fraud-svc | OOM/bloated + retry storm | `restart` | Cleared bloat |
| push-svc | retry backlog + CPU overload | `restart` + `throttle` 60%→0 | Broke storm, recovered |
| risk-db | KeyError from cfg-11 allowlist | `rollback` v57 (no effect), then `revert_config` cfg-11 | Fixed 73% errors |
| web-storefront / admin-portal | failing via fraud-svc→risk-db | (recovered via above) | 0% errors |
| mobile-api | suggest-svc 211ms vs 50ms budget | `scale` suggest-svc 4→6 (no effect) | Unfixable — bottleneck is pricing-svc 180ms |

Edge services at shift end: web-storefront 0%, admin-portal 0%, partner-api 0%, mobile-api 4.5%.
