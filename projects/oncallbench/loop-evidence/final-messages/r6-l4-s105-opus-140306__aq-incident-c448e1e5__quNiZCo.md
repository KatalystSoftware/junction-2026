# r6-l4-s105-opus-140306/aq-incident-c448e1e5__quNiZCo

Level 4, seed 105, opus, score as run 0.0, regraded 0.0. The agent's closing message, verbatim:

The shift is over. All four customer-facing services had a 0% error rate from minute 85 to minute 120, and no throttles were left on. I made one mistake: I reverted the wrong currency-svc change first, which costs a $10,000 wasted-mitigation charge.

**Causes found and what fixed them:**
1. **shipping-svc: bad deploy v36 that leaked memory.** Memory was at 99% and the service kept restarting, and callers' retries overloaded it. partner-api was failing about 83%. I rolled back v36 and throttled the service for a short time to stop the retries. partner-api has been at 0% since about minute 30.
2. **emails-svc: bad deploy v46.** It made the currency field required in the price formatter, which raised `KeyError: 'currency'`. The failures went up through sms-svc, import-svc and reviews-svc to admin-portal and web-storefront, which were failing about 4%. That mattered most because admin-portal brings in $17,700 a minute. I rolled back v46 and throttled during the rollback to stop the retries. admin-portal has been at 0% since about minute 62.
3. **currency-svc: bad deploy v175 at minute 46.** It removed the `orders.write` permission scope, and web-storefront went to about 98% errors. Here I got it wrong first: I reverted config change cfg-33 (a credentials rotation made at the same minute), which fixed nothing. I then read the diffs, found the real cause, and rolled back v175 at minute 73. web-storefront has been at 0% since minute 85.
4. **giftcards-svc: overloaded by retries, with no bad change behind it.** Its traffic was about 1,450 requests per second, more than 8 replicas (or later 12) could handle, so it went back into a retry storm each time I lifted the throttle. I scaled it to 20 replicas, where it runs at about 68% CPU. mobile-api has been at 0% since about minute 85.

**Costs I added:**
- **Wasted mitigation:** $10,000 for the currency-svc config revert.
- **giftcards-svc:** 12 extra replicas at $3 each per minute until the end of the shift; I chose not to scale back down because of the risk of another overload.
- **cart-svc:** I scaled it from 4 to 6 replicas at minute 96 as a precaution. It had been at about 98% CPU without errors, and it sits on the path to admin-portal through quotes-svc. That adds about $126.
