# r9-l5-s103-opus-152453/aq-incident-5bac5a85__dpaS6rC

Level 5, seed 103, opus, score as run 0.2135. The agent's closing message, verbatim:

The shift is over. From minute 77 to 120, all four customer-facing services were at 0% errors. I found and fixed four faults, but I rolled back the wrong change on inventory-svc. That cost $10,000 as a wasted action and set off a retry storm that briefly took every customer-facing service to about 70% errors.

**What I fixed:**
1. **payments-svc** (hit web-storefront and mobile-api, 72–88% errors at the page): quotes-svc config change `cfg-6` added a second rules source. The rules file it publishes grew to 346 entries, over payments-svc's limit of 200, and payments-svc's retries overloaded it. I throttled payments-svc to 75% to stop the storm and reverted `cfg-6`. Once the next good file arrived around minute 34, I lifted the throttle.
2. **pricing-svc** (mobile-api): deploy `v105` set call deadlines 10x too short. I rolled it back and it was clear by minute 35.
3. **inventory-svc** (about 3.7% errors on all four customer-facing services, which is roughly $680/min on admin-portal alone): config `cfg-31` removed `currency` from the price fields.
   - **My mistake:** deploy `v123` changed the same query, so I rolled it back without checking the config diff. That was the wrong change.
   - inventory-svc was already running at 86% CPU, so failures during the rollback were retried until it was overloaded. Errors reached about 70% on every customer-facing service around minutes 48–58. admin-portal earns $18,300/min, so most of the shift's lost revenue came from this window.
   - I contained it with a temporary 35% throttle and by scaling inventory-svc from 4 to 6 replicas.
   - At minute 76 I reverted `cfg-31` and errors went to 0.
4. **labels-svc** (behind geo-svc, which tax-svc and disputes-svc call; about 50% extra errors on web-storefront and mobile-api from minute 55): config `cfg-38` dropped the `orders.write` token scope. I reverted it at minute 67.

**What's still running:** inventory-svc stayed at 6 replicas, which costs about $6/min, roughly $370 from when the scale landed to the end of the shift. I kept the headroom because at 4 replicas it has almost none. The status-page and experiments-svc CPU alerts had been firing since before the page and never affected customers, so I left them alone.

**Lesson:** when a deploy and a config change land at the same minute, read both diffs before acting.
