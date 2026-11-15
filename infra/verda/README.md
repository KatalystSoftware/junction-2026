# How we used Verda

Every live demo and most of our compute ran on Verda.

| What | Verda product | Used by |
| --- | --- | --- |
| Our server: the live sites behind one proxy, and the agent evaluations | CPU instance (`CPU-TURIN.8V.32G`, FIN-03), defined in [`main.tf`](main.tf) | All entries |
| Video renders | Second CPU instance, same file | All entries' videos |
| Model training and serving | GPU instances, rented and deleted through the API ([`verda.py`, `grab.py`](../../projects/oncallbench/rl/)) | OnCallBench: Qwen3.5-2B SFT and RL, Gemma 4 26B-A4B SFT, Gemma served for its Harbor runs |
| Nemotron 3.5 Super VL | Dedicated serverless container | Since When's difference check; OnCallBench's Nemotron row |

## Process

1. **Infrastructure as code.** Both CPU machines, their SSH keys and startup script are written in
   [`main.tf`](main.tf) with Verda's official OpenTofu provider (`verda-cloud/verda`):
   `tofu apply` creates them; the API credentials come from sops-encrypted secrets.
2. **One server for every demo.** Caddy in [`proxy/`](proxy/README.md) gives each project its own
   HTTPS subdomain: [incident](https://incident.katalyst.fyi/), [since-when](https://since-when.katalyst.fyi/),
   [kutsu](https://kutsu.katalyst.fyi/) and [katalyst.fyi](https://katalyst.fyi/). Since When's MariaDB 11.8 runs on the same machine.
3. **Evaluations off our laptops.** OnCallBench's Harbor + OpenCode runs, 48 per model, ran in Docker on the CPU
   instance.
4. **GPUs on demand.** `grab.py` polls availability and creates the cheapest GPU of at least 80 GB
   that's free (A100, RTX PRO 6000, H100, H200, B200; spot first); `verda.py` deletes it when the run ends.
   The Gemma SFT took 90 minutes on one ([results](../../projects/oncallbench/rl/RESULTS.md#compute-and-cost)).
5. **A container for the big model.** Nemotron 3.5 Super VL has a strict rate limit on NVIDIA's
   hosted API, so Since When's checks run against a dedicated Verda container serving the same
   model ([`differences/llm.py`](../../projects/since-when/differences/llm.py), `verda-super`).

## What it let us do

- One machine served every demo through the whole weekend, recreated from code at any time.
- A 26B open model trained in a 90-minute run on a GPU we paid for only while it ran.
- Since When checks its differences with a 120B model without waiting on a rate limit.
