The shift is over. Every customer-facing service was at 0% errors from about minute 84 to the end, and nothing new broke in the last 35 minutes. I don't know the final score or exact dollar cost.

**Causes found and fixed**

| Customer impact | Root cause | Fix |
|---|---|---|
| mobile-api ~97% errors (started at minute -25) | pricing-svc was getting more traffic than its 6 replicas could handle. Callers retrying failed requests kept it overloaded. | Throttled it to stop the retries, then scaled 6 → 14 replicas (landed at minute 59). Lifted the throttle at minute 76. |
| mobile-api, same path | sms-svc deploy v156 changed the message format to "v3", which failed with `DecodeError: unknown wire schema 'v3'`. | Rolled back the deploy. It stayed overloaded from retries afterwards, so I throttled it 50% for about 8 minutes until that cleared. |
| partner-api 4.5% errors (the $18,100/min service) | quotes-svc deploy v59 hardcoded its database connection pool to 4, so requests timed out. The failures reached partner-api through returns-svc and search-svc. | Rolled back v59, then throttled quotes-svc briefly to clear the retry overload the rollback caused. |
| web-storefront ~99%, admin-portal ~20% (started at minute 35) | Config change cfg-22 on the shared DNS resolver dns-8 changed its forwarders to `10.9.9.9`. Lookups failed for every service that uses dns-8, including loyalty-svc and through it address-svc. | Reverted cfg-22. |
| web-storefront, same path | address-svc config cfg-20 (minute 47) removed `currency` from `price_fields`, causing `KeyError: 'currency'`. | Reverted cfg-20. |

**Mistakes that cost money**
- **Rolling back quotes-svc caused a spike.** The rollback pushed quotes-svc into retry overload. partner-api was at about 44% errors for roughly 10–15 minutes around minutes 45–65. Throttling quotes-svc before the rollback would probably have avoided most of that.
- **I misread pricing-svc at first.** I lifted its throttle partway at minute 50 before scaling, and it overloaded again. Scaling it right away would have brought mobile-api back sooner.

**Running cost:** the 8 extra pricing-svc replicas stayed until the end of the shift, about $1,450.

**Left alone:** cart-svc has been near 100% CPU since before the page. Nothing calls it, so it isn't losing revenue. It's worth a look outside the incident.
