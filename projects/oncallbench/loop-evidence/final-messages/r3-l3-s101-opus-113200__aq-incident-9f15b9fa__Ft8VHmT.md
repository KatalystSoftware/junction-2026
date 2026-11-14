# r3-l3-s101-opus-113200/aq-incident-9f15b9fa__Ft8VHmT

Level 3, seed 101, opus, score as run 0.9288. The agent's closing message, verbatim:

I found and fixed four separate causes during the shift. At the end, all four customer-facing services were at a 0% error rate.

1. **pricing-svc traffic surge, which hit mobile-api:** traffic jumped from about 1,060 to 2,700 requests per second 25 minutes before the page. CPU sat at 99% and about 38% of requests failed. I scaled it from 6 to 16 replicas at minute 7. I left it at 16 for the rest of the shift, so the 10 extra replicas cost about $3,300.
2. **Bad sms-svc deploy, also hitting mobile-api:** deploy v156 changed the wire schema from v2 to v3, and about 54% of its requests started failing at minute −8. Together with the pricing overload, mobile-api was failing about 71% of requests. I rolled it back at minute 16, and mobile-api was back to 0% errors by minute 35.
3. **Bad quotes-svc config, which hit partner-api:** config change cfg-15 cut the database pool size from 40 to 4. The resulting timeouts passed up through returns-svc and search-svc, and partner-api was failing 4.5% of requests. That cost about $410 a minute, the largest loss of the shift because partner-api earns the most. I reverted the config at minute 35 and partner-api was at 0% by minute 38. Tracing it down three services took a while, so this one ran longest.
4. **New fault mid-shift: bad address-svc config, which hit web-storefront:** config change cfg-20 at minute 47 removed `currency` from `price_fields`. That caused a `KeyError` in the price formatter and about 98% of web-storefront requests failed. I reverted the config at minute 59 and the storefront was clean by minute 61.

Things I deliberately left alone:
- **cart-svc CPU alert:** it was firing at 98% CPU the whole time. Nothing depends on cart-svc, so it wasn't hurting customers, and touching it risked a $10,000 wasted-mitigation charge.
- **Other recent changes:** the sms-svc log-level config, the quotes-svc logging deploy, and the dependency-bump deploys on returns-svc and address-svc were harmless.

No new faults appeared in the last hour, and I ended the shift at minute 116.
