# r9-l5-s102-opus-152434/aq-incident-07bdf4d8__bZWSz6C

Level 5, seed 102, opus, score as run 0.892. The agent's closing message, verbatim:

The shift is over. All four customer-facing services were at 0% errors from minute 59 to minute 120, except geo-svc's outage from minute 69 to 79. I applied five mitigations, each fixing a confirmed cause. I added no extra replicas and left no throttles on.

**Root causes and fixes:**

1. **tracking-svc config `cfg-34` (minute -21):** it added a second rules source, so the rules file it publishes grew to 258 entries against a limit of 200. currency-svc crashed loading that file and then got stuck in a retry storm, with 99% CPU and about 80% of its requests being retries. This hit web-storefront and, through couriers-svc, mobile-api.
   - Reverted the config at minute 15.
   - Once the crashes stopped, I throttled currency-svc to 60% for about 3 minutes (minutes 22–25) to clear the retry storm, then lifted it. web-storefront was back to 0% by minute 29.
2. **import-svc config `cfg-38` (minute -28):** it cut `db_pool_size` from 40 to 4. admin-portal got pool timeouts on its calls to import-svc, while import-svc's own metrics looked healthy. This was the most expensive fault: 4.2% of admin-portal's $12,800/min, about $540/min.
   - Reverted at minute 42; admin-portal was at 0% by minute 53.
3. **couriers-svc deploy `v155` (minute -20):** it broke the rate limiter's refill (`rate * elapsed / 1000`), so couriers-svc returned 429 errors and mobile-api was at 41–59% errors.
   - Rolled back from minute 53 to 58; mobile-api was at 0% by minute 59.
4. **New fault: geo-svc config `cfg-10` (minute 69):** it changed `wire_schema` from v2 to v3, causing decode errors. web-storefront and partner-api were both at 74% errors.
   - I checked both changes from that minute: the deploy `v37` only touched logging, so I reverted the config instead of rolling back the deploy. Fixed by minute 80.

**Alerts I deliberately left alone:**
- **status-page:** an external service, not part of this estate.
- **flags-svc high CPU and errors:** nothing calls it, so it costs no revenue.
- **catalog-svc high CPU:** its error rate stayed normal.

The biggest avoidable loss was admin-portal: I checked its three dependencies first and only found the import-svc problem from admin-portal's own logs, so it ran at 4.2% errors until about minute 43.
