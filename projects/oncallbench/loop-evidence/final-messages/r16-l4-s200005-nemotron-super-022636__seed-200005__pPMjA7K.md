# r16-l4-s200005-nemotron-super-022636/seed-200005__pPMjA7K

Level 4, seed 200005, nemotron-super, score as run 0.0. The agent's closing message, verbatim:

The shift has ended (minute 120), so no further actions are possible. Here's the incident summary.

## Root causes found

1. **`events-queue` (data)** — primary node unreachable, plus a self-sustaining retry storm (73% retries). Root of the big cascade: `ledger-svc` → and via `recommendations-svc`/`flags-svc` → `media-svc`/`push-svc`/`search-svc`/`tokens-svc`, and via `pricing-svc` → `partner-api`/`admin-portal`/`mobile-api`.
2. **`returns-svc` (app)** — `StaleEntry: ttl elapsed before first read` + retry storm (73% retries, cpu 0.99). Root of a second cascade: `returns-svc` → `suggest-svc` (92%) → `recommendations-svc` (94%) → `flags-svc` (storm) → `media-svc` (100%) → `partner-api`; and `recommendations-svc` → `pricing-svc` (94%) → `partner-api`/`admin-portal`/`mobile-api`. **Never mitigated** — ran out of time diagnosing.
3. **`profile-svc`** — was healthy (0.002% error) but slow (140ms p99) causing `reviews-svc`'s 50ms rpc DeadlineExceeded → `web-storefront` 4% (the largest loss, $26.5k/min). **I misdiagnosed this** and rolled it back; the rollback's 30% failure triggered a retry storm that worsened web-storefront to 42%.

## Actions taken
- `events-queue` failover (min 57–58) — improved it 88%→40%
- `profile-svc` rollback (min 62–67) — **error**, caused the profile-svc storm
- `profile-svc` throttle 25% (min 85) — broke the profile-svc storm
- `events-queue` throttle 25% (min 86) — broke the events-queue storm

## Final state (minute 120)
- `profile-svc` and `events-queue` are healthy but still throttled at 25% (should have removed the throttles) → `web-storefront` at 25% instead of 0%.
- `returns-svc` still in storm → `partner-api` 100%, `admin-portal` ~99.5%, `mobile-api` ~94% remain down.

## Key lessons
- Break retry storms with `throttle` (shed load, not retried) — overload doesn't self-recover.
- `profile-svc` wasn't actually erroring; its latency was the issue. Rolling it back was a wasted-mitigation mistake that created a new storm.
- Always remove throttles once a service recovers (setting back to 0 is free).
- `returns-svc` needed the same throttle treatment as events-queue/profile-svc, but time ran out.
