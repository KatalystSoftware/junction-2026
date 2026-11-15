# r16-l4-s200002-nemotron-super-022624/seed-200002__rXLsDWo

Level 4, seed 200002, nemotron-super, score as run 0.0. The agent's closing message, verbatim:

The shift is over (minute 120). Here's the incident summary:

## What I found and fixed

| # | Service | Root cause | Fix | Result |
|---|---------|-----------|-----|--------|
| 1 | `profile-svc` | Bad deploy `v94` (TLS min 1.2→1.3 broke clients) | `rollback v94` | `web-storefront` + `mobile-api` recovered (~90%→0) |
| 2 | `thumbnails-svc` | Bad config `cfg-39` (`wire_schema v2→v3` protocol break) | `revert_config cfg-39` | `web-storefront` + `partner-api` recovered (66%→0) |
| 3 | `couriers-svc` | Retry-loop overload from `profile-svc` (callers_retry=3) | `scale` to 12 replicas | Loop broke, `profile-svc` healthy |

## What remained broken at shift end

- **`admin-portal` at 4%** (~$816/min): caused by `experiments-svc`, which `seo-svc` was rate-limiting (429s). Root cause: `seo-svc` deploy `v30` changed `refill = rate * elapsed` → `/ 1000`, starving the rate-limiter bucket. I tried scaling `seo-svc` (no effect — rate limiter is shared, not per-replica). `rollback` was too costly: 30% failure during the 6-min rollback would put `admin-portal` at 30% (~$36,720), worse than leaving it at 4%. Left unfixed.
- **`web-storefront` + `mobile-api` at 85%** (final minutes): I scaled `couriers-svc` back to 4 replicas (completing minute 114) while its load was still elevated (~897 rps vs ~476 capacity at 4 replicas). It re-overloaded, and `profile-svc` (hard dep on `couriers-svc`) failed again, cascading to both edge services.

## What I'd do differently
- Don't scale `couriers-svc` back until its rps drains to normal (~335); it was still at ~897 when I scaled down.
- For `seo-svc`, the rate-limiter bug needs a `rollback` of `v30`, but only if the 6-min 30% failure window is acceptable given remaining shift time — here it wasn't.
