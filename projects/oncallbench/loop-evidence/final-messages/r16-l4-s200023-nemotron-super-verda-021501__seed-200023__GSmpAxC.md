# r16-l4-s200023-nemotron-super-verda-021501/seed-200023__GSmpAxC

Level 4, seed 200023, nemotron-super-verda, score as run 0.0. The agent's closing message, verbatim:

The shift is over. Here's the incident summary:

## What I fixed

| Service | Problem | Mitigation | Result |
|---------|---------|-----------|--------|
| `events-queue` | Data primary node gone (logs: "primary node unreachable") + retry-storm overload | `failover`, then `scale→20` to drain retry storm, `scale→8` | Recovered, healthy |
| `vouchers-svc` | Retry-storm overload (triggered by my `rollback v175`, rps 1532→3040, cpu 0.99) | `scale→20` | Recovered, healthy |
| `notifications-svc` | 4.4% error (from vouchers-svc data issue) | Resolved once vouchers-svc recovered | Recovered, 0.003% |
| `partner-api` | 4.3% @ $10,300/min (via notifications-svc) | Fixed via above | **0.0%** |
| `mobile-api` | 4.3% @ $400/min (via notifications-svc) | Fixed via above | **0.0%** |
| `web-storefront` | 8.4% → self-resolved | — | **0.0%** |

## What remained broken

`admin-portal` stayed at **92.3%** error for the rest of the shift. Root cause chain I never got to finish:

`address-svc` (71%, **its own fault** — not overloaded, both deps `sms-svc`/`profile-db` healthy) → `couriers-svc` (71%, hard dep) → `limits-svc` (92%, retry-storm overload) → `admin-portal` (92%).

I identified `address-svc` as the culprit at minute ~105 but the shift ended (minute 120) before I could check its logs/changes and apply a mitigation.

## Score impact

The high-revenue services (`partner-api` $10,300/min, `web-storefront`, `mobile-api`) were fully recovered, which avoids the largest losses. `admin-portal` ($450/min at ~92% = ~$414/min) stayed broken for most of the shift, which is the main remaining cost. I also incurred a temporary setback when the `vouchers-svc` rollback triggered a retry storm (then corrected with `scale`).
