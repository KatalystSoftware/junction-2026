# r16-l4-s200003-nemotron-super-022628/seed-200003__HxAGEzU

Level 4, seed 200003, nemotron-super, score as run 0.0. The agent's closing message, verbatim:

The shift is ending (4 minutes left). Here's the final state:

**Resolved:**
- **web-storefront**: 0.0 (was 0.90) — fixed via seo-svc scale + import-svc & risk-svc rollbacks
- **partner-api**: 0.0 (was 0.24→0.86) — fixed via import-svc & risk-svc rollbacks
- **mobile-api**: 0.0 (healthy throughout)

**Root causes fixed:**
1. **import-svc** — memory leak/OOM from deploy v144 → rollback
2. **seo-svc** — retry-storm overload → scale to 24 replicas
3. **risk-svc** — bad deploy v17 ("add tracing spans") at minute 59 caused `pool.acquire` timeouts → rollback (this also fixed the sessions-svc → geo-svc cascade hitting web-storefront + partner-api)

**Still unresolved:**
- **admin-portal**: 0.043 error, caused by **search-svc** (0.0445) with `StaleEntry: ttl elapsed before first read` errors against healthy bundles-svc. Tried: rollback v113, rollback v112, restart ×2 — none removed the base fault. Remaining cost: ~$834/min for the final minutes.

All mitigations complete; no operations in progress; no throttles.
