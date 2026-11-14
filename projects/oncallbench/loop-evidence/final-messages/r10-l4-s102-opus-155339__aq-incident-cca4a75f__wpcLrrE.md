# r10-l4-s102-opus-155339/aq-incident-cca4a75f__wpcLrrE

Level 4, seed 102, opus, score as run 0.7954, regraded 0.8028. The agent's closing message, verbatim:

I found and fixed four faults. All four edge services were at 0% errors from minute 77 to the end of the shift at minute 120, with no throttles left on.

1. **currency-svc overloaded (web-storefront and mobile-api at 87–92% errors):** Its normal traffic had roughly tripled to about 3,600 rps at minute −21, which is more than its 3 replicas can serve. Callers' retries then pushed load to about 13,000 rps. I scaled it to 9 replicas and briefly throttled it 90% to clear the retries. Web-storefront was back to 0% by minute 21. It is still at 9 replicas, running at about 72% CPU with traffic slowly rising. That costs $18/min, and I kept it because going back to 3 replicas would bring the overload back.
2. **admin-portal at 4.2% errors (about $670/min, the biggest loss):** The cause was in import-svc. Its deploy v177 hardcoded the database pool size to 4, so admin-portal's calls timed out. import-svc's own metrics looked healthy. It was running near capacity and its callers retry, so before rolling back I scaled it from 8 to 12 replicas to avoid a retry storm. After the rollback I set it back to 8. admin-portal was at 0% by minute 54.
3. **couriers-svc deploy v100 (mobile-api still at about 41%):** The deploy divided the rate limiter's refill by 1000, so most requests were rejected with "429 Too Many Requests". Rolling it back brought mobile-api to 0% by minute 59.
4. **geo-svc config cfg-6, new at minute 69 (web-storefront and partner-api at 74%):** The change switched `wire_schema` from v2 to v3. Reverting the config fixed both by minute 78.

catalog-svc has been at about 98% CPU since minute −9 while its traffic stayed flat, but its error rate stayed near zero. I didn't restart it, because a restart that turned out unnecessary costs $10,000 and fails half its requests for 3 minutes. It's worth a look on the next shift.
