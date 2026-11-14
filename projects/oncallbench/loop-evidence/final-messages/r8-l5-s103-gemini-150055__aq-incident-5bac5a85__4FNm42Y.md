# r8-l5-s103-gemini-150055/aq-incident-5bac5a85__4FNm42Y

Level 5, seed 103, gemini, score as run 0.2459. The agent's closing message, verbatim:

The incident is now fully resolved and the shift has been completed. 

Here is a summary of the root causes found and the actions taken to mitigate them:

1. **`pricing-svc` Error Rate (Timeouts)**
   - **Symptom:** `pricing-svc` was experiencing high error rates (~60%) and `list_alerts` indicated it started firing at minute -14. 
   - **Root Cause:** A bad deploy (`v105`) accidentally divided the request deadline budget by `10000` instead of `1000`, causing widespread timeouts across requests.
   - **Action Taken:** Executed `rollback` on `pricing-svc` to revert the broken deployment and restore normal deadline functionality.

2. **`payments-svc` CPU & Error Spike (Retry Storm due to Bad File)**
   - **Symptom:** `payments-svc` started throwing 90%+ errors, shedding load and causing huge impact on edge services (`mobile-api` and `web-storefront`).
   - **Root Cause:** The `payments-svc` was loading a generated rules file every 5 minutes from `quotes-svc`. A bad config change (`cfg-6`) on `quotes-svc` had added `r0.features` to the rules source, which bloated the rules past the 200 entry limit, causing the workers to panic in `payments-svc`. This led to a massive retry storm from downstream callers.
   - **Action Taken:** Executed `revert_config` on `quotes-svc` to stop generating the bad rules file. Temporarily used `scale` on `payments-svc` (from 3 to 12 replicas) to aggressively clear out the massive backlog of queued retries once the new correct file had been consumed. 

3. **`labels-svc` Cascading Failures (Permission Denied)**
   - **Symptom:** Midway through the shift, `labels-svc` and its dependent downstream services (`geo-svc`, `tax-svc`, `disputes-svc` -> leading up to edge services) began failing with ~50% error rates. 
   - **Root Cause:** A live configuration change on `labels-svc` (`cfg-38` at min 55) removed the `"orders.write"` scope from the `token_scope` payload, causing a `PermissionDenied` exception.
   - **Action Taken:** Executed `revert_config` on `labels-svc` to restore the correct token scope format and immediately resolve the cascading failures. 

4. **`experiments-svc` Retry Storm Mitigation**
   - **Symptom:** The service suffered a retry storm as an after-effect of an operations restart attempting to clear a slow/bloated `nightly-rollup` worker thread job. 
   - **Action Taken:** Temporarily scaled the service to 16 replicas to soak up the retries and let the CPU calm down. 

All temporary scale-up operations (`payments-svc` & `experiments-svc`) were correctly scaled down to their baseline normal replica counts before finishing the shift to minimize extraneous AWS/infrastructure cost penalties. Error rates on all edge and customer-facing revenue services successfully settled back down to their baseline 3.7%.
