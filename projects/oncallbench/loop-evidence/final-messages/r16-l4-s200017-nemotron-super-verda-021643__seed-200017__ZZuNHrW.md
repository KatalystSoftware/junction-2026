# r16-l4-s200017-nemotron-super-verda-021643/seed-200017__ZZuNHrW

Level 4, seed 200017, nemotron-super-verda, score as run 0.0. The agent's closing message, verbatim:

The shift is over (minute 120). Here's the incident summary:

## What I did

1. **Minute 29**: Rolled back `ledger-svc` v80 — the deploy changed `deadline = budget_ms / 1000` to `/ 10000` (10x shorter), causing timeouts, a retry storm (rps 400→1442), and cpu 0.99. This was the root of the `mobile-api`/`web-storefront` cascade.

2. **Minute 70**: Scaled `ledger-svc` to 6 replicas — the rollback alone didn't break the self-sustaining retry storm (rps stayed at 847, cpu 0.99). Scale gave it capacity to drain the backlog. ledger-svc fully recovered (0.003 error, cpu 0.41). This recovered `web-storefront` and `partner-api` to 0.0 error.

3. **Minute 71**: Restarted `recommendations-svc` — steady 4.2% error causing `admin-portal`'s 4% loss (852/min, the biggest). Restart didn't help.

4. **Minute 85**: Restarted `suggest-svc` — stuck (cpu/mem 0.99, 10 restarts/30m). Recovered (0.002 error), which recovered `checkout-svc`.

5. **Minute 99**: Rolled back `profile-db` v116 — changed `row.get("currency","EUR")` to `row["currency"]`, causing KeyError on 4% of requests (found in logs). **Mistake**: the rollback caused 30% failures during its run (minutes 99–104), which triggered a new retry storm on `profile-db` (rps 900→1944, cpu 0.99, error 0.41). I didn't have time to scale it to break the storm.

6. **Minute 106**: Restarted `labels-svc` — stuck at 0.88 error despite healthy `checkout-svc`. Restart didn't resolve it.

## Final state (minute 120)

| Service | Error Rate | Revenue/min | Loss/min |
|---|---|---|---|
| web-storefront | 0.0 | 300 | 0 |
| mobile-api | ~0.88 | 600 | ~528 |
| partner-api | 0.0 | 550 | 0 |
| admin-portal | ~0.42 | 21,300 | ~8,946 |

**Total loss: ~9,474/min** at shift end. `admin-portal` got worse (0.04→0.42) because the `profile-db` rollback disturbance triggered a retry storm I couldn't break in time. `mobile-api` remains blocked by stuck `labels-svc`.

The key lesson: rolling back a service causes 30% in-flight failures, which can trigger a retry storm in its callers — scale proactively to prevent it (as I did successfully for `ledger-svc`, but too late for `profile-db`).
