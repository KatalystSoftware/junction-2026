# r16-l4-s200000-gemma-base-224420/seed-200000__MBjgQiK

Level 4, seed 200000, gemma-base, score as run 0.0191. The agent's closing message, verbatim:

The incident involved two primary faults:
1. **`audit-svc`**: A bad deployment (`v44`) introduced a bug in the rate limiter, causing a retry storm and high CPU/error rates. I mitigated this by rolling back to the previous version and then scaling the service to 6 replicas to handle the resulting load.
2. **`checkout-svc`**: A bad configuration change (`cfg-52`) reduced the `entry_ttl_s` from 600 to 1, causing massive request spikes and subsequent overload. I mitigated this by rolling back the deployment.

The `mobile-api` and `web-storefront` errors were downstream symptoms of these service failures.
