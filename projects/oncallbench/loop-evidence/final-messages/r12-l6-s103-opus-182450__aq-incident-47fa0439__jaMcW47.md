I found and fixed six causes. From minute 77 to the end of the shift at minute 120, all four customer-facing services showed 0% errors, and no new faults appeared.

| Cause | What I did |
|---|---|
| **payments-svc** was overloaded: new requests rose from about 1,100 to about 3,500 a second, and retries pushed it to 12,000 a second with about 90% failing. This hit web-storefront and mobile-api. | Turned on a 90% throttle to stop the retries and scaled from 3 to 12 replicas. Lifted the throttle once the replicas were running. CPU is now about 0.6. |
| **pool-a** config cfg-44 cut `max_pods` from 400 to 40, so payments' new replicas stayed pending. | Reverted the config. The replicas then came up. |
| **dns-3** config cfg-20 made it fail about 8% of its lookups. | Reverted the config. |
| **inventory-svc** deploy v123 changed `row.get("currency", "EUR")` to `row["currency"]`, causing KeyErrors. These caused admin-portal's 4% errors through shipping-svc and ledger-svc. admin-portal earns $21,600 a minute, so this cost about $864 a minute. | Scaled from 4 to 8 replicas first, because it was running at 0.86 CPU and the rollback could have set off a retry storm. Then rolled back the deploy. |
| **pricing-svc** deploy v105 cut its call timeout tenfold, so about 60% of its requests failed and mobile-api failed with them. | Rolled back the deploy. |
| **labels-svc** config cfg-38 started at minute 55 and removed the `orders.write` permission. About 51% of its requests failed, which hit web-storefront and mobile-api. | Reverted the config. |

I also scaled experiments-svc from 4 to 6 replicas as a precaution, because it was running at 0.97 CPU. It was not failing, so this one may not have been needed.

I didn't cut the extra replicas back before finishing, so they were charged until the end of the shift:
- payments-svc: 9 extra
- inventory-svc: 4 extra
- experiments-svc: 2 extra

Reducing them would have saved a few hundred dollars, but payments-svc and inventory-svc had been close to capacity, and I judged the risk of another retry storm not worth it.
