# r16-l4-s200022-nemotron-super-verda-033404/seed-200022__DZ2e2sF

Level 4, seed 200022, nemotron-super-verda, score as run 0.0. The agent's closing message, verbatim:

The shift is over. Here's a summary of the incident:

## What I found and fixed

**Root cause 1: `profile-db` primary node unreachable** (data tier)
- Logs showed "primary node unreachable, write rejected" — not overload
- `failover` fixed it; profile-db recovered to 0.04% error
- This unblocked: `bundles-svc` → `partner-api` chain

**Root cause 2: `bundles-svc` OOM kills** (app tier)
- 10 out-of-memory kills, 99% mem — `restart` cleared it
- bundles-svc recovered to 0.03% error

## What I couldn't fully resolve in time

**`emails-svc`: 76% error, 99% cpu, retry storm** → causing `partner-api` at 76% ($850/min)
- Discovered at minute 117 with only ~3 minutes left; no time to mitigate
- Depends on `push-svc` (soft) and `events-queue` (soft)

**`currency-svc`: steady 4.2% error** → causing `admin-portal` at 4.3% ($16,800/min)
- Connection pool timeout to `promo-cache`, but promo-cache looked healthy
- Tried: restart, rollback (v39 deploy), scale to 8 replicas — none resolved it
- `notifications-svc` restart also didn't help (the issue was upstream in currency-svc)

## Actions taken
| Service | Mitigation | Result |
|---|---|---|
| profile-db | scale 4→8, then 8→16 | Reduced CPU but not errors |
| profile-db | failover | ✅ Fixed (primary node unreachable) |
| bundles-svc | restart | ✅ Fixed (OOM) |
| currency-svc | restart, rollback, scale | ❌ Still 4.2% |
| notifications-svc | restart | ❌ Didn't address root cause |

The two remaining faults (`emails-svc` and `currency-svc`) were identified too late in the shift to mitigate.
