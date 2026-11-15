# r16-l4-s200015-nemotron-super-verda-020725/seed-200015__PXAe3hp

Level 4, seed 200015, nemotron-super-verda, score as run 0.0. The agent's closing message, verbatim:

The shift has ended. Here's a summary of the incident response:

## What happened

**Faults identified and fixed:**
1. **checkout-svc** — Deploy v85 ("weekly release" at minute -16) removed the `orders.write` scope, causing 83% error rate. Fixed by rolling back v85 + scaling 4→8 replicas. Fully recovered (~0.001% error).
2. **cascade recovery**: recommendations-svc and cart-svc recovered as downstream effects once checkout-svc was fixed and scaled.

**Faults not fully resolved:**
3. **ranking-svc** — Steady 4% error rate (from config `cfg-11` "update allowlist" at minute -39). Reverted the config and restarted, but the 4% persisted. This kept **web-storefront** (15700/min revenue) and **admin-portal** at 4% error.
4. **banners-svc** — 51% error rate since minute 64 (missed entirely). It's a hard dependency of **partner-api**, contributing to partner-api's continued 87% error alongside cart-svc's overload.

## Actions taken
| Action | Service | Result |
|--------|---------|--------|
| revert_config | checkout-svc (cfg-40) | No effect alone |
| revert_config | ranking-svc (cfg-11) | No effect on 4% error |
| restart | checkout-svc | No effect alone |
| rollback | checkout-svc (v85) | Fixed root cause |
| scale | checkout-svc 4→8 | Cleared overload, recovered |
| scale | ranking-svc 3→6 | Cleared overload, but 4% error remained |
| scale | cart-svc 4→8 | Reduced error from 0.96→0.47 |
| restart | cart-svc | In progress at shift end (completes min 121) |

**Missed:** banners-svc fault (0.51 error since minute 64) — a separate cause of partner-api failures that was never investigated.
