# r10-l4-s103-opus-153718/aq-incident-cc75b422__uvjVqe3

Level 4, seed 103, opus, score as run 0.5944, regraded 0.6129. The agent's closing message, verbatim:

The shift is over. All four customer-facing services were at 0% errors from minute 71 to the end, but one of my fixes caused a costly spike along the way.

| # | Cause | Customer impact | Fix | Back to 0% errors |
|---|---|---|---|---|
| 1 | Traffic to `payments-svc` tripled at minute −23 and set off a retry storm. Load reached about 12k rps on 3 replicas. | web-storefront and mobile-api errors around 88–95% | Scaled to 9 replicas and briefly throttled 60% of requests to stop the retries, then lifted it. CPU settled around 0.8. | ~min 23 for web; mobile was also hit by fault 3 |
| 2 | Bad deploy `v123` on `inventory-svc` (minute −23): `row["currency"]` lost its `"EUR"` default and threw a KeyError. The errors came up through `shipping-svc` and `ledger-svc`. | admin-portal and partner-api at 4% | Rolled back `v123` | min 24 |
| 3 | Bad deploy `v105` on `pricing-svc` (minute −14): the request deadline became 10× too short. | mobile-api | Rolled back `v105` | min 38 |
| 4 | New fault: config change `cfg-38` on `labels-svc` at minute 55 removed the `orders.write` scope. The errors came up through `geo-svc` to `tax-svc` and `disputes-svc`. | web-storefront and mobile-api at 51% | Reverted the config | min 71 |

**My mistake:** `inventory-svc` was already at about 86% CPU. While the rollback was failing 30% of its requests, callers retried them and overloaded it. That pushed admin-portal from 4% to about 55% errors from roughly minute 17 to 23. admin-portal earns $21,600 a minute, so this probably cost around $70k, the largest single loss of the shift. A 50% throttle on `inventory-svc` stopped the retries, and everything cleared once the rollback finished. I should have checked its headroom and scaled or throttled it before rolling back.

**Left in place:**
- `payments-svc` still runs 9 replicas instead of 3. That costs $18 a minute, which is worth it because the higher traffic level never went down.
- `experiments-svc` kept a CPU alert all shift. Nothing customers used depended on it, so I left it alone.

No throttles were on at the end, and I applied no mitigations to services that didn't need them.
