# r16-l4-s200013-nemotron-super-023218/seed-200013__PRHrkkX

Level 4, seed 200013, nemotron-super, score as run 0.1986. The agent's closing message, verbatim:

Shift complete. All edge services are healthy (0% or 0.04% error, well under the 1% fault threshold).

**Root causes found and fixed:**

| Service | Root Cause | Mitigation |
|---|---|---|
| `cart-svc` | Memory bloat/OOM from retry storm | `restart` + `scale` to 12 |
| `limits-svc` | Retry storm (CPU overload) | `scale` to 24 |
| `ledger-svc` | Config `cfg-43` removed `orders.write` scope (`PermissionDenied`) | `revert_config` + `scale` to 12 |
| `sitemap-svc` | Config `cfg-31` rate limit change | `revert_config` |

**Cascade resolved:**
- `ledger-svc` (hard dep) → `limits-svc` → `web-storefront`/`mobile-api` (95% → 0%)
- `sitemap-svc` → `subscriptions-svc` → `partner-api` (4% → 0.04%)
- `cart-svc` → `admin-portal` (49% → 0.04%)

**Not acted on:** `audit-svc` TLSv1.3 deploy (`v73`) — rollback would cost ~$43k in temporary 30% failure vs ~$16k from leaving the 4% partner-api error, so it was correctly left alone. (partner-api recovered anyway via the sitemap-svc revert.)
