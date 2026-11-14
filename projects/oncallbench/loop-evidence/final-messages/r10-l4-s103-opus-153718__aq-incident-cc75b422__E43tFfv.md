# r10-l4-s103-opus-153718/aq-incident-cc75b422__E43tFfv

Level 4, seed 103, opus, score as run 0.1722, regraded 0.1776. The agent's closing message, verbatim:

The shift is over, and all four customer-facing services were at 0% errors from minute 75 to the end (I last checked at minute 114). There were four separate causes. One outage, from minute 40 to about 51, was a side effect of my own inventory-svc rollback.

1. **payments-svc overload (web-storefront and mobile-api, from minute −23):** Traffic roughly tripled (about 1,100 to 3,300 requests per second) with only 3 replicas. Callers' retries then pushed the load to about 12,000 per second. I scaled it to 10 replicas and turned on a 60% throttle at minute 8 to stop the retries. The throttle stayed on until minute 22, about 10 minutes longer than it needed to, so those two services kept losing about 60% of requests during that time. After lifting it, payments-svc ran at about 70% CPU.
2. **pricing-svc bad deploy v105 (mobile-api, from minute −14):** It made request deadlines 10× too short (`budget_ms / 10000`). I rolled it back at minute 19. Its config change from the same minute (cfg-23) was harmless, so I left it alone.
3. **inventory-svc bad deploy v123 (admin-portal and partner-api at 4%, from minute −23):** The deploy crashes when a row has no `currency` field; before, it defaulted to EUR. The failures reached admin-portal through shipping-svc and ledger-svc. This was the costliest fault, because admin-portal earns $21,600 a minute. I started the rollback at minute 40.
   - **The outage I caused:** inventory-svc was already running at 87% CPU. The rollback fails 30% of requests while it runs, and callers retried those failures until the service was overloaded. All four edge services sat at about 55% errors from minute 40 to about 51. I broke the retry loop with a 50% throttle, scaled it to 6 replicas, and lifted the throttle at minute 51. I should have added replicas before starting that rollback.
4. **labels-svc config change cfg-38 (new fault at minute 55; web-storefront and mobile-api at 51%):** The change removed the `orders.write` permission, so geo-svc's calls to labels-svc were refused. tax-svc and disputes-svc depend on geo-svc, which is how it reached customers. I reverted it at minute 74, so this fault ran for about 19 minutes before I fixed it.

No action went to a service that didn't need it, and no throttles are on. Two scale-ups stayed in place to the end because cutting back looked risky:
- **payments-svc:** 10 replicas instead of 3, about $21 a minute.
- **inventory-svc:** 6 replicas instead of 4, about $6 a minute.

experiments-svc ran at about 97% CPU the whole shift. It never caused customer errors, so I didn't touch it.
