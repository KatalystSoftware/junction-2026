# r16-l4-s200017-nemotron-super-023444/seed-200017__xVpgz7X

Level 4, seed 200017, nemotron-super, score as run 0.0. The agent's closing message, verbatim:

The shift is over. The ledger-svc restart backfired — it triggered a larger retry storm (error_rate 0.40→0.61, rps 885→1404, retry_share 0.55→0.71), making things worse. Final state:

| Service | Error Rate | Revenue/Min | Loss/Min |
|---------|-----------|-------------|----------|
| admin-portal | 0.04 | 21,300 | 852 |
| mobile-api | 0.99 | 600 | 594 |
| web-storefront | 0.68 | 300 | 204 |
| partner-api | 0.18 | 550 | 101 |

**What I identified and attempted:**
1. **ledger-svc** — Root cause of the mobile-api/partner-api chain. Bad deploy v80 (deadline /1000→/10000) at minute -16 caused timeouts and a retry storm. Rolled back v80 (0.88→0.40) and reverted cfg-51 config, but the retry storm was self-sustaining at cpu 0.99. The restart made it worse by spiking retries. Should have scaled or throttled instead to break the cycle.
2. **recommendations-svc** — Steady 0.04 error rate causing admin-portal's 0.04. Rolled back v108 but it didn't fix it (still 0.04 after rollback). Never found the true root cause.
3. **suggest-svc** — Stuck at mem 0.99, 10 restarts. Never restarted it.

**Key lessons:**
- A retry storm can persist after the original cause is removed; you need to add capacity (scale) or shed load (throttle) to break it, not restart (which amplifies retries).
- Not every alert is a root cause — trace the dependency chain to find the actual source.
- admin-portal's 4% error rate (852 revenue/min lost) was the single biggest cost driver, and I never resolved it.
