I've ended the shift, and all four customer-facing services were at 0% errors from minute 91 to the end. I found and fixed six problems. The costliest mistake was mine: the rollback I ran on inventory-svc pushed admin-portal (the service earning $21,600/min) from 4% errors to about 50% for roughly 14 minutes.

| # | Cause | What it broke | Fix | Result |
|---|---|---|---|---|
| 1 | inventory-svc deploy v123 (minute -23) read the currency field without a default value, so pricing requests without one failed | shipping-svc → ledger-svc → admin-portal (steady 4%) and partner-api | Rolled back v123 at minute 37 | Fixed |
| 2 | That rollback drew a burst of retries that overloaded inventory-svc | admin-portal ~50% from about minute 37 to 50 | Rejected 60% of inventory-svc requests for 3 minutes so the retries stopped, then lifted it | admin-portal and partner-api at 0% by minute 51 |
| 3 | payments-svc was overloaded and stuck there by retries; no recent change caused it | web-storefront ~90%, mobile-api ~96% | Scaled from 3 to 9 replicas at minute 14 | The new replicas stayed pending until fix 4 |
| 4 | pool-a config cfg-44 cut the pool's pod limit from 400 to 40 | Blocked the payments-svc scale-up | Reverted cfg-44 at minute 42 | Replicas ready by minute 47; after a 50% throttle at minutes 56–58, payments-svc errors were near 0 by minute 62 |
| 5 | dns-3 config cfg-20 made the resolver fail about 8% of lookups | partner-api ~19% and several app services | Reverted at minute 13 | partner-api down to 4% by minute 16 |
| 6 | pricing-svc deploy v105 cut its call deadlines tenfold, so calls timed out (`DeadlineExceeded`) | mobile-api | Rolled back at minute 76 | Fixed |
| 7 | New fault at minute 55: labels-svc config cfg-38 dropped the `orders.write` permission | geo-svc → tax-svc, so web-storefront ~50% and mobile-api | Reverted at minute 89 | Everything at 0% by minute 91 |

**What I'd do differently:** inventory-svc was already close to capacity before the rollback. Turning on a partial throttle *before* rolling back would probably have prevented the retry storm on admin-portal.

**Remaining cost:** payments-svc is still at 9 replicas instead of 3, about $18/min. Its CPU at 9 replicas was 0.78, so dropping to 8 would have put it near capacity again.

I don't think any of the fixes was spent on a service that didn't need it. I checked the diff before every config revert except dns-3 and pool-a; dns-3 was reverted on timing alone, though partner-api recovered right after. Both rollbacks were checked against their diffs first.
