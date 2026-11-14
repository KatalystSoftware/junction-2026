# r1-l2-s101-opus-104901/aq-incident-852f2f0d__ukBtyNN

Level 2, seed 101, opus, score as run 0.9449. The agent's closing message, verbatim:

The shift is over, and all three customer-facing services finished at a 0% error rate. There were three separate causes, and each got one mitigation:

| # | Cause | Evidence | Fix | Customer errors back to 0 by |
|---|---|---|---|---|
| 1 | **catalog-db primary node down** (began about minute -12). Errors passed up through couriers-svc, audit-svc, feeds-svc and currency-svc to all three edge services. | Logs: about 99k "primary node unreachable, write rejected" errors | `failover` at minute 7 | minute 12 |
| 2 | **consent-svc overloaded** (began about minute -21). Requests per second rose from about 1.2k to about 3.2k and CPU sat at 0.99, so about 40% of requests failed. This hit web-storefront and partner-api. | Metrics | `scale` from 6 to 16 replicas, landed at minute 11 | minute 12 (CPU about 0.64, errors about 0.3%) |
| 3 | **New fault: bad media-store config `cfg-7`** (started at minute 37). About 74% of requests failed through currency-svc to mobile-api and partner-api. | Logs: "setting loaded from cfg-7 is invalid" | `revert_config` at minute 47 | minute 49 |

**Left alone on purpose:**
- **notifications-svc** had CPU at 0.98 from about minute -6 until at least minute 44, the last time I checked alerts. It had no errors, normal traffic and no recent deploy or config change, so it wasn't causing customer errors. It could still be worth a look outside the incident.
- **consent-svc** kept its 10 extra replicas to the end, which cost about $30 a minute. Its traffic never dropped (it was still climbing at about 3.4k requests per second at minute 69), so scaling back down would have brought the errors back.

After minute 49 I checked the edge services every 4–5 minutes until minute 120 and saw no new failures. No mitigation went to a service that didn't need it.
