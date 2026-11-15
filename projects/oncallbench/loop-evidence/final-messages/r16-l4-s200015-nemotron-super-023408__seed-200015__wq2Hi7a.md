# r16-l4-s200015-nemotron-super-023408/seed-200015__wq2Hi7a

Level 4, seed 200015, nemotron-super, score as run 0.0. The agent's closing message, verbatim:

Shift complete. Summary of the incident:

**Root causes found & fixed:**
1. **checkout-svc** — bad deploy `v85` (weekly release, min -16) caused 83% errors → **rollback**. Fixed the checkout→recommendations→cart→partner-api chain.
2. **cart-svc** — bloated memory/OOM from retry storm → **restart** + **scale to 8**. Fully recovered (0.0002%).
3. **sessions-cache** — overloaded (cpu 0.86) causing ranking-svc connection-pool timeouts → **scale to 6**. This was the root cause of ranking-svc's 4.3% errors.
4. **ranking-svc** — stuck pool + retry storm from notifications-svc → **restart** + **scale to 6**. Recovered to 0.041%, fixing web-storefront and admin-portal.

**Wasted mitigations:** `revert_config` on checkout-svc (cfg-40) and ranking-svc (cfg-11) — both were wrong guesses (the real causes were a deploy and a stuck pool, respectively).

**Remaining at shift end:** **banners-svc** at 51% (from a minute-64 deploy/config change) → partner-api at 51%. No time left to apply a mitigation before minute 120.

web-storefront (0.04%, $15.7k/min) and admin-portal (0.04%) are healthy; mobile-api (0%) healthy; partner-api (51%, $800/min) still degraded.
