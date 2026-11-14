# r4-l4-s101-gemini-130258/aq-incident-ec900b74__2wGGDG5

Level 4, seed 101, gemini, score as run 0.0, regraded 0.0. The agent's closing message, verbatim:

I have successfully managed the incident and restored all services to full health. Here is a summary of the issues and the actions taken:

### 1. `pricing-svc` and `sms-svc` Overload
- **Symptom:** `mobile-api` error rate peaked near 97%, with `pricing-svc` overloaded by a retry storm and `sms-svc` showing high errors and CPU.
- **Cause:** Deploy `v156` on `sms-svc` changed the wire schema to `v3`, causing `DecodeError`s which resulted in a massive cascade of retries starting from `pricing-svc`.
- **Mitigation:** I rolled back the `sms-svc` deploy (`v156`). To recover the overwhelmed `pricing-svc` faster from its retry storm, I temporarily scaled it up to 24 replicas. Once `sms-svc` fully rolled back, I scaled `sms-svc` up briefly to absorb its own backlog.

### 2. `web-storefront` Errors
- **Symptom:** `web-storefront` began experiencing 98% error rates around minute 47.
- **Cause:** A configuration change (`cfg-20`) was pushed to `address-svc`, modifying the `price_fields` list and omitting `currency`, which caused widespread `KeyError` exceptions. 
- **Mitigation:** I reverted the configuration change (`cfg-20`) on `address-svc`, immediately restoring `web-storefront` to an error rate of 0%.

### 3. `partner-api` Error Rate & `cart-svc` CPU Alert
- **Symptom:** `partner-api` was sitting at a 5% error rate that eventually spiked during rollbacks. `cart-svc` was firing a CPU >= 99% alert due to being bottlenecked.
- **Cause:** `quotes-svc` had recently undergone a deploy (`v59`) that hardcoded its database connection pool size to 4. This bottleneck trickled down to `returns-svc` (causing `TimeoutError`s) which in turn bottlenecked both `cart-svc` and `search-svc`, eventually making `partner-api` fail. 
- **Mitigation:** I initially investigated by rolling back `returns-svc` but later confirmed `quotes-svc` was the root cause. I rolled back `quotes-svc` (`v59`). Upon rollback completion, a retry storm kept `quotes-svc` overloaded, so I successfully mitigated the remaining queue by scaling it to 24 replicas. This simultaneously cleared the `cart-svc` CPU alert and brought the `partner-api` error rate back down to 0%.

The shift is complete with all alerts cleared and no outstanding operations.
