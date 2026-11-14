# r10-l4-s101-opus-155047/aq-incident-ec900b74__yZYAnrJ

Level 4, seed 101, opus, score as run 0.1791, regraded 0.1791. The agent's closing message, verbatim:

The shift is over. All four customer-facing services were at 0% errors from minute 90 to the end, with no alerts firing and no throttles on. Along the way I made one costly wrong call: the rollback of returns-svc at minute 38 didn't fix anything, so it will likely be charged as a $10,000 wasted mitigation.

**What caused the errors:**
1. **partner-api, 4.5% errors from before the page (about $815/min, the biggest loss):** quotes-svc deploy `v59` replaced the configured database connection pool size with a fixed `Pool(size=4)`. Requests timed out waiting for a connection, and that passed up through returns-svc and search-svc to partner-api. Because quotes-svc ran close to capacity and its callers retry, I scaled it from 6 to 12 replicas before rolling the deploy back at minute 75. Retries reached 50% of its traffic during the rollback but it didn't overload. partner-api was at 0% by minute 84.
2. **mobile-api, around 97% errors at the page:** this had two separate causes.
   - **More traffic:** pricing-svc's traffic jumped about 2.5x at minute −25, overloaded it, and set off a retry storm. Scaling it from 6 to 16 replicas ended the overload by minute 23.
   - **Bad deploy:** sms-svc deploy `v156` switched its wire format to "v3", which caused `DecodeError: unknown wire schema 'v3'`. This failed about half its requests, and callers retrying them kept it overloaded. I first took it for plain overload and spent time on scaling and two short throttles before reading its logs. Rolling back `v156` at minute 84 fixed mobile-api by minute 90.
3. **web-storefront, a new fault at minute 47 (98% errors):** address-svc config change `cfg-20` removed `currency` from `price_fields`. Reverting it at minute 58 fixed the errors.

**What will still cost money:**
- **The returns-svc rollback:** I rolled back deploy `v121` because its timing matched partner-api's errors, but the change looked harmless and the errors came from quotes-svc. Besides the probable $10,000 charge, the rollback failed 30% of returns-svc requests for 6 minutes. I couldn't see how much of that reached partner-api.
- **Extra replicas:** at the end, pricing-svc was still at 16 (normal 6), sms-svc at 10 (normal 8) and quotes-svc at 8 (normal 6). pricing-svc still needs its replicas because its traffic stayed high, about 2,950 requests per second. I left the other two slightly above normal so their CPU stayed around 60–65%.
