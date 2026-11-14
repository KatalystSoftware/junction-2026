The shift is over, and all four customer-facing services were at 0% errors from minute 83 to the end at 120. I found and fixed five separate causes. Fixing one of them set off a second outage on the highest-earning service, and that was my mistake.

**What I found and did:**

1. **currency-svc retry storm** (since minute -21). Traffic ran at about 13k requests per second against capacity for about 1.7k. Most of it was retries, and it was taking down web-storefront and mobile-api. Normal traffic had also grown to about 3.8k requests per second, which is more than its 3 replicas can serve. I throttled it to 90% to stop the retries and scaled it from 3 to 9 replicas. I lifted the throttle at minute 55, once the new replicas were up; CPU is now about 0.72 with almost no errors.
2. **dns-6 config `cfg-42`, "adjust health probe"** (minute -6). This lookup service was failing about 8.7% of lookups, which caused partner-api's 8.5% errors. I reverted the config and partner-api dropped to 0%.
3. **import-svc deploy v177** (minute -28). It hard-coded a connection pool of 4, so admin-portal's calls to it timed out (4.2% errors). I rolled it back.
   - **My mistake:** the rollback fails 30% of requests while it runs, and import-svc was already near capacity. That started a retry storm and pushed admin-portal to about 52% errors around minutes 35–43. At $15,900/min, that cost roughly $8k/min for about 8 minutes, the most expensive part of the shift. Throttling import-svc for one minute (60%) ended it. I should have throttled before starting the rollback.
4. **pool-h config `cfg-17`.** It pointed the machine pool at a zone that doesn't exist (`eu-north-9`), so currency-svc's new replicas couldn't start. Reverting it got all 9 replicas running by minute 54.
5. **couriers-svc deploy v100** (minute -20). It broke the rate limiter: tokens refilled 1000× too slowly, so couriers-svc rejected requests (429s). mobile-api was still at 41% errors after currency recovered. I rolled it back at minute 66 and mobile-api went to 0%.
6. **geo-svc config `cfg-6`**, a new fault at minute 69. It switched the wire schema from v2 to v3, putting web-storefront and partner-api at about 74% errors. I reverted only the config; the deploy that went out with it looked harmless. Both were back to 0% by minute 83.

**Left alone on purpose:**
- **catalog-svc** has a CPU alert at 0.97, but its errors stayed normal, so I didn't touch it.
- **currency-svc** stays at 9 replicas, about $18/min. Its traffic is genuinely higher now, so going back to 3 would overload it again.

I didn't use any mitigation on a service that didn't need it.
