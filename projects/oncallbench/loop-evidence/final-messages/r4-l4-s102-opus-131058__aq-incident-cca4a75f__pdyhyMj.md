# r4-l4-s102-opus-131058/aq-incident-cca4a75f__pdyhyMj

Level 4, seed 102, opus, score as run 0.653, regraded 0.659. The agent's closing message, verbatim:

The shift is over, and all four customer-facing services were at 0% errors for the last 37 minutes. Four separate problems caused customer errors. I fixed all of them, but the first fix on couriers-svc was the wrong one.

1. **currency-svc was overloaded (minute −21 to about 20).** Its normal traffic had nearly tripled, to about 3,700 requests per second against capacity for about 1,700. Failed calls were retried, which pushed it to about 13,000 requests per second. web-storefront (87% errors) and mobile-api (92%) went down through it. Rejecting 90% of its traffic for a few minutes on its own didn't fix it, because normal traffic alone was still over capacity. I added replicas (3 → 9) and briefly rejected traffic again to clear the retries, and it recovered. Its traffic is still growing, so I left it at 9 replicas; that costs $18 a minute.

2. **couriers-svc's rate limiter was rejecting most requests (mobile-api at 41% errors, minute −20 to about 59).** It had a config change and a deploy at the same minute. I reverted the config change first without reading what it did, and that didn't help, so it will probably be charged as a $10k wasted mitigation. The actual cause was deploy v100: a bug divides the rate limiter's refill rate by 1000. Rolling it back fixed it.

3. **import-svc's connection pool was cut to 4 (admin-portal at about 4.4% errors, minute −28 to about 59).** Deploy v177 hard-coded the pool size to 4, so admin-portal's calls timed out. admin-portal earns the most ($15,900/min), so this was the costliest problem. Before rolling back, I added replicas (8 → 14) so that the 30% of requests that fail during a rollback could be retried without overloading it. The rollback fixed it and I set it back to its normal 8 replicas.

4. **A new problem on geo-svc started during the shift (minute 69 to 82).** web-storefront and partner-api hit 74% errors. Config change cfg-6 switched the message format it reads from v2 to v3, so it couldn't decode requests. Reverting the config fixed it.

One possible risk is still open: catalog-svc has been at about 98% CPU since minute −9. It wasn't failing requests and its callers don't retry, so I didn't touch it. It's worth watching before it tips over.
