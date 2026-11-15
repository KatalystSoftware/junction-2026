# r16-l4-s200000-nemotron-super-022616/seed-200000__wosRZFn

Level 4, seed 200000, nemotron-super, score as run 0.0. The agent's closing message, verbatim:

Shift over (minute 120). Final state:

| Service | Error rate | Revenue/min | Status |
|---|---|---|---|
| partner-api | 0.0 | 19000 | ✅ Recovered (was 4%→spiked to 71% mid-shift, now 0%) |
| admin-portal | 0.0 | 450 | Healthy |
| web-storefront | 0.66 | 600 | Improved (0.92→0.66), residual limits-svc storm |
| mobile-api | 0.98 | 500 | Still failing (checkout-svc throttled 50% + limits-svc) |

**Actions taken:**
1. **Rollback audit-svc (v44)** — rate-limiter bug (`refill = rate * elapsed / 1000`) caused `429 bucket empty`, cascading to limits-svc → web-storefront/mobile-api. Broke the resulting retry storm with throttle, then unthrottled.
2. **Rollback stock-svc (v27)** — response-format change caused consent-svc `KeyError: 'currency'` → partner-api 4%. This fixed partner-api (now 0.0, better than its original 4%), but triggered a stock-svc retry storm that I broke with throttle then unthrottled.
3. **Rollback checkout-svc (v132)** — `StaleEntry` cache bug → 95% error. Storm did not break with throttle; left checkout-svc throttled at 50% (better than 95% failure), protecting mobile-api partially.

**Remaining at shift end:** web-storefront and mobile-api still elevated due to limits-svc residual storm and the checkout-svc throttle. partner-api (the largest revenue source) is fully recovered.
