# r10-l4-s102-opus-155339/aq-incident-cca4a75f__vNjwc2i

Level 4, seed 102, opus, score as run 0.0258, regraded 0.0261. The agent's closing message, verbatim:

The shift ran the full 120 minutes and all four customer-facing services ended at 0% errors. I found four separate causes; each one is fixed and I checked the result.

1. **currency-svc was overloaded (from about minute −21).** Its normal traffic went from about 1,300 to 3,800 requests per second, while 3 replicas can handle about 1,700. Callers retrying the failed requests pushed it to about 13,000 per second and an 87% error rate. That broke couriers, limits, ledger and auth, so web-storefront and mobile-api were failing 87–92% of requests. Its only recent deploy came well before the errors started, so I didn't count it as the cause.
   - My first fix didn't hold. I briefly rejected most of its traffic to stop the retries, but its normal load was still too much for 3 replicas.
   - I scaled it to 9 replicas, then rejected traffic again for a few minutes to clear the retries. It has run at about 73% CPU since. Web-storefront was back to 0% by minute 29.
   - I left it at 9 replicas through the end of the shift because the load was still rising. That costs about $18 per minute for the extra replicas.

2. **admin-portal was failing 4.2% of requests, the biggest loss at about $670/min.** Deploy v177 of import-svc set its database connection pool to a fixed size of 4. I rolled it back.
   - The rollback failed some requests, and admin-portal's retries overloaded import-svc, so admin-portal errors rose to about 43%.
   - Rejecting half of import-svc's traffic for two minutes cleared that. Admin-portal was at 0% by minute 48.

3. **mobile-api stayed at about 41% after currency-svc recovered.** Its logs showed couriers-svc rejecting calls because its rate limiter had run out. Deploy v100 of couriers-svc had broken how the limiter refills (it divided the refill by 1,000). I rolled it back.

4. **A new fault started at minute 69:** web-storefront and partner-api jumped to 74% errors. A config change to geo-svc (cfg-6) moved it to a new wire schema version, v3. I reverted that config at minute 77 and both were at 0% by minute 79. I left the deploy made at the same minute (v180) alone because it only bumped a library version and renamed a variable.

No other services were changed and no throttles are still on. currency-svc is the only service still running above its normal replica count.
