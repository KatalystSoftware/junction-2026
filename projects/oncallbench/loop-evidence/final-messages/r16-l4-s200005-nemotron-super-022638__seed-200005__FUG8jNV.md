# r16-l4-s200005-nemotron-super-022638/seed-200005__FUG8jNV

Level 4, seed 200005, nemotron-super, score as run 0.0. The agent's closing message, verbatim:

The shift has ended (minute 120). Here's a summary of the incident response:

## Root causes found & mitigated

| # | Service | Root cause | Mitigation | Result |
|---|---------|-----------|------------|--------|
| 1 | `events-queue` | Data-service primary node unreachable (`primary node unreachable, write rejected`) | `failover` → then `scale` 6→12 to break retry storm | Fixed (0.001%) |
| 2 | `profile-svc` | Bad deploy `v75`: `deadline = budget_ms/1000` → `/10000` (10x shorter, causing timeouts) | `rollback` v75 → then `scale` 8→16 to break rollback-induced retry storm | **web-storefront 0%** |
| 3 | `returns-svc` | Bad config `cfg-35`: `entry_ttl_s 600→1` (`StaleEntry: ttl elapsed`) | `revert_config` cfg-35 | Root fixed, retry storm still draining at shift end |

## Outcome
- **web-storefront (26500/min): 0% errors** — the largest revenue loss eliminated.
- `mobile-api`, `partner-api`, `admin-portal` still recovering (47–99%) at shift end because the `returns-svc` retry storm (`returns-svc → suggest-svc → recommendations-svc → pricing-svc/flags-svc`) hadn't fully drained before minute 120.

Key lessons: the `returns-svc` revert fixed the root cause but the retry storm needed more time (or a scale/throttle) to break — it was still at ~47% error with cpu 0.99 when the shift ended.
