# r3-l3-s103-opus-113139/aq-incident-5b188273__bWKV3Wi

Level 3, seed 103, opus, score as run 0.9309. The agent's closing message, verbatim:

The shift is over, and all four customer-facing services were at 0% errors from minute 69 to the end. I found three separate causes and fixed each one, and no fix was applied to a service that didn't need it.

| # | Started | Cause | Fix | Result |
|---|---|---|---|---|
| 1 | min -23 | **payments-svc** was overloaded: traffic tripled (about 1.1k to 3.3k requests/sec) with no deploy behind it. CPU sat at 99% and about 47% of requests failed. Web and mobile were hit. | Scaled from 3 to 10 replicas at min 7 | Errors near 0 and CPU about 0.57 from min 10 |
| 2 | min -14 | **pricing-svc** deploy v105 cut its timeout for calls to other services by 10x (`budget_ms / 10000`). It failed about 60% of requests, which hit mobile. | Rolled back v105 at min 14 | Fixed by min 19 |
| 3 | min -23 | **inventory-svc** deploy v123 changed `row.get("currency","EUR")` to `row["currency"]`, which throws a KeyError when a row has no currency. The errors spread through shipping-svc and ledger-svc. This put admin-portal, partner-api and web at 4% errors. | Rolled back v123 at min 29 | All four services at 0% by min 34 |
| 4 (started during the shift) | min 55 | **labels-svc** config change cfg-38 reduced `token_scope` from `[orders.read, orders.write]` to `[orders.read]`. About 51% of requests failed, spreading through geo-svc, tax-svc and disputes-svc to web and mobile. | Reverted cfg-38 at min 67 | Fixed by min 69 |

Things I left alone on purpose:
- **experiments-svc** had a high-CPU alert all shift, but its error rate stayed around 0.3% and its traffic was flat. It wasn't causing anything.
- **Other recent changes** were not the cause: the pricing-svc cache TTL change, the inventory-svc rate-limit change and the labels-svc security patch deploy v134.

Where the cost came from:
- **Admin-portal's 4% errors** were the biggest cost. That service earns $16,200 a minute, so 4% is about $650 a minute, more than web and mobile's much higher error rates put together. It took me until minute 29 to trace it to inventory-svc, and the delay was mostly spent reading changes and logs one at a time.
- **The inventory-svc rollback** made 30% of requests fail on all four services for about 5 minutes, including admin-portal. That cost roughly $25k, but there was no faster way to get rid of a bad build.
- **The 7 extra payments-svc replicas** cost about $2.3k for the shift. I kept 10 because traffic was still rising. 8 would probably have been enough and saved about $500.

I don't know the final score; the simulator works it out when it replays the shift.
