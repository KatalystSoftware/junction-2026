# r1-l1-s101-opus-104946/aq-incident-62f55852__wVVT9mG

Level 1, seed 101, opus, score as run 0.9711. The agent's closing message, verbatim:

The shift ran the full 120 minutes and all three customer-facing services ended with 0% errors. There were three separate faults; I fixed each one at its source and confirmed it worked.

| Minute | Cause | Effect | Fix | Result |
|---|---|---|---|---|
| −21 | **consent-svc** traffic nearly tripled (about 1,200 to 3,160 requests/sec, no recent changes). CPU hit 0.99 and it rejected about 40% of requests because its queue was full. | ~50% errors on web-storefront and partner-api | Scaled from 6 to 15 replicas (min 0) | CPU fell to 0.68 and errors stopped by minute 5 |
| −12 | **catalog-db** primary node unreachable, so writes were rejected | Errors spread through couriers-svc, audit-svc, limits-svc, pricing-svc, feeds-svc, geo-svc and currency-svc, reaching all three customer-facing services | Failover (min 0) | Fixed by minute 5 |
| 37 (new) | **media-store** config change `cfg-7` ("raise log level") loaded an invalid setting | 74% errors on mobile-api and partner-api | Reverted the config (min 40) | Back to 0% by minute 43 and stayed there |

- **Left alone on purpose:** notifications-svc had a high-CPU alert from before the page. Its logs showed a scheduled `nightly-rollup` job, and it had no errors. The alert cleared by itself around minute 88, so I didn't spend a mitigation there.
- **Ongoing cost:** the 9 extra consent-svc replicas cost about $3,100 over the shift. I didn't scale back down because traffic stayed high and running short of capacity would cost more.
- **Final `finish` call:** it returned "the shift is over" because I had already waited out all 120 minutes, so the shift was fully played out.
