# r9-l5-s101-opus-152413/aq-incident-5815b038__uasf6Ke

Level 5, seed 101, opus, score as run 0.6483. The agent's closing message, verbatim:

The shift is over. All four customer-facing services had zero errors from minute 74 to minute 120, and no new faults showed up in that time. I don't have the final cost or score, because the simulator works those out by replaying the shift.

| Problem | Cause | What I did | Fixed at |
|---|---|---|---|
| partner-api failing about 4.7% of requests ($22.7k/min service, so roughly $1,000/min lost) | Deploy v149 to quotes-svc at minute −40 made the price formatter crash with `KeyError: 'currency'`. The failures passed up through returns-svc and search-svc to partner-api. | quotes-svc was at 87% CPU, so I added replicas (6 → 12) before rolling back v149. That way the 30% of requests that fail during a rollback wouldn't set off a retry storm. I put it back to 6 replicas afterwards. | about minute 52 |
| sms-svc stuck in a retry storm | Config change cfg-16 to subscriptions-svc doubled the rules source. The rules file it publishes grew to 344 entries against a limit of 200, and sms-svc's workers crashed loading it. | Reverted cfg-16 at minute 17. sms-svc then stayed overloaded from retries alone, so I rejected 75% of its requests for about 6 minutes to clear them, then lifted that. | about minute 54 |
| mobile-api failing about 95% of requests | pricing-svc's traffic had grown from about 1,060 to about 2,850 requests a second, well past what 6 replicas can handle (about 1,600). It had been overloaded and retry-storming since minute −25, and the sms-svc failures added to it. | Rejected 85% of its requests to stop the storm, scaled it 6 → 14 replicas, then lifted the rejection. | minute 74 |
| web-storefront failing about 99% of requests (new fault at minute 47) | Config change cfg-36 to address-svc switched the wire schema from v2 to v3, and address-svc started failing with `DecodeError: unknown wire schema 'v3'`. | Reverted cfg-36. | minute 66 |

**Things to know:**
- **Ongoing cost:** pricing-svc is still at 14 replicas, which is 8 above normal, or about $24/min from minute 71. Its traffic is still climbing, and CPU was 71% at the last check. Going back to 6 replicas would overload it again.
- **Not touched:**
  - cart-svc has been at 99% CPU since minute −6, but nothing calls it, so it costs no revenue.
  - status-page is an external service whose alert doesn't belong to this estate.
- **Not investigated:** I never checked the deploy and config change made to search-svc at minute −14, or deploy v62 to subscriptions-svc. Fixing the actual causes cleared everything, so I left them alone to avoid charges for unneeded fixes.
