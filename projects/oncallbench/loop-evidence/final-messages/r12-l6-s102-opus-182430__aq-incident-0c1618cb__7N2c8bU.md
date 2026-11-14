The shift is over. All four customer-facing services were at a 0% error rate from minute 81 to minute 120. I found and fixed five causes, plus one overload. Two services are left with extra replicas, and I didn't find what started the currency-svc overload.

| # | Cause | Who it hit | Fix | When it cleared |
|---|---|---|---|---|
| 1 | A config change to the `dns-6` resolver at minute −6 ("adjust health probe", cfg-42) made it fail about 8.6% of lookups | partner-api | Reverted the config | Minute 12 |
| 2 | `currency-svc` was overloaded: its traffic rose about 10× from retries, mostly retries of retries. Traffic without retries was about 3× its pre-incident level | web-storefront and mobile-api (through limits-svc and couriers-svc) | Throttled it to 80% to stop the retries, then scaled it to 12 replicas | Minute 42 |
| 3 | A config change to the `pool-h` node pool at minute −39 (cfg-17) pointed new replicas at a zone that doesn't exist (`eu-north-9`), so new replicas there never became ready | It blocked the scale-ups of currency-svc and import-svc | Reverted the config | Pending replicas were ready by minute 38 |
| 4 | An `import-svc` deploy (v177) hardcoded its database connection pool to 4, so callers timed out | admin-portal, steady at 4.2% but worth $15,900/min | Scaled import-svc from 8 to 12 replicas first, because it was at 88% CPU and the rollback could have set off a retry storm. Then rolled it back | Minute 49 |
| 5 | A `couriers-svc` deploy (v100) broke its rate limiter: the refill rate was divided by 1000, so requests got "429 Too Many Requests" | mobile-api | Rolled it back | Minute 54 |
| 6 | New during the shift: a `geo-svc` config change at minute 69 (cfg-6) switched it to wire schema v3, which it couldn't decode | web-storefront and partner-api, 74% errors | Reverted the config | Minute 81 |

Costs and loose ends:
- **Extra replicas:** currency-svc ended at 9 (normal is 3). After the fix it was at 55% CPU on 12 replicas, so I brought it down to 9 to keep headroom for retries. import-svc stayed at 12 (normal is 8) for the whole shift as cheap protection for admin-portal. Together that's about $30 a minute.
- **Rollback disruption:** the import-svc rollback briefly pushed admin-portal to about 33% errors while it ran, from about minute 39 to 44.
- **Throttle cost:** I left the currency-svc throttle at 80% from minute 12 to 40 while waiting for the new replicas. That throttle alone was failing about 80% of web-storefront's requests and most of mobile-api's over that time.
- **Unexplained trigger:** something sent currency-svc into overload at about minute −20, but I didn't find what. It didn't come back during the shift.
- **Wasted mitigations:** none. Every revert and rollback was matched to a specific change I had checked with `get_diff`.
