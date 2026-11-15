# r16-l4-s200019-nemotron-super-023504/seed-200019__9p4ZuKx

Level 4, seed 200019, nemotron-super, score as run 0.0. The agent's closing message, verbatim:

The shift is over. Final results:

- **web-storefront**: 0% errors ✅ (fixed via giftcards-svc rollback v110)
- **mobile-api**: 86.5% errors ❌ (orders-db → currency-svc → auth-svc chain still broken)
- **partner-api**: 4% errors ❌ (tax-svc still broken)
- **admin-portal**: 86% errors ❌ (same chain as mobile-api)

I fixed one of four failing edge services. The root causes for `orders-db` and `tax-svc` were never correctly identified — I tried `revert_config`, `restart`, and `scale` on orders-db, and `rollback` and `restart` on tax-svc, none of which resolved their underlying issues. Also wasted ~$30K on incorrect mitigations (revert_config on orders-db cfg-43, rollback on tax-svc v142, revert_config on giftcards-svc cfg-40).

The giftcards-svc fix worked: rolling back v110 (the `row["currency"]` deploy) restored web-storefront. But orders-db and tax-svc remain unresolved — orders-db may have needed `failover` (primary node gone) rather than the changes I attempted, and tax-svc's 4% error rate persists despite reverting its only recent deploy.
