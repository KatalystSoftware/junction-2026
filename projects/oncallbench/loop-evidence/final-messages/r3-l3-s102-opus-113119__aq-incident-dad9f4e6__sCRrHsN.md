# r3-l3-s102-opus-113119/aq-incident-dad9f4e6__sCRrHsN

Level 3, seed 102, opus, score as run 0.9334. The agent's closing message, verbatim:

I found and fixed four separate faults. All four edge services were at 0% errors for the last ~37 minutes of the shift, and I ended it at minute 120.

1. **currency-svc was overloaded.** Traffic had nearly tripled, from about 1,285 to 3,600 requests per second, with CPU at 99% and 42% of requests failing since minute -21. That broke limits-svc and couriers-svc, and through them web-storefront and mobile-api. I scaled it from 3 to 9 replicas at minute 7; the extra replicas cost $3 each per minute until the end of the shift. web-storefront was back to 0% by minute 18. I never re-checked currency-svc's own metrics after the scale, but its alert was gone by minute 35.
2. **import-svc had a bad deploy, v177.** It hard-coded the database connection pool to 4, so admin-portal's calls to it timed out (about 4% errors on the highest-revenue service, roughly $500/min). I rolled it back at minute 18; admin-portal was at 0% by minute 27.
3. **couriers-svc had a bad deploy, v100.** It broke the rate limiter's refill maths (divided by 1000), so callers got "429 bucket empty" errors and mobile-api lost about 60% of its requests. I rolled it back at minute 27; mobile-api was at 0% by minute 33. The config change made around the same time (cfg-43) only raised the burst allowance, so I left it alone.
4. **geo-svc got a bad config change at minute 69 (cfg-6).** It switched the wire schema from v2 to v3, and callers couldn't decode it, so web-storefront and partner-api failed 74% of requests. The deploy just before it (v180) was only a variable rename, so I reverted the config at minute 81 and both were clean by minute 83.

catalog-svc's CPU stayed at about 98% the whole shift, but it showed no errors and no traffic increase, so I didn't touch it. Someone should find out why it runs that hot.

**Follow-up:** currency-svc is still at 9 replicas instead of its normal 3. I didn't scale it back down because the higher traffic hadn't gone away; if it drops off, those extra replicas can come off.
