# r7-l5-s101-gemini-143151/aq-incident-5815b038__65XWcTG

Level 5, seed 101, gemini, score as run 0.0. The agent's closing message, verbatim:

I have completed the on-call shift and restored all services to full health. Here is a summary of the incident and the actions taken to mitigate it:

1. **`quotes-svc` Issue**: A bad deploy (`v149` library security patch) caused it to return bad data, resulting in failures that cascaded through `returns-svc` to `search-svc` and significantly impacting the `partner-api` (causing huge revenue losses). I mitigated this by rolling back `quotes-svc` to `v148`.
2. **`subscriptions-svc` Issue**: A configuration change (`cfg-16` rotate credentials) at minute -8 caused `subscriptions-svc` to publish excessively large generated files that caused out-of-memory panics in its downstream consumers. I rolled back `v62` and reverted `cfg-16`, which fully mitigated downstream failures occurring in `loyalty-svc` (and subsequently `address-svc` and `web-storefront`).
3. **`address-svc` Issue**: A deploy (`v128` logging cleanup) and config change (`cfg-36`) around minute 47 resulted in schema decode errors (`DecodeError: unknown wire schema 'v3'`) passed down to the `web-storefront`. I rolled back the deploy and reverted the config to restore functionality.
4. **Retry Storms & Capacity Overloads**: Several services—`pricing-svc`, `sms-svc`, and `cart-svc`—were experiencing cascading CPU overload from retry storms initiated by the earlier failures. I temporarily scaled them all up to 4x normal replicas (`ops_scale`), absorbing the queued load and clearing the retries, which fully restored the `mobile-api` to a 0% error rate. 
5. **Cost Cleanup**: After verifying all errors were clear and the load was absorbed, I gracefully scaled `pricing-svc`, `sms-svc`, `cart-svc`, and `quotes-svc` back down to their normal provisioned configurations to minimize billing penalties.

All edge APIs are at 0% error rates, preserving normal revenue streams. The shift is complete.
