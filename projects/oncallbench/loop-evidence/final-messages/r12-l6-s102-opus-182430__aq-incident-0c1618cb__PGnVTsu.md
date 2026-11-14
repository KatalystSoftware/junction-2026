The shift is over. All four customer-facing services were at 0% errors from minute 62 to the end, apart from a geo-svc fault that started at minute 69 and was fixed by minute 81.

**Causes found and what I did**

1. **currency-svc overloaded by retries (began about 21 minutes before the page).** Normal traffic had grown to about 3,800 requests per minute, more than its 3 replicas could handle. Failed calls were being retried, so it was taking about 13,000 per minute. This took down web-storefront and mobile-api (about 90% errors). I rejected 90% of its requests to stop the retries and asked for 10 replicas. The retries came back as soon as I lifted that limit at minute 10, so I put it back until the new capacity was ready.
2. **pool-h, the machines currency-svc runs on, couldn't start new replicas.** Config change cfg-17 had pointed new machines at a zone that doesn't exist (`eu-north-1` → `eu-north-9`). I reverted it, the extra replicas came up, and I lifted the limit at minute 42. web-storefront then went to 0% errors.
3. **dns-6 failing 8.5% of lookups** since a "health probe" config change (cfg-42) 6 minutes before the page. I reverted it, and partner-api went from 8.5% to 0%. I reverted this without first reading what the change did, so that part rests on the timing and the recovery alone.
4. **import-svc deploy v177** hard-coded its database connection pool to 4. That caused admin-portal's steady 4.2% errors, the costliest problem at about $670 a minute. Before rolling it back I raised import-svc to 14 replicas, so the 30% of requests that fail during a rollback wouldn't set off another retry pile-up. The rollback brought admin-portal to 0%, and I then set import-svc back to its normal 8.
5. **couriers-svc deploy v100** broke its rate limiter (refill divided by 1000), so it returned "429 Too Many Requests" for about 41% of calls. That left mobile-api at 41% errors after currency-svc recovered. Rolling it back fixed it by minute 62.
6. **New fault at minute 69: geo-svc config change cfg-6** switched it to an unrecognised message format (`v2` → `v3`). web-storefront and partner-api hit 74% errors. Reverting it at minute 79 cleared both by minute 81.

**Still in place:** currency-svc is running 10 replicas instead of its normal 3, at $21 a minute. Its traffic now needs about 7 replicas, and at 10 it was at 66% load. I kept the extra margin because its traffic was still growing.

I didn't act on the other alerts (catalog-svc, payments-db and checkout-svc CPU), because none of them was hurting customer-facing services.
