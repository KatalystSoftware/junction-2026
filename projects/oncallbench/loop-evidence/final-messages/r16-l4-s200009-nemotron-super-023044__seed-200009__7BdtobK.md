# r16-l4-s200009-nemotron-super-023044/seed-200009__7BdtobK

Level 4, seed 200009, nemotron-super, score as run 0.0. The agent's closing message, verbatim:

The shift is over (minute 120). All metric calls are now rejected. Here's where things stand:

**What I did:**
1. `revert_config` on `bundles-svc` (cfg-49) — **wrong call**. bundles-svc's 4.4% error was actually an sms-svc schema v3 decode error, not the rate-limit config. No effect; $10k wasted.
2. `rollback` on `flags-svc` (v34) — **correct call**. flags-svc was memory-leaking (OOM kills, mem 0.99). Error dropped 89%→41%, mem 0.99→0.43. Cascade (inventory-svc→mobile-api/admin-portal) was recovering but hadn't cleared by shift end.
3. `rollback` on `events-queue` (v102) — **didn't fix it**. events-queue still at 92% with TLS handshake errors; the config change cfg-47 (same minute) may have been the real cause.
4. `rollback` on `sms-svc` (v24) — **made things worse**. sms-svc was healthy (0.002%); after rollback it jumped to 41%, dragging bundles-svc/web-storefront from ~4% to ~41%. $10k wasted + increased losses.

**Final edge state (minute 112):**
| Service | Error Rate | Revenue/min | Loss/min |
|---|---|---|---|
| web-storefront | 41.4% | $22,900 | ~$9,480 |
| mobile-api | 99.3% | $450 | ~$447 |
| partner-api | 95.5% | $400 | ~$382 |
| admin-portal | 99.9% | $500 | ~$500 |

Key lesson: I misdiagnosed bundles-svc (reverted the wrong change) and then compounded it by rolling back sms-svc, which was healthy and broke a working service. The flags-svc rollback was the only correct mitigation, but its cascade hadn't fully cleared when the shift ended.
