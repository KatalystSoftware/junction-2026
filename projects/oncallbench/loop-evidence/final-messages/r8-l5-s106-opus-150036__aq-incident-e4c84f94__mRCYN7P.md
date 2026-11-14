# r8-l5-s106-opus-150036/aq-incident-e4c84f94__mRCYN7P

Level 5, seed 106, opus, score as run 0.3598. The agent's closing message, verbatim:

The shift is over. All four customer-facing services were at 0% errors from minute 74 to the end. The most expensive mistake was mine: the orders-db rollback pushed it into overload, and partner-api ($14k/min) was failing more than half its requests for several minutes.

**Root causes and fixes:**

1. **disputes-svc config cfg-7** (minute −18) added a second rules source. The rules file it publishes grew to 316 entries against a limit of 200, so profile-db crashed loading it. That spread through ledger-svc and tracking-svc to mobile-api, and through subscriptions-svc and checkout-svc to admin-portal. I reverted the config at minute 11. profile-db was stuck in a retry storm (83% of its traffic was retries), so at minute 27 I turned on a 90% throttle for a few minutes, then lifted it.
2. **orders-db deploy v167** (minute −29) changed `row.get("currency","EUR")` to `row["currency"]`, which throws a KeyError. That passed through payouts-svc and giftcards-svc to partner-api as a steady 4% error rate, about $560/min. I rolled it back at minute 24.
   - **My mistake:** orders-db was already at 86% CPU. The 30% of requests the rollback failed set off a retry storm, and partner-api's error rate went from 4% to 55–70% for about 8 minutes. This was the largest single cost of the shift. I stopped it with a one-minute 70% throttle and scaled orders-db from 3 to 5 replicas.
   - **Should have done first:** throttled or scaled orders-db before starting the rollback.
3. **tracking-svc deploy v154** was running out of memory: heap at 99%, repeated restarts, and a share of mobile-api's errors. I rolled it back at minute 43, memory dropped to 45%, and the errors stopped. The diff didn't show where the leak is, but it was the only recent deploy.
4. **New fault during the shift: geo-svc deploy v140** (minute 49) removed the `orders.write` permission, causing PermissionDenied errors and a retry storm, with mobile-api at about 82% errors. I rolled it back at minute 66 and used a one-minute 70% throttle to end the storm.

**Left alone on purpose:**
- **giftcards-svc CPU alert:** caused by a nightly scheduled job, not a fault.
- **status-page alert:** it's an external service, outside this estate.
- **disputes-svc v182 and geo-svc cfg-40:** I checked both diffs and neither was a cause.

I kept orders-db at 5 replicas until the end of the shift, about $6/min, because at 3 replicas it runs near capacity.
