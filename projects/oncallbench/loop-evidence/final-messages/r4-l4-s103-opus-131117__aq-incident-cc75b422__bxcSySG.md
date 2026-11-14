# r4-l4-s103-opus-131117/aq-incident-cc75b422__bxcSySG

Level 4, seed 103, opus, score as run 0.6969, regraded 0.7187. The agent's closing message, verbatim:

The shift is over. I found and fixed three faults, and all four customer-facing services ended back at their normal 4% error rate. Admin-portal ($21.6k/min) and partner-api were never affected.

1. **payments-svc overload (already going when I was paged, minute −23).** Real traffic tripled, from about 1.1k to 3.4k requests per second, against 3 replicas. Callers retrying the failures pushed load to about 12k per second, and web-storefront and mobile-api were failing 88–95% of requests. I scaled payments-svc to 10 replicas and set a 60% throttle to break the retry loop. By minute 12 the retries were gone, so I lifted the throttle at minute 20. Payments-svc stayed at 10 replicas to the end of the shift, about $2.4k in replica cost.
2. **pricing-svc bad deploy (minute −14, about 60% errors).** Deploy v105 changed the call deadline from `budget_ms / 1000` to `budget_ms / 10000`, so calls got a tenth of their time budget. I rolled it back and it was finished at minute 22. A config change at the same minute (password reference and cache time) looked harmless, so I left it.
3. **labels-svc bad config (new fault at minute 55, about 53% errors on web-storefront and mobile-api).** Config change cfg-38 removed the `orders.write` permission. The errors spread through geo-svc, tax-svc and disputes-svc to both storefronts. I reverted the config at minute 68, and both were back to normal by minute 70. The deploy at the same minute only updated a library and added a route behind a flag, so I didn't roll it back.

**Left alone:** experiments-svc ran at about 0.97–0.99 CPU from minute −5 to the end, with almost no errors, steady traffic and no recent changes. Adding a fifth replica didn't lower the CPU, so I set it back to 4, which is free. That cost about $30 in replica time. I didn't restart it: a restart would have failed requests that callers retry, which could have tipped it over, and it would have cost $10k if it wasn't needed. Customers never saw an impact from it.

**Avoidable losses:** about 22 minutes of the payments overload after I was paged, 22 minutes of pricing errors, and about 15 minutes of the labels fault. No mitigation went to a service that didn't need it, so there was no $10k charge.
