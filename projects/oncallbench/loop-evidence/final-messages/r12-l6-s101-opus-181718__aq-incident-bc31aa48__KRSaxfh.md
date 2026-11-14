The shift is over. From minute 92 to the end at minute 120, all four customer-facing services were at a 0% error rate. Fixing things took longer than it should have, and I made one mitigation the shift didn't need, which costs $10,000.

**What was broken and what I did**

1. **sms-svc bad deploy (from minute -8).** Deploy v156 changed the wire schema from v2 to v3. I rolled it back at minute 15. Its caller, pricing-svc, kept retrying failed calls, and that kept sms-svc overloaded after the rollback. I turned on throttling at minute 48 to stop the retry overload and turned it off at minute 57.
2. **pricing-svc overloaded by retries (from minute -25).** This is why mobile-api failed 82–98% of requests until about minute 82. I throttled it twice to stop the retry loop. The first time I lifted the throttle it went straight back into overload. That was partly because sms-svc was still failing, but mainly because pricing-svc gets about 2,900 requests per second and its normal 6 replicas only handle about 1,700. I scaled it to 10 replicas, then to 13, and it now runs at about 76% CPU. **Those 7 extra replicas are still running and cost $21 a minute.**
3. **quotes-svc bad deploy (from about minute -40).** Deploy v59 hard-coded the database connection pool size to 4. Calls from returns-svc timed out waiting for a connection, and the failures passed up through search-svc to partner-api (about 4.7% errors, around $800 a minute). I rolled it back at minute 46. The rollback set off its own retry overload, which pushed partner-api to about 55% errors until a throttle from minute 55 to 61 cleared it. partner-api has been at 0% since about minute 61.
4. **dns-8 resolver config change (minute 35).** Change cfg-22 made about 11% of lookups fail for every service behind dns-8. I reverted it at minute 54.
5. **address-svc config change (minute 47).** This caused `KeyError: 'currency'` errors and took web-storefront to about 98% errors. **First I rolled back the deploy made at the same time (v118). That was the wrong change and costs $10,000.** At minute 75 I also mis-clicked a scale to the normal replica count, which is free but held up the rollback by 4 minutes. Reverting the config change (cfg-20) fixed it at minute 91.

**What I left alone:** cart-svc has been at 99% CPU since minute -6, but no customer-facing service depends on it.

**What would have saved money:**
- Checking the infrastructure alerts sooner would have caught dns-8 earlier.
- Fixing sms-svc before lifting the first throttle on pricing-svc would have avoided the second overload.
- Scaling quotes-svc before rolling it back would probably have avoided the overload that rollback caused.
- I should have checked the address-svc config diff before rolling back its deploy.
