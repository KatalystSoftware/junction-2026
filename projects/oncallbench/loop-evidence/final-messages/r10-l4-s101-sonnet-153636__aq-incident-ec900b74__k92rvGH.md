# r10-l4-s101-sonnet-153636/aq-incident-ec900b74__k92rvGH

Level 4, seed 101, sonnet, score as run 0.021, regraded 0.021. The agent's closing message, verbatim:

All four edge services were at 0% errors from minute 90 through the end of the shift. I ended the shift at minute 102 with 18 minutes left. I didn't check status after that, so the last minutes are unconfirmed.

**What was broken and what fixed it**
- **sms-svc / mobile-api:** deploy v156 broke sms-svc, which then ran in a retry storm with pricing-svc. I rolled back v156. Pricing-svc stayed overloaded, so I throttled it to 90% and scaled it from 6 to 16 replicas. I lifted the throttle at minute 90, once the extra replicas were up.
- **partner-api:** quotes-svc deploy v59 hard-coded a database pool size of 4, which caused the steady ~4.5% errors. Rolling back v59 cleared it.
- **web-storefront:** address-svc config cfg-20 (made at minute 47) caused the `KeyError: 'currency'` errors. Reverting it cleared the errors.

**Mistakes that cost money**
- I rolled back returns-svc v121 and address-svc v118. Neither was a cause. That is two wasted mitigations at $10,000 each, plus 6 minutes of 30% failures on each service.
- I lifted the pricing throttle at minute 71, before the added replicas had landed. Pricing overloaded again until I re-throttled and scaled it.
- It took until minute 61 to find the quotes-svc fault, so partner-api (the biggest earner) was at 4.5% errors for about an hour.

**Cleanup**
- I scaled sms-svc back to 8 and quotes-svc back to 6.
- I left pricing-svc at 16 replicas because its load is now about 2,950 requests/min. That is roughly 10 extra replicas costing $3 each per minute.
