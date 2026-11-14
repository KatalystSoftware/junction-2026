# r0-l0-s102-opus-101431/aq-incident-65a4f416__qmRkPfQ

Level 0, seed 102, opus, score as run 1.0. The agent's closing message, verbatim:

The incident is fixed and the shift is over. Both customer-facing services stayed at 0% errors from minute 7 to the end of the shift.

**Cause:** cart-svc build v152 (a "dependency bump"), deployed 24 minutes before the page. Its logs showed about 100k "unhandled exception in request handler (first seen in build v152)" errors in 10 minutes, and its error rate was 42%. cart-svc is a hard dependency of recommendations-svc, which both web-storefront and mobile-api call hard, so both were failing 42% of requests. The services cart-svc depends on (inventory-svc, shipping-db, users-db) were healthy.

**What I did:** I rolled back cart-svc at minute 0. The rollback finished at minute 6, and by minute 7 there were no alerts and no edge errors.

**Monitoring:** I checked alerts and edge status at minutes 27, 57, 87 and 107 and nothing came back. inventory-svc traffic was creeping up steadily, but its CPU stayed flat at about 0.64, so I didn't scale it.

**Cost:** about $250 in lost revenue, almost all from the 6-minute rollback (15% failures on two services earning $300/min each). That's my estimate from those numbers; the tools don't report the actual score. There were no extra replicas and no wasted mitigations.
