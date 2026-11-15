# r16-l4-s200022-nemotron-lightning-015017/seed-200022__MbWvZgx

Level 4, seed 200022, nemotron-lightning, score as run 0.0. The agent's closing message, verbatim:

Shift ended at minute 120. Here's a summary of the incident and actions:

**Root causes identified and mitigated:**

| Service | Issue | Mitigation | Result |
|---------|-------|------------|--------|
| **bundles-svc** | cpu 0.99, mem 0.99, error_rate 0.96, retry_share 0.7, 3x rps spike | Scale 6→12 replicas | error_rate → 0.78, cpu → 0.82 |
| **profile-db** | cpu 0.99, error_rate 0.82 | Scale 4→12 replicas | error_rate → 0.53, cpu → 0.66 |
| **ledger-svc** | error_rate 0.82 after config change cfg-25 (burst_allowance 200→220, conn_idle 300→240) | revert_config | error_rate → 0.53 |
| **emails-svc** | Suddenly broke at minute 56: error_rate 0.76, cpu 0.99, rps 333→1067 | Scale 8→16 replicas | error_rate → 0.40 |

**Final edge service state:**
- web-storefront: error_rate 0.0 (revenue 800/min) — healthy
- mobile-api: error_rate 0.0 (revenue 700/min) — healthy  
- partner-api: error_rate 0.86 (revenue 850/min) — persistent, from dependency failures
- admin-portal: error_rate 0.04 (revenue 16800/min) — chronic low-level issue

**Cost drivers:** Primary was partner-api's 0.86 error_rate sustained over 120 min. Extra replica costs from 3 scale operations (bundles-svc +6, profile-db +8, emails-svc +8 replicas). No wasted mitigations applied.

The key lesson: monitor dependency health proactively, as a fault in one app service (bundles-svc) cascades to edge services (partner-api), and new faults can emerge mid-shift (emails-svc).
