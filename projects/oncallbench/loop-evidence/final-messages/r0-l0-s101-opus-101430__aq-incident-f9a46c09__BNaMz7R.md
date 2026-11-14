# r0-l0-s101-opus-101430/aq-incident-f9a46c09__BNaMz7R

Level 0, seed 101, opus, score as run 0.9947. The agent's closing message, verbatim:

I fixed the incident at minute 4 by adding replicas to `profile-db`, and I ended the shift at minute 25 with both customer-facing services at 0% errors.

- **Cause:** about 16 minutes before the page, requests to `profile-db` more than doubled, from about 1,100/s to about 2,400/s. Its CPU sat at 99% and it was turning away about 29% of requests as overloaded. Customer traffic hadn't changed, and none of the three services that call `profile-db` showed a rise in requests either, so I couldn't tell where the extra load came from.
- **Ruled out:** `profile-db` had no recent deploy or config change; its last release went out about 3.5 hours earlier. None of the services it feeds had a change at the time either, so a rollback or config revert didn't fit. The other database on the customer path, `shipping-db`, was healthy.
- **Spread:** the overload made `thumbnails-svc`, `sessions-svc` and `catalog-svc` fail about 30% of requests, and `export-svc` and `currency-svc` about 9%. That added up to about 55% errors on `web-storefront` and `mobile-api`, roughly $575 lost per minute.
- **Fix:** I scaled `profile-db` from 6 to 10 replicas at minute 0. Edge errors were at 0% by minute 5, and `profile-db` stayed below 0.5% errors at about 85% CPU through minute 25 with no alerts.

**Cost:** about $8,700 in lost revenue before the scale took effect, plus about $1,400 for the 4 extra replicas for the rest of the shift. There were no wasted mitigations.

**Follow-up:** the extra replicas are still running, and the source of the extra load is unknown. Find where it comes from before scaling `profile-db` back to 6, or the overload will come back.
