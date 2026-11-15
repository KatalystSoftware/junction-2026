# r16-l4-s200001-nemotron-super-022622/seed-200001__xCewYLN

Level 4, seed 200001, nemotron-super, score as run 0.0. The agent's closing message, verbatim:

Shift complete. Here's the incident summary:

## What was wrong

Two customer-facing edge services were failing:
- **mobile-api** (4% errors, $18,300/min revenue) — failing via `shipping-svc`, which got 429 rate-limit responses from `catalog-db`.
- **partner-api** (~99% errors, $850/min) — failing via `push-svc` ← `address-svc` ← `identity-svc` ← `giftcards-svc` ← `ranking-svc`, which was stuck in a severe overload retry storm (cpu 0.99, 72% retries, shedding load).

## Actions taken
- Reverted `catalog-db` config `cfg-14` (`beta_cohort_pct 0→1`) — did **not** resolve shipping-svc's 429s.
- `ranking-svc`: scaled 4→8→16 and restarted — broke the retry storm; recovered to ~0% error (cpu 0.51, retries 0).
- `push-svc`: restarted (cleared OOM, mem 0.99→0.5) and scaled 4→8 — broke its retry storm; push-svc itself healthy (cpu 0.41) but still returning 0.81 error because its hard dependency `address-svc` hadn't fully unwound.

## Left unresolved at shift end (minute 120)
- **shipping-svc / mobile-api**: still 0.04 errors ($732/min) — the catalog-db config revert wasn't the fix; root cause (likely `shipping-svc`'s recent deploy or a persistent rate limit) was never confirmed.
- **partner-api**: still ~0.81 errors ($694/min) — `push-svc` recovered but `address-svc`/identity chain hadn't fully cleared before time ran out.

## What would be needed with more time
- Restart/unwind `address-svc` → `identity-svc` → `giftcards-svc` to clear the remaining cascade behind partner-api.
- For shipping-svc: rollback `shipping-svc` deploy `v127` or further investigate `catalog-db` rate limiting (the config revert was insufficient).

Total avoidable cost was reduced by fixing ranking-svc/push-svc, but mobile-api and the tail of partner-api kept draining revenue through the end of the shift.
