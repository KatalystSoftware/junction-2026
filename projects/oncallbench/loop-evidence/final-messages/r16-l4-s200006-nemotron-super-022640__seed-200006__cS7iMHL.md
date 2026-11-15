# r16-l4-s200006-nemotron-super-022640/seed-200006__cS7iMHL

Level 4, seed 200006, nemotron-super, score as run 0.0. The agent's closing message, verbatim:

The shift has ended (minute 120). Here's the incident resolution summary.

## Root causes found & fixed

| # | Service | Root cause | Fix | Result |
|---|---------|-----------|-----|--------|
| 1 | **payments-db** | config `cfg-20`: `db_pool_size 40→4` (connection-pool collapse, cpu 0.99) | `revert_config` (m 23-24), then `scale 4→8` to break retry-stall (m 65-68) | Recovered; rooted out the mobile-api chain |
| 2 | **import-svc** | deploy `v129`: wire schema `v2→v3` (DecodeError in notifications-svc) | `rollback v129` (m 46-51) | Fixed partner-api (0.042→0.0) |
| 3 | **identity-svc** | deploy `v153`: `row.get("currency","EUR")→row["currency"]` (KeyError) → retry storm | `rollback v153` (m 108-113) | Fixed catalog-svc → web-storefront/mobile-api |

Plus scales to break retry-stall overloads: `import-svc 6→12`, `payments-db 4→8`, `identity-svc 4→16`.

## Wasted mitigation
- **notifications-svc rollback (v55)**: I initially attributed partner-api's 4.2% error to notifications-svc (its metrics matched). The rollback didn't fix it — logs showed the real cause was import-svc's v3 schema. This was a wasted mitigation (~$10,000).

## Remaining at shift end
`recommendations-svc` is stuck at cpu 0.99 / error 0.427 (overload, not a retry storm). It drives:
- **thumbnails-svc** 0.427 (hard dep) → **mobile-api** 0.4245
- **thumbnails-svc → auth-svc** (soft, 30%) 0.128 → **admin-portal** 0.1273, **web-storefront** 0.1273

`partner-api` is fully recovered at 0.0 (the largest revenue service, 23300/min).

## Final edge state (minute 120)
- partner-api: 0.0 ✓
- web-storefront: 0.1273
- mobile-api: 0.4245
- admin-portal: 0.1273

The biggest revenue leak (partner-api) was stopped. The residual cost comes from the recommendations-svc overload that ran out of time to address (it needs `scale` to break its overload, or a config/build fix).
