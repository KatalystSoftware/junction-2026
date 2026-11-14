# r7-l5-s102-opus-143827/aq-incident-07bdf4d8__tCFmBPo

Level 5, seed 102, opus, score as run 0.8807. The agent's closing message, verbatim:

I found and fixed five faults, and all four customer-facing services were at 0% errors from minute 81 until the shift ended at 120. I used no extra replicas and made no fixes on services that didn't need them.

| # | Cause | What customers saw | Fix | Fixed at |
|---|---|---|---|---|
| 1 | currency-svc was stuck in a retry storm: about 80% of its incoming traffic was retries and CPU sat at 0.99. It had no changes of its own. | web-storefront 76% errors, mobile-api 86% | Throttled it to 70% at minute 7 and lifted the throttle at 25; it stayed healthy after that | ~min 25 |
| 2 | tracking-svc config cfg-34 added a duplicate rules source (`[features, r0.features]`) to the file it generates. It went out at the same time as currency-svc's problems, and flags-svc and inventory-svc, which also load that file, started failing. | Possibly part of #1 (not proven) | Reverted cfg-34 | min 17 |
| 3 | import-svc config cfg-38 cut `db_pool_size` from 40 to 4. Its own metrics looked healthy, but admin-portal was timing out on calls to it. | admin-portal 4.2% errors | Reverted cfg-38 | ~min 43 |
| 4 | couriers-svc deploy v155 broke its rate limiter: the refill was divided by 1000, so requests got "429 Too Many Requests". | mobile-api 41% errors | Rolled back v155 | min 60 |
| 5 | New fault during the shift: geo-svc config cfg-10 at minute 69 changed `wire_schema` from v2 to v3. | web-storefront and partner-api 74% errors | Reverted cfg-10 | min 81 |

Fault #3 was the most expensive. admin-portal earns $12,800 a minute, so its 4.2% error rate cost about $540 a minute for roughly 43 minutes. I worked on currency-svc first and found the import-svc cause later than I would have liked.

**Left alone on purpose:**
- **catalog-svc** ran at 0.97–0.99 CPU all shift. Its error rate stayed near zero and its callers don't retry, so nothing could build on it.
- **status-page** showed 100% errors, but it is hosted outside our estate and is not a cause.

**Deserves a follow-up:** catalog-svc's high CPU on low traffic is unexplained.
