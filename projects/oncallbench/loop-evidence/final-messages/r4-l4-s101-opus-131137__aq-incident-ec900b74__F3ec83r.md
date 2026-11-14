# r4-l4-s101-opus-131137/aq-incident-ec900b74__F3ec83r

Level 4, seed 101, opus, score as run 0.3719, regraded 0.3719. The agent's closing message, verbatim:

The shift is over. From minute 77 to 120, all four customer-facing services showed 0% errors and no throttles were left on. I didn't get the final cost figure from the simulator, so I can't tell you the score.

I found and fixed four causes:

1. **mobile-api (about 97% errors when paged):** pricing-svc had more traffic than it could handle. Its callers retry, so it was flooded with retries of failed calls from minute -25. A bad sms-svc deploy at minute -8 (`v156`, which changed the wire schema from v2 to v3) made things worse.
   - I rolled back sms-svc.
   - I briefly rejected 90% of requests at both pricing-svc and sms-svc so the retry floods could clear.
   - Fresh traffic to pricing-svc was about 2,700 requests per second, roughly twice what 6 replicas can serve. I scaled it from 6 to 14 replicas and rejected 50% of its requests until the new replicas came up. mobile-api was at 0% errors by minute 62.
2. **partner-api (about 4.7% errors since minute -42, but its revenue is $18,100/min):** quotes-svc deploy `v59` at minute -40 hard-coded its database connection pool size to 4. The pool ran out and requests timed out, and that passed up through returns-svc and search-svc to partner-api.
   - I rolled back `v59`.
   - The rollback failed some requests, and the retries overloaded quotes-svc. partner-api errors rose to about 56–70% for roughly 6–8 minutes, which was costly.
   - A one-minute 90% throttle on quotes-svc cleared the overload, and partner-api was at 0% by minute 70.
3. **web-storefront (about 99% errors, a new fault at minute 47):** address-svc config change `cfg-20` dropped `currency` from its price fields. I reverted the config and errors were at 0% by minute 77.

**Things I deliberately left alone:**
- **cart-svc:** it has been at 99% CPU since minute -6, but no customer-facing service calls it.
- **Recent changes that looked harmless:** the returns-svc library patch and the address-svc handler refactor. Neither turned out to be the cause.

**Ongoing cost:** pricing-svc is still at 14 replicas (8 above normal), which costs about $24 a minute. I kept them because its current traffic needs at least 11. If that traffic falls back to its earlier level of about 1,060 requests per second, it can go back down to 6.
