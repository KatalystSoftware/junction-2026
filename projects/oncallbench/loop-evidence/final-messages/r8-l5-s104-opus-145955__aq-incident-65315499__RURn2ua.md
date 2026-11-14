# r8-l5-s104-opus-145955/aq-incident-65315499__RURn2ua

Level 5, seed 104, opus, score as run 0.5697. The agent's closing message, verbatim:

The shift ran the full 120 minutes. Every customer-facing service has been at 0% errors since minute 71 and stayed there to the end. Three faults were behind the incident, plus a traffic surge.

**What I found and did:**
1. **Traffic surge on auth-svc** (since minute -23): requests went from about 677 to 1,950 per second and CPU hit 0.99. I scaled it from 8 to 18 replicas at minute 7. This was hurting web-storefront and mobile-api.
2. **Bad config change on consent-svc** (`cfg-39`, minute -19): it added `r0.features` to `rules_source`, which looked like it was producing a bad generated file. loyalty-svc and export-svc load that file. I reverted the change at minute 18. I'm not certain this one was a real cause: afterwards loyalty-svc's errors steadied at about 71% instead of swinging between 71% and 95%, but loyalty-svc was also stuck overloading itself with retries.
3. **Bad deploy on checkout-svc** (`v116`, minute -37): it raised the minimum TLS version from 1.2 to 1.3. risk-svc's calls then failed ("TLS handshake failed: protocol version"), which caused the 4% errors on admin-portal. That cost about $1,800 a minute, the largest single loss, because admin-portal earns $45,600 a minute. I first scaled checkout-svc from 6 to 10 replicas: it was at 0.86 CPU, and I didn't want the failures during the rollback to trigger a retry overload. Then I rolled the deploy back at minute 53, and admin-portal went to 0%.
   - I misread this at first: risk-svc's own deploy `v137` looked suspicious, but its diff was harmless. That cost a few minutes.
4. **Retry overload on loyalty-svc**: about 78% of its traffic was retries. I throttled it to 80% for 3 minutes (minutes 52–55) to break the loop, then lifted the throttle. It recovered without more replicas.
5. **New fault on flags-svc** (`cfg-8`, minute 50): it cut `rpc_budget_ms` from 500 to 50. flags-svc then failed about 55% of requests, which hit partner-api, mobile-api and web-storefront. I reverted it at minute 68.

**Remaining costs:** auth-svc (18 replicas) and checkout-svc (10) stayed above normal until the end, about $42 a minute. auth-svc still needed the extra capacity: it was at 0.82 CPU with 18 replicas. I could have set checkout-svc back to 6 replicas, but it would have run at about 0.86 CPU. I kept the extra headroom in case of another fault on the admin-portal path.

**Not acted on:** the `status-page` alert, which is an external service, and a CPU alert on ledger-svc. Neither caused customer errors.

I don't have the final cost figure; the score comes from the simulator replaying these actions.
