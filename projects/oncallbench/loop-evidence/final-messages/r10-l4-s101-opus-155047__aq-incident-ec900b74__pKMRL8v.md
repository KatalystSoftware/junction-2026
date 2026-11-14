# r10-l4-s101-opus-155047/aq-incident-ec900b74__pKMRL8v

Level 4, seed 101, opus, score as run 0.7272, regraded 0.7272. The agent's closing message, verbatim:

The shift is over. All four customer-facing services were at 0% errors from minute 69 to the end at minute 120. I found and fixed four separate causes, and every action I took landed on a service that needed it, so no $10,000 wasted-mitigation charges.

| Cause | Customer impact | Fix | Back to normal by |
|---|---|---|---|
| **quotes-svc** deploy v59, shipped at −40, set its database connection pool to a fixed size of 4, so calls timed out. This failed returns-svc, then search-svc, then partner-api. | partner-api at 4.5% errors on $18,100/min, the most expensive fault | Added replicas first so retries during the rollback wouldn't overload it, then rolled back v59 | ~min 48 |
| **sms-svc** deploy v156, shipped at −8, changed the message format to "v3", which failed to decode. Callers kept retrying the failures, so retries swamped the service. | mobile-api (via pricing-svc) | Throttled and scaled it to break the retry loop, then rolled back v156 | ~min 59 |
| **pricing-svc** had real traffic growth plus a retry loop since −25. | mobile-api at ~97% errors | Throttled it for a while and scaled it from 6 to 12, later 14 | ~min 62 |
| **address-svc** config change cfg-20, a new fault at minute 47, dropped `currency` from `price_fields`. | web-storefront at ~98% errors (also via recommendations-svc) | Reverted the config | ~min 65 |
| **Other alerts:** cart-svc has had a CPU alert since −6. | None, nothing calls it | Left alone | — |

The temporary extra replicas on sms-svc and quotes-svc went back to normal once they had recovered. Lifting the throttles is why mobile-api errors only fell gradually while I was still working on sms-svc.

The remaining cost is pricing-svc at 14 replicas instead of 6, about $24/min. I kept them deliberately: it was running at about 81% CPU on 12 replicas and traffic was still climbing.
