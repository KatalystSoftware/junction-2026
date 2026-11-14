# r7-l5-s101-opus-143149/aq-incident-5815b038__MHfW8rF

Level 5, seed 101, opus, score as run 0.0. The agent's closing message, verbatim:

The shift is over. All four customer-facing services were at 0% errors from minute 100 to the end, with no throttles left on. I fixed five separate causes, but my mistakes cost revenue along the way.

| # | What customers saw | Root cause | Fix |
|---|---|---|---|
| 1 | partner-api failing about 4.6% of requests from the page, rising to 41% by minute 49. This is the $22.7k/min service, so it mattered most. | Deploy v149 to quotes-svc changed `row.get("currency","EUR")` to `row["currency"]`, so requests without a currency threw a KeyError. The failures passed up through returns-svc and search-svc to partner-api. | Rolled back v149 at minute 34. |
| 1b | Same as above | quotes-svc was already near capacity (CPU 0.87). The 30% of requests failing during the rollback were retried, and the retries overloaded it. | Scaled quotes-svc from 6 to 12 replicas at minute 54. partner-api was back to 0% by minute 69. |
| 2 | mobile-api failing about 96% | Config change cfg-16 to subscriptions-svc doubled `rules_source`. The rules file it publishes grew to 344 entries, over sms-svc's limit of 200, so sms-svc workers crashed loading it. That set off a retry storm on sms-svc. | Reverted cfg-16, then throttled sms-svc to 70% for 5 minutes to clear the retry storm. |
| 3 | mobile-api still failing | pricing-svc traffic had grown from about 1,060 to about 2,900 requests/sec, more than 6 replicas can handle. This retry storm was already running 25 minutes before the page. | Throttled it to stop the storm, then scaled pricing-svc from 6 to 16 replicas. Fixed by minute 100. |
| 4 | web-storefront failing about 99%, starting at minute 25 | Config change cfg-36 to address-svc (minute 47) set `wire_schema` to v3, which its callers can't decode. | Reverted cfg-36 at minute 69. |

**Mistakes:**
- **Rollback without headroom:** I started the quotes-svc rollback without checking whether it had room to absorb the extra retries. Scaling it first would have avoided the overload, which cost about 20 minutes of partner-api losing around 40% of its revenue.
- **Throttle lifted too early:** I removed the pricing-svc throttle before checking its capacity, so the retry storm started again. mobile-api failed at about 82% for roughly 10 more minutes before I scaled.
- **Slow on web-storefront:** It got worse at minute 25, but I didn't look at it until minute 49.

**Not fully explained:** address-svc was already failing about 55% from minute 25, before cfg-36 went in. It recovered after the reverts, so the bad subscriptions file reaching loyalty-svc is a likely cause, but I didn't confirm it.

**Left in place:** quotes-svc is still at 12 replicas and pricing-svc at 16, both charged at $3 per extra replica per minute. I kept them because neither has enough capacity at its normal replica count. No mitigation went to a service that didn't need it. I didn't act on the status-page and cart-svc alerts because they weren't affecting customers.
