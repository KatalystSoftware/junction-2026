# r2-l3-s101-sonnet-112130/aq-incident-9f15b9fa__7MfpnX3

Level 3, seed 101, sonnet, score as run 0.6397. The agent's closing message, verbatim:

The shift is over and all four edge services were at 0% errors when it ended. I had fixed all the faults by minute 73. I made one mistake along the way, and the partner-api fix came late.

Four separate faults, in the order I found them:

1. **Mobile-api, 71% errors (minute 0):**
   - **pricing-svc:** its CPU was pinned at 99% on 6 replicas, so I scaled it to 12 (landed at minute 14).
   - **sms-svc:** deploy v156 changed the wire schema from v2 to v3, which pricing-svc couldn't decode. I rolled it back (done at minute 19).
   - Mobile-api was at 0% by minute 26.
2. **Partner-api, steady 4.5% errors (about $410/min):**
   - **returns-svc rollback:** I rolled back returns-svc v121 first, because the errors started after that deploy. This was wrong. The library bump wasn't the cause, so that rollback was a wasted mitigation ($10,000). It also briefly pushed returns-svc errors to 33% while it ran.
   - **quotes-svc config:** the real cause was quotes-svc config change cfg-15, which cut `db_pool_size` from 40 to 4. That starved returns-svc of connections. I reverted it (done at minute 57), and partner-api dropped to 0%.
3. **Web-storefront, about 99% errors (started minute 47):** address-svc config cfg-20 removed `currency` from `price_fields`, causing `KeyError: 'currency'`. I noticed it at minute 59 and reverted it (done at minute 71). I left the unrelated v118 dependency bump alone.
4. **Left alone:**
   - **cart-svc:** its CPU alert isn't on any edge service's dependency path.
   - **pricing-svc replicas:** I kept all 12. CPU is still 82% on 12 replicas, so it would be overloaded at 6, and the extra replicas cost $3 each per minute.

I waited out the rest of the shift and checked status at minutes 85, 100 and 120. No new faults appeared.

The extra cost came from running partner-api's fault until minute 57 and the unneeded returns-svc rollback. Web-storefront was also down for about 24 minutes (minutes 47 to 71) because I didn't see its fault until minute 59.
