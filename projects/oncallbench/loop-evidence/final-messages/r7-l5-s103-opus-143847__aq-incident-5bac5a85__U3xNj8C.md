# r7-l5-s103-opus-143847/aq-incident-5bac5a85__U3xNj8C

Level 5, seed 103, opus, score as run 0.5466. The agent's closing message, verbatim:

The shift is over. All four customer-facing services ended at a 3.7% error rate, which looks like their normal background level. admin-portal (by far the biggest earner at $18,300/min) sat at 3.7% for the whole shift and was never hit by any of the faults. I didn't calculate the final cost.

**Faults found and fixed:**

1. **pricing-svc, bad deploy v105** (started at −14): the deploy cut the call deadline by a factor of 10 (`budget_ms / 10000`), so calls timed out ("DeadlineExceeded"). Errors reached mobile-api. I rolled it back at minute 18.
2. **quotes-svc, bad config cfg-6** (started at −23): it changed `rules_source` to `[features, r0.features]`, which made the file quotes-svc publishes bad. payments-svc loads that file, so it failed, and callers retrying the failures overloaded it (CPU at 0.99, rps up from about 1,100 to 6,000). This hit web-storefront and mobile-api. partner-api failed from the same cause, starting around minute 18 (probably through images-svc, which depends on thumbnails-svc, which also loads the file). I reverted the config at minute 35. By minute 41 everything was back to normal.
   - At minute 7 I scaled payments-svc from 3 to 12 replicas to absorb the retry load. That brought CPU down to 0.8, but errors stayed around 62% until the bad file was fixed. At minute 44 I scaled it back to 4, not 3, because at 3 replicas its normal CPU is about 0.78, which leaves little headroom. That one extra replica costs about $3/min.
3. **labels-svc, bad config cfg-38** (a new fault at minute 55): it removed `orders.write` from `token_scope`, so its calls failed with PermissionDenied. That broke geo-svc, which broke tax-svc and disputes-svc, putting web-storefront and mobile-api at about 53% errors. I reverted it at minute 74, and by minute 77 everything was back to normal.

**Left alone on purpose:**
- **status-page alerts:** it's hosted outside our estate.
- **experiments-svc high CPU:** no customer impact traced back to it.
- **pricing-svc cfg-23 and quotes-svc v67:** changes made at the same time as the real causes, but their diffs showed nothing harmful.

None of the mitigations were spent on a service that didn't need one. The edge services stayed at their normal level from minute 77 to the end of the shift.
