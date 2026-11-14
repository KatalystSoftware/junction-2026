# r4-l4-s101-sonnet-130254/aq-incident-ec900b74__vreuMGJ

Level 4, seed 101, sonnet, score as run 0.2558, regraded 0.2558. The agent's closing message, verbatim:

I fixed two of the three faults, but `partner-api` was still failing about 4.5% of its requests when I ended the shift at minute 120. The cause is probably `quotes-svc`. That is the biggest remaining loss, roughly $800 per minute, because `partner-api` earns $18,100 per minute.

**What I fixed**
- **`mobile-api` (about 97% errors):**
  - **Cause:** `sms-svc` deploy v156 switched to wire schema "v3", which callers couldn't decode. That set off a retry storm that overloaded `pricing-svc` and `sms-svc`.
  - **Fix:** I rolled back v156, then scaled `sms-svc` and `pricing-svc` to 24 replicas to clear the overload. `mobile-api` was clean from about minute 73.
  - **Delay:** It took until then because `sms-svc` stayed overloaded after the rollback, and I only scaled it at minute 58.
- **`web-storefront` (about 99% errors from minute 47):** `address-svc` config cfg-20 had dropped the `currency` price field, which caused `KeyError: 'currency'`. I reverted that config, and `web-storefront` was back to 0% by minute 73. I found it late, so it ran broken for about 25 minutes.

**What I got wrong**
- **Wasted rollback:** I rolled back `returns-svc` v121, thinking it caused the `partner-api` errors. It didn't help. That cost about $10,000 plus 30% failures on a service `partner-api` depends on for several minutes.
- **Needless scale-up:** I also scaled `quotes-svc` up to 10 replicas, which didn't help either. I scaled it back to 6.

**What is still broken**
- **Symptom:** `partner-api` errors come from `returns-svc`, which logs `quotes-svc` timeouts (`pool.acquire() exceeded 200ms`). They started around minute -45.
- **Likely cause:** `quotes-svc` deploy v59, made at minute -40. It hardcodes the database pool size to 4 instead of using the setting. I did not roll it back. During the 6-minute rollback, 30% of `quotes-svc` requests would fail, and I estimated that could cost more than the roughly 17 minutes left to save.
- **Missed chance:** I only found v59 at minute 96. Rolling back earlier would probably have paid off, and that was my main mistake.
- **Replicas:** `pricing-svc` is at 14 replicas (normal is 6) and `sms-svc` is at 10 (normal is 8). I left `pricing-svc` high because 6 replicas looked too small for its current load.
