# r16-l4-s200019-nemotron-super-023502/seed-200019__eMA9f7H

Level 4, seed 200019, nemotron-super, score as run 0.0. The agent's closing message, verbatim:

The shift is over. Here's the final state:

**Final edge service status (minute 120):**
| Service | Error Rate | Revenue/min | Status |
|---|---|---|---|
| web-storefront | 0% | $400 | ✅ Recovered |
| admin-portal | 0% | $550 | ✅ Recovered |
| mobile-api | 4% | $800 | ⚠️ Residual (tax-svc) |
| partner-api | 4% | $29,100 | ⚠️ Unfixed (tax-svc) |

**What was fixed:**
1. **orders-db** — retry storm (CPU 0.99, 72% retries). Scaled 8→32 replicas, broke the retry cycle. This recovered currency-svc → auth-svc → admin-portal.
2. **giftcards-svc** — bad deploy v110 (`row["currency"]` KeyError). Rolled back, recovered giftcards → promotions-svc → web-storefront.
3. **currency-svc** — bad config cfg-59 (credential rotation). Reverted config, dropping errors from 91%→37%.

**Not fixed:**
- **tax-svc** — 4.3% errors persisting the whole shift. My rollback of v142 was wasted (it was just logging changes: `log.info`→`log.debug`). The real cause (likely geo-svc timeout on tax-svc's 50ms RPC budget) was never identified. This leaves partner-api at 4% ($1,164/min) and mobile-api at 4%.

**Wasted mitigations:** tax-svc rollback ($10k) and orders-db failover ($10k, didn't clear the retry storm — scale did).
