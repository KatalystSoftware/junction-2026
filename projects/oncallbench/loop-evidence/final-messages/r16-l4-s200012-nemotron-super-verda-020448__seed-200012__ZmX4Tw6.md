# r16-l4-s200012-nemotron-super-verda-020448/seed-200012__ZmX4Tw6

Level 4, seed 200012, nemotron-super-verda, score as run 0.0. The agent's closing message, verbatim:

The shift is over. Here's a summary of the incident and resolution:

## Root Causes Found & Fixed

| # | Service | Root Cause | Fix | When |
|---|---------|-----------|-----|------|
| 1 | `experiments-svc` | Bad config `cfg-26`: rotated DB credentials (`vault:v41→v42`), narrowed token scope | `revert_config` (cfg-26) | min 41-42 |
| 2 | `events-queue` | Bad deploy `v145`: changed wire schema `v2→v3`, causing `DecodeError` in `giftcards-svc` | `rollback` (v145) | min 58-63 |
| 3 | `ledger-svc` | Bad config `cfg-45`: `entry_ttl_s: 600→1`, cache expired immediately | `revert_config` (cfg-45) | min 73-74 |

## Retry Storms Broken with Scale

After the root fixes, two services were stuck in retry storms (callers retrying 3×, pushing CPU to 99%):
- `events-queue`: scaled to 16 replicas (min 84-87), then back to 8 (min 110-113)
- `experiments-svc`: scaled to 8 replicas (min 109-112)

## Impact

All mitigations were correctly targeted (no wasted mitigations). By end of shift (min 120):
- **mobile-api**: 0% error (was 4.2%, $365/min loss — the biggest revenue risk)
- **giftcards-svc**: 0% error (was 4.4%)
- **experiments-svc**: 0.002% error (was 90%)
- **payments-svc**: 38% error (was 94%, recovering)
- **admin-portal**: 38% error (was 94%, recovering)
- **web-storefront**: 11% error (was 28%, recovering)

The remaining errors at shift end are residual recovery from `payments-svc` not fully converging before minute 120, but all root causes were eliminated.
