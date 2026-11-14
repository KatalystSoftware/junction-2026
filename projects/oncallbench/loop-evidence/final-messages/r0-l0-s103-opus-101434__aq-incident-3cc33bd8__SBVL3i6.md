# r0-l0-s103-opus-101434/aq-incident-3cc33bd8__SBVL3i6

Level 0, seed 103, opus, score as run 1.0. The agent's closing message, verbatim:

I rolled back a bad deploy on `limits-svc` at minute 0, and the shop was back to 0% errors by minute 7. It stayed clean until the shift ended at minute 120.

**Cause:** At minute −19, `limits-svc` went live with build v142 ("refactor request handlers"). Its logs showed about 312k "unhandled exception in request handler" errors, which first appeared in v142, and its error rate went from about 0.3% to 80%.

**How it spread:** `identity-svc` and `inventory-svc` depend hard on `limits-svc`, so both failed at the same 80%. `checkout-svc` failed through `inventory-svc`. Both shop-facing services call all three, so they were losing about 99.2% of requests, which matches this one fault alone.

**What I did:**
- **Rollback of `limits-svc`** (minute 0 to 6). This was the only mitigation I applied, so there were no wasted-mitigation charges and no extra replica costs.
- **Checked for other causes:** `risk-db` and `users-db` (the data services), `images-svc` and recent changes on `checkout-svc` all looked normal.
- **Monitored until the end:** no alerts after the rollback and no sign of the fault coming back.

**Approximate lost revenue:** about $7.9k. That is roughly six minutes at 99% errors during the rollback, at $1,250/min across both services. The 19 minutes before the page fall outside the shift.
