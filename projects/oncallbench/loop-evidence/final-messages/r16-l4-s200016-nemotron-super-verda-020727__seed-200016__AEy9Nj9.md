# r16-l4-s200016-nemotron-super-verda-020727/seed-200016__AEy9Nj9

Level 4, seed 200016, nemotron-super-verda, score as run 0.0. The agent's closing message, verbatim:

The shift is complete. Here's a summary of what I found and did:

## Root causes identified and fixed

1. **media-store** (data) — primary node unreachable → **failover**. This was the root of the `address-svc` → `cart-svc/tax-svc` cascade driving `mobile-api` and `admin-portal` to ~90% errors.

2. **payments-svc** — bad deploy `v103` changed `row.get("currency","EUR")` to `row["currency"]` (KeyError) → **rollback**. This was the root of `fraud-svc` → `recommendations-svc` → `web-storefront` (the largest bleed, ~668/min). The rollback itself triggered a retry storm that I cleared with a temporary scale-up, then scaled back to normal (free).

3. **flags-svc** — bad deploy `v135` hardcoded connection pool to size 4 (`Pool(size=4)`) → **rollback**. This caused pool exhaustion driving `translations-svc` → `mobile-api`.

4. **address-svc** — overload from the cascade → temporary scale to 16 replicas (needed for its genuine elevated load; left in place since scaling back would re-overload it).

## Final state
All edge services near 0–2% error at shift end:
- web-storefront: 0%
- partner-api: 0%
- mobile-api: ~2.2%
- admin-portal: ~2.2%

The largest revenue losses (web-storefront at 16700/min) were stopped early. Only a small residual cost remains from address-svc's extra replicas and the last few minutes of ~2% edge errors.
