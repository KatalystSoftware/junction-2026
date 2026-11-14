# r16-l4-s200008-gemma-base-224444/seed-200008__CNTiayy

Level 4, seed 200008, gemma-base, score as run 0.335. The agent's closing message, verbatim:

The incident involved multiple interconnected faults. I identified and mitigated the following:

1.  **`sitemap-svc`**: High error rates and CPU were caused by a bad configuration change (`cfg-48`) that removed the `currency` field from `price_fields`. I first scaled the service to handle the retry storm and then reverted the configuration, successfully restoring service.
2.  **`profile-db`**: A configuration change (`cfg-32`) removed the `orders.write` scope, causing `PermissionDenied` errors in `risk-svc`. I reverted this config, which resolved the downstream errors in `risk-svc` and `couriers-svc`.
3.  **`couriers-svc`**: After resolving the `profile-db` issue, `couriers-svc` remained in a high-load state due to a retry storm. I applied a 50% throttle to allow the service to recover from the overload.
