# r10-l4-s102-opus-155339/aq-incident-cca4a75f__5Cky3w8

Level 4, seed 102, opus, score as run 0.0358, regraded 0.0361. The agent's closing message, verbatim:

I found and fixed four faults. All four customer-facing services were at 0% errors from minute 80 until the shift ended at minute 120.

1. **currency-svc was overloaded (web-storefront and mobile-api at about 90% errors).** Its incoming traffic tripled at minute −21, from about 1,300 to about 3,700 requests per second. That was more than 3 replicas could serve, and the callers' retries kept it overloaded. Throttling it alone didn't fix it, because the extra traffic was real demand and not just retries. I scaled it from 3 to 10 replicas and lifted the throttle once the new replicas were up. Web-storefront recovered by minute 39.
2. **import-svc had a bad deploy (admin-portal at about 4.2% errors).** Deploy v177 hardcoded its database connection pool to 4 (`Pool(size=4)`), so calls timed out. At admin-portal's $15,900/min, this was the most expensive fault. I rolled it back at minute 30, but the rollback's own failures set off a retry storm and pushed admin-portal to about 45–55% errors for roughly 13 minutes. That spike was probably the largest single loss of the shift. A short 50% throttle cleared the storm, and I scaled import-svc from 8 to 12 replicas because it normally runs near 88% CPU. Admin-portal was clean from about minute 44.
3. **couriers-svc had a bad deploy (mobile-api at about 41% errors).** Deploy v100 broke the rate limiter: it divided the refill rate by 1000, so requests got "429 Too Many Requests". I rolled it back and mobile-api was clean at minute 58.
4. **geo-svc had a bad config change that started during the shift (web-storefront and partner-api at 74% errors).** At minute 69, config change cfg-6 switched the wire format from v2 to v3, which its callers couldn't decode. I reverted it and both services were clean by minute 80.

**Cost notes:**
- currency-svc and import-svc stayed scaled up (7 and 4 extra replicas) to the end of the shift, about $3,000 in total. I judged that cheaper than risking another overload.
- I didn't touch two other things I looked at, so no fixes went to services that didn't need them:
  - **catalog-svc** has been running at about 99% CPU since minute −9, with no recent change and no errors. It's worth someone checking.
  - **admin-portal's deploy v96** only bumped a library version and changed a log line.
