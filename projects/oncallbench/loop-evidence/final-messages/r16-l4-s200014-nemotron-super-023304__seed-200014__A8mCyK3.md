# r16-l4-s200014-nemotron-super-023304/seed-200014__A8mCyK3

Level 4, seed 200014, nemotron-super, score as run 0.0. The agent's closing message, verbatim:

Shift over. Final state:

| Service | Error Rate | Revenue/min | Loss/min |
|---------|-----------|-------------|----------|
| admin-portal | 0% | $850 | $0 ✓ fixed |
| mobile-api | 12% | $450 | $54 |
| web-storefront | 64% | $450 | $288 |
| partner-api | 72% | $18,700 | ~$13,426 |

**What I did:**
1. `rollback risk-svc v59` (leaking build, 99% mem) — partially fixed web-storefront (99%→64%); retry storm still draining.
2. `rollback suggest-svc v52` (rate limiter `/1000` bug) — partially fixed mobile-api (28%→12%).
3. `revert_config address-svc cfg-59` — fixed admin-portal (77%→0%).
4. `rollback events-queue v58` (TLSv1.2→v1.3 breaking flags-svc) — **correct root cause for partner-api, but started at minute 116 with a 6-minute rollback that completes at 121 (after shift end).** It made partner-api worse (4%→72%) during the rollout without fixing it in time. This was a misjudged action given the clock.

**Missteps:** `revert_config flags-svc cfg-30`, `rollback address-svc v87`, and `rollback flags-svc v86` were wrong changes ($10,000 each wasted). The events-queue rollback was the right fix but too late — partner-api was steady at 4% before I touched it.

The shift is complete; nothing further can be done.
