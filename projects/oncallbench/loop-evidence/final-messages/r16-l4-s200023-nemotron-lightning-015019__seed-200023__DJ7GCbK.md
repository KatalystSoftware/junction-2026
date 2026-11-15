# r16-l4-s200023-nemotron-lightning-015019/seed-200023__DJ7GCbK

Level 4, seed 200023, nemotron-lightning, score as run 0.0. The agent's closing message, verbatim:

**Shift over at minute 120.** Here's a recap of the incident:

### What went wrong
- **events-queue** was the root bottleneck: cpu 0.99, error_rate ~0.94, very high retry_share 0.73
- This cascaded: events-queue → couriers-svc (hard dep) → limits-svc (hard dep) → admin-portal (edge, $450/min)
- **notifications-svc** had intrinsic error_rate ~0.046, propagating hard to partner-api ($10,300/min) and mobile-api ($400/min)
- **cart-svc** error_rate ~0.084 was the main cause of web-storefront errors ($800/min)

### Mitigations applied (5 actions)
1. **`revert_config` limits-svc** - WASTED ($10,000). The cfg-49 "rotate credentials" at minute -14 wasn't the root cause.
2. **`restart` couriers-svc** - Partial benefit, temporarily broke the cascade.
3. **`scale` events-queue 8→12** - Partial benefit, modest error rate improvement. Cost $540.
4. **`restart` notifications-svc** - Mixed; caused temporary error rate spike then recovery.
5. **`throttle` events-queue 50%** - Helped cpu (0.99→0.89) and retry_share (0.73→0.71); explicitly never wasted.

### Final error rates
- admin-portal: 0.9771, partner-api: 0.043, web-storefront: 0.0819, mobile-api: 0.043

### Key takeaway
The $10,000 wasted config revert was the dominant cost error. Addressing the events-queue overload directly (earlier scale or throttle) without the wasted mitigation would have minimized the shift cost.
