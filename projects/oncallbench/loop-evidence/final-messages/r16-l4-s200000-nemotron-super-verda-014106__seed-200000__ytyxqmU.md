# r16-l4-s200000-nemotron-super-verda-014106/seed-200000__ytyxqmU

Level 4, seed 200000, nemotron-super-verda, score as run 0.0. The agent's closing message, verbatim:

The shift is over. Final state:

| Service | Error Rate | Revenue/Min | Lost/Min |
|---------|-----------|-------------|----------|
| web-storefront | 70% | $600 | ~$422 |
| mobile-api | 80% | $500 | ~$399 |
| partner-api | 40% | $19,000 | ~$7,619 |
| admin-portal | 0% | $450 | $0 |

**What I fixed:**
- **audit-svc**: Rolled back bad deploy `v44` (rate limiter `refill / 1000` bug) + scaled to break retry storm → fully recovered
- **checkout-svc**: Reverted bad config `cfg-52` (`entry_ttl_s: 600→1` causing StaleEntry errors) → root cause fixed, retry storm persists
- **stock-svc**: Rolled back bad deploy `v27` (`row.get→row["currency"]` KeyError) → root cause fixed, retry storm persists
- **consent-svc**: config revert didn't help — the real cause was stock-svc's deploy

**What ran out of time:** Scales on limits-svc, checkout-svc, and stock-svc were started at minutes 118-120 but complete at 121-123 — after the shift ended at minute 120. The retry storms on those services never broke during the shift.

Key lesson: retry storms persist after root causes are fixed and need active intervention (scale or throttle) to break. I should have started scaling earlier (around minute 101 when audit-svc recovered) rather than spending time investigating.
