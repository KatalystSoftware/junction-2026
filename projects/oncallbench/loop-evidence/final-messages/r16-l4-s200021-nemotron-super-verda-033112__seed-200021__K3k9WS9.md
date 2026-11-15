# r16-l4-s200021-nemotron-super-verda-033112/seed-200021__K3k9WS9

Level 4, seed 200021, nemotron-super-verda, score as run 0.0. The agent's closing message, verbatim:

The shift is over (minute 120). Here's the incident summary:

## Root causes found & fixed

| # | Service | Fault | Fix | Edge impact |
|---|---------|-------|-----|-------------|
| 1 | `export-svc` | Bad config `cfg-18` (`db_pool_size 40→4`) at m-11 | `revert_config` | mobile-api 50% → 0 |
| 2 | `loyalty-svc` | Bloated/OOM process (memory leak from `v164`) | `restart` | web-storefront/partner-api 76% → 0 |
| 3 | `subscriptions-svc` | Bad deploy `v118` removed `orders.write` scope → `PermissionDenied` | `rollback v118` | admin-portal 4.5% → 0 |
| 4 | `translations-svc` | Bad deploy `v176` (`KeyError: 'currency'`) at m+70 | `rollback v176` | web-storefront/partner-api 76% → 0 |

I also broke retry-storm overloads on `loyalty-svc` and `subscriptions-svc` with temporary scale-ups, then scaled both back to normal replica count (free).

## Final state at minute 120
- **mobile-api: 0.0** ✅
- **admin-portal: 0.0** ✅
- **web-storefront: 0.89** ❌
- **partner-api: 0.89** ❌

The `loyalty-svc` memory leak (`v164`) returned; mem hit 0.98 and it OOM'd just as I restarted it (restart completes at m121, just after shift end), taking web-storefront and partner-api down in the final minutes. Restarting loyalty earlier (when the mem alert fired at m106) would have prevented this last relapse.

No throttles left on. All other services healthy.
