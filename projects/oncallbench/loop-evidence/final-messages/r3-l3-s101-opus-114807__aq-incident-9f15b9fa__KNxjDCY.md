# r3-l3-s101-opus-114807/aq-incident-9f15b9fa__KNxjDCY

Level 3, seed 101, opus, score as run 0.8988. The agent's closing message, verbatim:

I found and fixed four separate causes, and all four customer-facing services were at 0% errors from minute 60 until the shift ended at minute 120.

| Edge service hit | Root cause | Fix | Back to 0% by |
|---|---|---|---|
| mobile-api (~71% errors) | **pricing-svc** got about 2.6× its normal traffic (~1060 → ~2700 requests/sec) and ran out of CPU | Scaled from 6 to 17 replicas | ~min 30 (both mobile-api fixes) |
| mobile-api | **sms-svc** deploy `v156` (minute −8) changed the wire format from v2 to v3, so ~54% of its requests failed | Rolled back the deploy | ~min 30 (both mobile-api fixes) |
| partner-api (~4.5% of $9,100/min) | Config change `cfg-15` on **quotes-svc** cut `db_pool_size` from 40 to 4. Its callers timed out (returns-svc, then search-svc, then partner-api). | Reverted the config | ~min 47 |
| web-storefront (~98% errors, new fault at minute 47) | Config change `cfg-20` on **address-svc** removed `currency` from `price_fields`, causing `KeyError: 'currency'` | Reverted the config | ~min 60 |

- **Ignored on purpose:** cart-svc kept a CPU alert all shift. No customer-facing service calls it, so I left it alone rather than risk a $10,000 wasted-mitigation charge. The deploys that landed at the same time as the bad configs (address-svc `v118`, quotes-svc `v116`) looked harmless in their diffs, so I didn't roll them back.
- **Ongoing cost:** pricing-svc stayed at 17 replicas. Traffic was still high and rising slowly (about 2,850 requests/sec at minute 60, CPU around 0.6). The 11 extra replicas cost about $33/minute from minute 10.
- **Rest of the shift:** I checked status every 5 minutes from minute 60 to 114, and the alerts once at minute 79. No new faults appeared, so I ended the shift.

I don't have the final cost or score; the finish call returned only the end time.
