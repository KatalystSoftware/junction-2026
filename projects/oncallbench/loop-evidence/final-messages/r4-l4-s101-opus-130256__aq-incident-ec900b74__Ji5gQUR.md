# r4-l4-s101-opus-130256/aq-incident-ec900b74__Ji5gQUR

Level 4, seed 101, opus, score as run 0.5728, regraded 0.5728. The agent's closing message, verbatim:

I found three causes and fixed all of them. At the end of the shift all four customer-facing services were at 0% errors, with no throttles on. I don't have the final cost figure; the simulator works it out by replaying my actions.

**1. partner-api (highest revenue, about $18k/min) at about 4.7% errors.** I followed the errors down the chain partner-api → search-svc → returns-svc → quotes-svc. A quotes-svc deploy (v59, minute -40) hard-coded its database connection pool to 4, so calls from returns-svc were timing out.
- I first scaled quotes-svc from 6 to 12 replicas. It was running near capacity, and without the headroom the failures during the rollback would have set off a retry storm.
- Then I rolled back v59. partner-api has been at 0% since about minute 50.
- I set quotes-svc back to 6 replicas afterwards.

**2. mobile-api at about 97% errors.** sms-svc was stuck in a retry storm after a deploy (v156, minute -8) that changed its message format from v2 to v3. That pushed pricing-svc, which already had a retry storm of its own from minute -25, further into overload.
- I throttled pricing-svc to cut the load and rolled back v156.
- When I lifted the throttle, pricing-svc fell straight back into overload. Its real traffic is now larger than 6 replicas can handle, and sms-svc was still overloaded too.
- I scaled pricing-svc from 6 to 12 and sms-svc from 8 to 16, throttled pricing-svc briefly to clear the retries, then turned the throttle off. mobile-api has been at 0% since about minute 84.

**3. web-storefront at about 99% errors, a new fault at minute 47.** An address-svc config change (cfg-20) removed the `currency` field from its price fields. I reverted it and the storefront recovered by about minute 69.

Costs and follow-ups:
- **Errors cost money while I worked:** partner-api lost about $850/min until minute 50, and mobile-api was down for most of the shift until minute 84.
- **Extra replicas:** pricing-svc and sms-svc stayed scaled up to the end, at roughly $36/min, to keep them from overloading again. sms-svc would sit around 80% CPU at its normal 8 replicas.
- **Wasted actions:** none. Every rollback and the config revert went to a service with a confirmed bad change. quotes-svc also had a config change at minute -40, but it looked harmless and I left it alone.
- **Not fixed:** the code in returns-svc, sms-svc and address-svc still needs proper fixes before those changes go out again. pricing-svc needs more capacity for its current traffic.
