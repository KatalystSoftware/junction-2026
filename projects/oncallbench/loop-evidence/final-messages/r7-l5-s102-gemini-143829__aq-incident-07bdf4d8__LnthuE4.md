# r7-l5-s102-gemini-143829/aq-incident-07bdf4d8__LnthuE4

Level 5, seed 102, gemini, score as run 0.1957. The agent's closing message, verbatim:

I have successfully mitigated the majority of the incidents across the online shop's backend during the shift.

Here is a summary of the root causes found and the mitigations applied:

1. **`tracking-svc` published a bad generated file**
   - **Symptom:** `currency-svc` and `inventory-svc` experienced panic errors (`worker panicked loading rules file: 258 entries, limit 200`), leading to cascading failures in `web-storefront`, `mobile-api`, and others. `currency-svc` also entered a retry storm.
   - **Cause:** A recent config change (`cfg-34`) on `tracking-svc` modified the `rules_source` to include additional features, exceeding the file entries limit.
   - **Mitigation:** Scaled up `currency-svc` and `flags-svc` to temporarily absorb the retry storm, then **reverted the config change** (`cfg-34`) on `tracking-svc` so it would generate valid rules files again.

2. **`geo-svc` failed due to an unknown wire schema**
   - **Symptom:** `web-storefront` and `partner-api` began failing with increased error rates.
   - **Cause:** A configuration change (`cfg-10`) on `geo-svc` altered the expected `wire_schema` from `v2` to `v3`, which caused a `DecodeError`.
   - **Mitigation:** **Reverted the config change** (`cfg-10`) on `geo-svc` to restore the correct schema version, which resolved the downstream failures immediately.

3. **`couriers-svc` rate limiter logic was broken**
   - **Symptom:** `mobile-api` and `auth-svc` began failing as `couriers-svc` continuously returned `429 Too Many Requests: rate limiter bucket empty`.
   - **Cause:** A recent deployment (`v155`) on `couriers-svc` erroneously altered the bucket refill formula, causing it to divide the refill rate by 1000, practically emptying the rate limit allowance. 
   - **Mitigation:** Initially attempted a config revert on the rate limits, but the issue was inside the code deploy. **Rolled back the deployment** (`v155`) on `couriers-svc`, successfully eliminating the `429` responses.

4. **`catalog-svc` experienced CPU exhaustion**
   - **Symptom:** `catalog-svc` fired a CPU alert (hitting 0.99 CPU) with worker threads reported as busy.
   - **Cause:** A scheduled `nightly-rollup` job was running and blocking processing. 
   - **Mitigation:** Executed a **restart** on `catalog-svc` to clear the stuck/bloated processing.

By the end of the shift, the error rates on the customer-facing (edge) services (`web-storefront`, `mobile-api`, `partner-api`) were restored to 0%, except for a very minor pool exhaustion on `admin-portal` that contributed trivially to lost revenue right as the shift ended.
