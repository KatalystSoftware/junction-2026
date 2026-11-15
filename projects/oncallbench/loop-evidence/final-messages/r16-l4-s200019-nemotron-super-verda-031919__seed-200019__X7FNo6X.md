# r16-l4-s200019-nemotron-super-verda-031919/seed-200019__X7FNo6X

Level 4, seed 200019, nemotron-super-verda, score as run 0.0. The agent's closing message, verbatim:

Shift over. Here's the incident summary:

## Root causes found & fixed

1. **`orders-db`** — self-sustaining retry-storm overload (72% retries, rps 9× normal, 99% cpu). Not a gone-primary (failover didn't help). Fixed by **scaling to 32 replicas**, which broke the storm (error 0.86→0.004, cpu 0.99→0.52). This recovered the `currency-svc`→`auth-svc` chain.

2. **`currency-svc`** — `TLS handshake failed: protocol version` from config `cfg-59` "rotate credentials" (minute -12). Fixed with **`revert_config`** (no impact). This cleared `auth-svc`.

3. **`giftcards-svc`** — `KeyError: 'currency' in price formatter` from deploy `v110` (minute 48). **Rollback** in progress (completes minute 123, just after shift); it reduced giftcards-svc failure from 88%→30% during the final minutes.

## Result
- `admin-portal`: recovered to **0.0** error (auth-svc/currency-svc chain fixed).
- `partner-api`: still **4%** (tax-svc geo-svc 50ms RPC timeout — tried geo-svc scale and tax-svc v142 rollback; neither reduced p99 below the 50ms budget, so it's unresolved).
- `web-storefront` / `mobile-api`: still elevated, driven by `giftcards-svc` (rollback completes just after shift) and unresolved `tax-svc`.

Biggest unrecovered loss: `partner-api` (~1164 revenue/min).
