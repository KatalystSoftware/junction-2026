# r2-l3-s101-opus-112132/aq-incident-9f15b9fa__dUnXTFt

Level 3, seed 101, opus, score as run 0.8778. The agent's closing message, verbatim:

The shift is over and all four customer-facing services were at 0% errors from minute 64 to the end. I found four separate causes and used one mitigation on each. None of them failed.

| # | What customers saw | Cause | What I did | When it took effect |
|---|---|---|---|---|
| 1 | mobile-api failing (part of its 71% errors) | pricing-svc traffic jumped from about 1,060 to 2,700 requests/sec at minute −25, and its CPU sat at 99% | Scaled pricing-svc from 6 to 15 replicas | minute 10 |
| 2 | The rest of mobile-api's errors | sms-svc deploy v156 at minute −8 changed the wire schema from v2 to v3 | Rolled back sms-svc | minute 17 |
| 3 | partner-api at about 4.5% errors (about $410/min) | quotes-svc config change cfg-15 at minute −40 cut its database connection pool from 40 to 4. returns-svc then timed out waiting for connections, and that passed through search-svc to partner-api | Reverted the quotes-svc config | minute 54 |
| 4 | web-storefront at 98% errors (new fault at minute 47) | address-svc config change cfg-20 dropped `currency` from its price fields | Reverted the address-svc config | minute 63 |

Things to know:
- **Partner-api was slow to fix.** It ran at about 4.5% errors until minute 54, which is roughly $20k of lost revenue. That's probably the biggest cost of the shift. quotes-svc looked healthy in its own metrics, and I only found it through the returns-svc logs.
- **Changes I left alone:** returns-svc v121, quotes-svc v116, address-svc v118 and sms-svc cfg-7 were recent but turned out to be harmless or not the cause.
- **Ignored alert:** cart-svc has had high CPU since before the page. No customer-facing service depends on it, so I didn't touch it.
- **pricing-svc is still at 15 replicas.** That's 9 extra, costing $27/min from minute 10. I kept them because its traffic was still rising (about 2,860 requests/sec at minute 64).
