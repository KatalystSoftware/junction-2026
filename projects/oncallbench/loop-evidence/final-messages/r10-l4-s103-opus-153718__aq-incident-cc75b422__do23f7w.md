# r10-l4-s103-opus-153718/aq-incident-cc75b422__do23f7w

Level 4, seed 103, opus, score as run 0.1995, regraded 0.2058. The agent's closing message, verbatim:

The shift is over. All four customer-facing services were at 0% errors from minute 70 to the end.

The costliest stretch came from my own fix. Rolling back inventory-svc at minute 19 left it overloaded by retries, and every edge service sat at 52–60% errors from about minute 19 to 30. On admin-portal ($21,600/min) that was by far the biggest loss of the shift.

| Fault | Cause | What I did | Result |
|---|---|---|---|
| web-storefront and mobile-api at 88–95% errors since minute −23 | Traffic to payments-svc roughly tripled at minute −23 and set off a retry storm (CPU at 99%, 72% of requests were retries). It had no recent changes. | Scaled payments-svc from 3 to 10 replicas and throttled it to 60% for a few minutes to break the storm | Recovered by minute 22. CPU about 0.7 at 10 replicas. |
| admin-portal and partner-api at 4% errors | Deploy `v123` on inventory-svc changed `row.get("currency","EUR")` to `row["currency"]`. That caused KeyErrors, which reached shipping-svc, then ledger-svc, then the edge. | Rolled back `v123` | The rollback caused the overload above. A 60% throttle for 2 minutes plus scaling from 4 to 6 replicas cleared it; all four edge services were at 0% by minute 30. |
| mobile-api still at 58% | Deploy `v105` on pricing-svc changed the call deadline from `budget_ms/1000` to `budget_ms/10000`, so calls timed out | Rolled back `v105` | Cleared at minute 45 |
| New at minute 55: web-storefront and mobile-api at 51% | Config `cfg-38` on labels-svc dropped the `orders.write` token scope, so geo-svc failed. tax-svc and disputes-svc depend on geo-svc. | Reverted `cfg-38` | Cleared at minute 70 |

Other things to know:
- **experiments-svc:** CPU has been at 97–99% since minute −5, with no errors and no recent changes. I left it alone, and it didn't affect customers during the shift.
- **No wasted mitigations:** none of the rollbacks or config reverts hit a service that didn't need it.
- **Extra replicas:** payments-svc (+7) and inventory-svc (+2) stay scaled up and cost about $27/min.
  - payments-svc traffic is still about 3× its old level, so it needs the extra capacity.
  - inventory-svc ran at 86% CPU before the incident, so the 2 extra replicas protect it from another retry storm.

Review both counts after the shift.
