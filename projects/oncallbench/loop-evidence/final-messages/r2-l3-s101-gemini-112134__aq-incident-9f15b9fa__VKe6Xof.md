# r2-l3-s101-gemini-112134/aq-incident-9f15b9fa__VKe6Xof

Level 3, seed 101, gemini, score as run 0.4101. The agent's closing message, verbatim:

I have finished the on-call shift and mitigated the incidents. Here is a summary of the actions taken:

1. **`mobile-api` Incident (~$850/min at risk)**
   - **Symptom:** `mobile-api` had an elevated error rate.
   - **Investigation:** We identified that its hard dependency, `pricing-svc`, had a massive CPU spike to 0.99 with an increase in RPS, along with its own dependency, `sms-svc`, failing heavily.
   - **Mitigation:** 
     - Scaled `pricing-svc` from 6 to 12 replicas to handle the traffic load, dropping CPU back to safe levels.
     - Rolled back a recent bad deploy (`v156`) on `sms-svc` that had caused its error rate to jump.
   - **Result:** Error rates on `mobile-api` immediately dropped to zero.

2. **`partner-api` Incident (~$9,100/min at risk)**
   - **Symptom:** `partner-api` was returning errors.
   - **Investigation:** This was traced down through `search-svc` to `returns-svc`, which was having connection timeout issues (`pool.acquire() exceeded 200ms`). The root cause was actually in `quotes-svc`, which had a bad config change (`cfg-15`) reducing its `db_pool_size` from 40 to 4, starving the connection pool on the caller side.
   - **Mitigation:** Reverted the `cfg-15` config on `quotes-svc`. (A rollback on `returns-svc` was also tried initially). 
   - **Result:** The connection pool recovered, and `partner-api` errors dropped to zero.

3. **`web-storefront` Incident (~$500/min at risk)**
   - **Symptom:** Around minute 47, `web-storefront` began failing heavily.
   - **Investigation:** This correlated with a config change on `address-svc` (`cfg-20`) deployed right at minute 47 that drastically spiked error rates across the chain.
   - **Mitigation:** Immediately reverted config `cfg-20` on `address-svc`.
   - **Result:** Error rates on `web-storefront` recovered entirely.

4. **`cart-svc` High CPU Alert**
   - **Symptom:** Constant CPU alert at 0.99.
   - **Investigation:** Logs indicated a normal expected background process (`"scheduled job nightly-rollup is running"`). As `cart-svc` isn't attached to any revenue-generating edge service and was maintaining an acceptable error rate (< 0.005), this was deemed a red herring. It was ignored after a quick triage to avoid wasting money on unneeded capacity.

The shift is now complete, and the estate is fully healthy.
