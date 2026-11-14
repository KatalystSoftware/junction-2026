# r3-l3-s103-gemini-113141/aq-incident-5b188273__9GmzNWp

Level 3, seed 103, gemini, score as run 0.3148. The agent's closing message, verbatim:

I have completed the shift and stabilized all services. Here is a summary of the incidents that occurred and the mitigations applied to keep revenue loss to a minimum:

1. **Buggy Deploy on `pricing-svc` (Start of Shift)**:
   - **Symptom**: `pricing-svc` had a high error rate, affecting the `mobile-api`.
   - **Cause**: A recent deploy (`v105`) introduced a bug in `rpc/call.py` calculating deadlines incorrectly (`/ 10000` instead of `/ 1000`).
   - **Fix**: Rolled back the deploy (`v105`) on `pricing-svc`.

2. **Traffic Spike on `payments-svc` (Start of Shift)**:
   - **Symptom**: High CPU and error rate alerts on `payments-svc`, impacting `mobile-api` and `web-storefront`.
   - **Cause**: The service was overwhelmed by a 3x traffic spike (RPS jumped from ~1000 to ~3300), causing its request queues to fill up.
   - **Fix**: Scaled up `payments-svc` to 10 replicas to handle the load effectively.

3. **High CPU on `experiments-svc`**:
   - **Symptom**: Sustained 0.99 CPU alert. 
   - **Cause**: Logs indicated a scheduled `nightly-rollup` job was running. Since it wasn't dropping customer requests, this was a false alarm in terms of impact. 
   - **Action**: Initially attempted a restart and a scale-up, but quickly reverted the scale-up back to normal replicas (4) upon realizing it was a background task, avoiding unnecessary extra replica costs. The job naturally completed and the alert cleared on its own at minute 88.

4. **Bad Config on `labels-svc` (Minute 55)**:
   - **Symptom**: Error rates spiked on `web-storefront` and `mobile-api` midway through the shift.
   - **Cause**: A configuration change (`cfg-38`) deployed at minute 55 on `labels-svc` mistakenly removed the `orders.write` token scope. This caused failures cascading through `geo-svc`, `tax-svc`, and `disputes-svc` to the edge services.
   - **Fix**: Reverted the live config change (`cfg-38`) on `labels-svc`, restoring the correct token scope and dropping error rates back to the baseline.

The final 45+ minutes of the shift ran with 0 alerts and stable baseline metrics across all customer-facing edge services!
