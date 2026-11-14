# r6-l4-s104-opus-140247/aq-incident-7e283ba2__QcKzisE

Level 4, seed 104, opus, score as run 0.7913, regraded 0.835. The agent's closing message, verbatim:

The shift is over. Every edge service has been at 0% errors since about minute 70 and stayed there through minute 120. I found and fixed three separate causes.

1. **loyalty-svc bad deploy v47** (began at minute −19). It cut the RPC deadline to a tenth (`budget_ms / 10000`). That broke auth-svc, which broke web-storefront and mobile-api; both were at about 97% errors when I was paged.
   - I rolled back v47 at minute 13. Caller retries kept loyalty-svc overloaded afterwards, so web and mobile only dropped to about 40% errors.
   - Scaling loyalty-svc from 3 to 8 replicas at minute 38 cleared that by minute 42. I then set it to 5 replicas.
   - auth-svc traffic had roughly tripled at minute −23, so I scaled it from 8 to 16 replicas. It is still running near capacity (CPU about 0.91) at about 1,880 requests per second.

2. **checkout-svc bad deploy v116** (began at minute −37). It switched the wire format from schema v2 to v3, and risk-svc couldn't decode the replies. That cost admin-portal, the $36,500/min service, about 4% of its requests.
   - checkout-svc was already at CPU 0.87. Before rolling back, I scaled it from 6 to 12 replicas so the retries during the rollback wouldn't overload it.
   - The rollback finished at minute 44 and admin-portal went to 0%. I then set checkout-svc to 8 replicas.

3. **flags-svc config change cfg-14** (new fault at minute 50). It rotated the database credentials and raised the minimum TLS version to 1.3. It pushed web, mobile and partner-api to between 55% and 80% errors. I reverted it at minute 67 and all three were back to 0% by minute 70.

I also scaled ledger-svc from 6 to 8 replicas because it had been running at CPU 0.97–0.99 with traffic slowly rising. It never failed, so this was only a precaution.

**Cost:**
- **Lost revenue:** most of it comes from the delay in fixing admin-portal. Its 4% error rate cost about $1,460/min until minute 44. Web and mobile together lost about $1,000–1,400/min until minute 42.
- **Wasted mitigations:** none. I checked the diffs before acting so that I only reverted the actual faulty change, and the two scale-ups before the checkout rollback and the ledger-svc scale-up were scaling, which is never charged as wasted.
- **Extra replicas:** auth-svc, loyalty-svc, checkout-svc and ledger-svc stayed above normal until the end, at $3 per extra replica per minute. That is small next to the revenue at stake.
