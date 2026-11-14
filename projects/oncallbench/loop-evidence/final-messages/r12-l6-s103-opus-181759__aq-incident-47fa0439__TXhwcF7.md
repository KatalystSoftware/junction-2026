The shift is over. All four customer-facing services were at 0% errors from minute 80 to the end at minute 120, with no throttles on and no replicas pending.

I found and fixed six problems:

| # | Cause | Effect | Fix |
|---|---|---|---|
| 1 | Config change cfg-20 on the shared resolver `dns-3` at minute -14 made it fail about 8% of lookups. | Every service that looks up its backends through `dns-3` failed that share of its requests. | Reverted cfg-20 at minute 13. |
| 2 | `payments-svc` was stuck in a retry storm: 12k requests/min, 72% of them retries, 90% errors. Even its normal traffic is more than 3 replicas can handle. | `web-storefront` and `mobile-api` were failing over 90%. | Scaled it to 12 replicas, then back down to 10 once it had recovered. |
| 3 | Config change cfg-44 on `pool-a` (the machines `payments-svc` runs on) cut `max_pods` from 400 to 40. | The new `payments-svc` replicas couldn't start. | Reverted cfg-44. The replicas came up and the retry storm drained. |
| 4 | Deploy v105 of `pricing-svc` divided the call deadline by 10,000 instead of 1,000. | `pricing-svc` failed about 60% of requests, which hit `mobile-api`. | Rolled back v105. |
| 5 | Deploy v123 of `inventory-svc` changed `row.get("currency", "EUR")` to `row["currency"]`, so rows without a currency threw a KeyError. | Steady 4% errors on all four edge services through shipping and ledger. This was the most expensive fault, because `admin-portal` earns $21.6k/min. | Rolled back v123. |
| 6 | Config change cfg-38 on `labels-svc` at minute 55 removed the `orders.write` permission. This is a new fault that started during the shift. | `geo-svc` calls failed, which broke `tax-svc` and `disputes-svc`, so `web-storefront` and `mobile-api` were at 51% errors. | Reverted cfg-38 at minute 78. |

My `inventory-svc` rollback made one problem worse for a while. The rollback fails 30% of requests while it runs, and callers retry those, so `inventory-svc` overloaded. From about minute 54 to 60, all four edge services were failing at 50–75%. I stopped it by throttling `inventory-svc` to 50% for about three minutes and adding two replicas (4 → 6).

Two services were left above their normal replica count when I finished, and they cost money every minute:
- **`payments-svc`: 10 replicas (normal is 3).** It needs about 7 to carry its current traffic.
- **`inventory-svc`: 6 replicas (normal is 4).** I kept the extra two because it normally runs at about 85% CPU.

I don't think any mitigation went to a service that didn't need it. I read the change itself before each config revert and the two rollbacks.
