The shift is over, and all four customer-facing services were at 0% errors from minute 90 to minute 120. One of my own steps made things worse for a while: rolling back quotes-svc set off a retry storm that briefly took partner-api to about 52% errors (minutes 53–75).

**What broke and what I did**

| Problem | What I did | Result |
|---|---|---|
| **pricing-svc overloaded since minute −25** and stuck in a retry storm. Its traffic had gone from about 1,060 to about 2,900 requests/sec, more than 6 replicas can handle. mobile-api was failing about 97% of requests. | Rejected 50%, then 80%, of its requests to stop the storm. Scaled it from 6 to 12 replicas, then removed the throttle. | It runs at about 82% CPU with no errors. |
| **sms-svc bad deploy v156** at minute −8 (it changed the wire schema from v2 to v3). | Throttled it to break its own storm, then rolled the deploy back. | Fixed |
| **quotes-svc deploy v59** at minute −40 set its database connection pool to a fixed 4 connections. This caused about 4.5% errors on partner-api through returns-svc and search-svc. | Rolled the deploy back. | Fixed (see below) |
| **pool-b config cfg-11** added a "NoSchedule" taint, so no new replicas could start on that pool. | Reverted the config. | Fixed |
| **dns-8 config cfg-22** at minute 35 made the resolver fail about 11% of lookups. | Reverted the config. | Fixed |
| **address-svc config cfg-20** at minute 47 dropped `currency` from `price_fields`, causing `KeyError: 'currency'`. web-storefront was failing about 99%. | Reverted the config. | Fixed |

**My mistake:** quotes-svc was near capacity and its callers retry failed calls, so before the rollback I asked to scale it from 6 to 10 replicas. The new replicas never started because the pool-b taint was blocking them. The rollback's failures then set off the storm. It ended once I throttled quotes-svc and reverted pool-b. Checking that the scale had landed before starting the rollback would have prevented it. I then set quotes-svc back to 6 replicas, which costs nothing.

**What's left:**
- pricing-svc stays at 12 replicas (about $18/min) because its traffic needs them.
- Before minute 35, address-svc was already alerting, but its only recent changes came at minute 47. I didn't find what caused the earlier errors.
- No mitigation went to a service that didn't need it. I left cart-svc's CPU alert alone because no customer-facing service calls it, and the other recent changes I checked looked harmless.
