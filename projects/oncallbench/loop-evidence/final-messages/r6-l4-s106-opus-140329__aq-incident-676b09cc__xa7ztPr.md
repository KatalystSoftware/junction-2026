# r6-l4-s106-opus-140329/aq-incident-676b09cc__xa7ztPr

Level 4, seed 106, opus, score as run 0.0, regraded 0.0. The agent's closing message, verbatim:

The shift is over. From minute 84 to the end, all four customer-facing services were at 0% errors. I made one wrong call along the way: I rolled back payouts-svc when it didn't need it. That cost a $10k wasted-mitigation charge, plus about 6 minutes of roughly 30% errors on partner-api, our biggest earner at $11,200/min.

**What broke and what I did**
1. **profile-db was overloaded (mobile-api and admin-portal).** Normal traffic roughly tripled at minute −18, and callers retrying failed requests kept it overloaded. I scaled it from 4 to 12 replicas, then rejected 50% of its requests for about 2 minutes to stop the retries. It recovered by minute 35 and was running at about 75% CPU. I left it at 12 replicas, which costs $24/min.
2. **orders-db had a bad deploy (partner-api at 4% errors from before the page).** The minute −29 deploy (v167) made the price formatter fail when a row has no currency. payouts-svc depends on orders-db, giftcards-svc on payouts-svc, and partner-api on giftcards-svc, so the errors reached partner-api.
   - **My mistake:** I first rolled back payouts-svc's own deploy from minute −32. Its errors started right after that deploy, but its logs blamed orders-db, and the errors kept going after the rollback. I should have checked orders-db's changes before acting.
   - **The fix:** I rolled back orders-db v167. The rollback's own failures set off a retry overload on orders-db, which pushed partner-api to about 45% errors for several minutes. Rejecting 60% of orders-db's requests for 2 minutes cleared it, and partner-api was at 0% by minute 63.
3. **tracking-svc was leaking memory.** It was running out of memory and being killed and restarted repeatedly. I rolled back its minute −137 deploy (v164). Status afterwards showed no tracking-svc problem; the mobile-api errors still there came from geo-svc.
4. **geo-svc broke during the shift.** A deploy at minute 49 (v84) removed the `orders.write` permission, and its logs showed requests failing for that reason. Retries then overloaded it. I rolled the deploy back and rejected 70% of its requests briefly to clear the retries. mobile-api was at 0% by minute 84.

**Left alone on purpose:**
- **giftcards-svc CPU alert:** caused by a scheduled nightly job, not a fault.
- **geo-svc rate-limit config change:** it only adjusted cache time and burst limits.
- **orders-db credential rotation:** not related to the errors.

From minute 84 to 120 I checked status every 6 to 10 minutes and saw no new faults before ending the shift.
