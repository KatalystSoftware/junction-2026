# r4-l4-s102-gemini-131100/aq-incident-cca4a75f__is5Twiq

Level 4, seed 102, gemini, score as run 0.0, regraded 0.0. The agent's closing message, verbatim:

I have successfully completed the shift as the on-call engineer, resolving the issues that were causing lost revenue and returning all edge services to a stable, zero-error state.

Here is a summary of the incidents and the mitigations applied during the shift:

1. **`currency-svc` Overload:**
   - **Symptom:** `web-storefront` and `mobile-api` were experiencing massive error rates because their shared dependencies rely on `currency-svc`, which was shedding load due to an intense retry storm.
   - **Cause:** `couriers-svc` had a bad deploy (`v100`) at minute -20 that contained a bug in its rate limiter `bucket.py`, causing it to inadvertently flood `currency-svc` with requests.
   - **Mitigation:** I rolled back the `v100` deploy on `couriers-svc`. Additionally, I scaled `currency-svc` up to 12 replicas to allow it to quickly process the backlog and recover from the retry storm. Once traffic settled, I safely scaled `currency-svc` back down to 8 replicas to minimize ongoing cost while maintaining stability.

2. **`admin-portal` Errors:**
   - **Symptom:** The `admin-portal` (the highest revenue-generating service) began experiencing an error rate close to ~0.40 due to timeout errors when connecting to `import-svc`.
   - **Cause:** A deploy on `import-svc` (`v177` at minute -28) incorrectly hardcoded the connection pool size to 4, which caused its callers to queue up and eventually time out.
   - **Mitigation:** I immediately rolled back the `v177` deploy on `import-svc`. Since `import-svc` temporarily became overloaded with retries during the rollback, I scaled it up to 16 replicas to clear the retry storm and safely scaled it back to its normal 8 replicas once the RPS dropped to normal levels.

3. **`geo-svc` Failures:**
   - **Symptom:** Both `web-storefront` and `partner-api` began to see huge error rates (0.74+) starting at minute 69.
   - **Cause:** A config change on `geo-svc` (`cfg-6`) altered the wire schema from `v2` to `v3`, which broke its communication with down-stream callers.
   - **Mitigation:** I promptly reverted the `cfg-6` config change on `geo-svc`.

With these mitigations in place, all alerts cleared, the error rate across all edge services dropped back to 0.0, and operations returned to normal. I concluded the shift and ensured there were no unnecessary excess replicas burning costs.
