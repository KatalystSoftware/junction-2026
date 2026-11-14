# OnCallBench: an on-call shift on a generated microservice estate

OnCallBench is the project's name; the task and its identifiers are still `aq-incident`. AfterQuery "Break the Agent" environment. Submitted level: **4**. Judged agent: **OpenCode with
`anthropic/claude-opus-5-5`**.

## What the agent has to do

It is paged at minute 0 of a 120-minute shift on an online shop's backend: 60 seeded, simulated
services (edge, app, data), several faults at once, more starting mid-shift. Every failed request
at an edge service loses that service's revenue per minute. Through the `ops` MCP tools it reads
alerts, metrics, logs and the deploy and config history, then rolls back, reverts, restarts,
scales, fails over or throttles until the shop is healthy, and ends the shift.

## Why it is hard

The tools show everything needed; the difficulty is acting in the right order while the bill runs.

- **A correct fix can make things worse.** Callers retry. Roll back the bad deploy on a hot
  service without throttling or scaling first, and the retries flood it and take the richest edge
  down with it (Microsoft 365, Nov 2026: restarted servers fell over when traffic returned).
- **Two overloads look alike and need opposite fixes.** A retry storm drains under a short
  throttle; real traffic needs replicas. A throttle sheds revenue for as long as it is on, and
  nothing lifts it for you (AWS us-east-1, Oct 2025).
- **The loud alert is often a decoy, and the costliest fault is quiet**: a 4% error rate on an edge
  earning $21,600 a minute, next to edges failing 90% (a healthy edge fails under 1%, and the
  instruction says so).
- **Everything costs.** Telemetry queries move the clock (only `get_status` and `get_topology` are
  free), and a rollback, revert, restart or failover on a service that did not need it costs
  $10,000. Scaling and throttling are never fined: they cost what they add or reject.

Opus 5.5 finds the causes, then loses on judgment. In six of its nine runs on the shipped task it
rolled back the quiet fault's hot service without adding capacity first ("The rollback failed some
requests, and admin-portal's retries overloaded import-svc, so admin-portal errors rose to about
43%"); the two runs that scaled first and wasted nothing scored 0.73 and 0.80. On seed 101 (the
committed run below, 0.57, recorded before the instruction stated the healthy baseline) it
read real traffic as a retry storm and held an 85% throttle for 28 minutes ("When I lifted the
throttle, pricing-svc fell straight back into overload"). Elsewhere it rolled back a hot service
unprotected, reverted a config "without reading what it did", and twice made the shift cost more
than doing nothing. Every rule cites a public postmortem: `postmortems.md`.

## How it is scored

The MCP server logs every action it accepts to a volume the agent's container mounts read-only.
The verifier, in its own container, replays that log in the same deterministic simulator and
totals the shift's cost: lost revenue, extra replica-minutes and $10,000 per wasted mitigation.
Nothing the agent writes or says is scored, and a missing or corrupted log grades as doing
nothing. The log's HMAC uses a key that is in the source, so it catches corruption, not forgery;
what stops a forged log is that only the sidecar can write it.

`score = (cost_do_nothing - cost) / (cost_do_nothing - cost_reference)`, clipped to 0..1, written
to `/logs/verifier/reward.txt` (the full cost breakdown goes to `reward.json`). The reference is a
scripted on-call expert (`task/solution/policies.py`) that uses only the same MCP tools over HTTP.
Its rule: a service is a cause when it fails more than its dependencies explain, and it undoes a
change only after reading its diff. On 200 seeds nobody tuned on (3000-3199) it avoids 0.54-0.86
of what an oracle that knows the faults avoids (mean 0.75) and is never worse than doing nothing
(`python3 generality.py --seeds 3000-3199`).

| Level 4, seeds 101-103 (never used to tune the reference) | Score |
| --- | --- |
| Reference | 1.00 |
| Do-nothing (`nop` agent) | 0.00 |
| Stop-early (looks at the dashboards, then ends the shift) | 0.00 |
| Try every mitigation on everything that fires | 0.00 |
| **Opus 5.5** (9 runs, three on each of seeds 101-103) | **0.32** mean, median 0.18 (0.03-0.80) |
| Opus 5.5 on six fresh seeds, 107-112 (one run each) | 0.55 mean (0.34-0.75) |
| Gemini 3.1 Pro (seed 101) | 0.00 |
| Sonnet 5.5 (seed 101) | 0.02 |

Seeds 101-106 were used for the model runs while the levels were built, and the instruction's
sentence on the healthy baseline was added after Opus runs on seed 101. The reference's generality
is measured on 3000-3199, which no one ran while building.

Those are runs on the task as shipped. Across all 15 Opus runs on nine seeds the mean is 0.41 and
the best run 0.80: the gap holds on every seed, and its size varies with the estate (seeds 101-103
happen to be harder than 107-112). The fresh-seed runs were made once, after the reported numbers,
with nothing changed in between. After the agent's image moved to Alpine (see the known limitation
below), one more Opus run per shift scored 0.00, 0.78 and 0.28, in line with the runs above; the
0.00 rolled back quotes-svc without protecting it and set off the retry storm. Before the
instruction stated the healthy baseline, Opus averaged 0.58 on seeds 101-103 (four runs) and 0.45
over seven runs on seeds 101-106, Gemini 0.00 (three runs) and Sonnet 0.26.

Every run with its cost: `metrics.json`; how each level was built and checked: `LOOP.md`.

**Common seeds.** Every model is compared on the same 24 level-4 seeds, **200000-200023**, which no
demo, tuning or training run used: the Gemma adapter was first evaluated there in our own runner
(`rl/RESULTS.md`). Opus 5.5 gets two Harbor runs per seed, Fable 5.2 one, Gemma untrained and
fine-tuned their own Harbor runs, plus the reference, do-nothing and stop-early; every result goes
into `metrics.json` and this section whatever it is. This set replaced an earlier pre-registered
one, the HTTP status codes 404, 418, 500, 502, 503 and 504 (55aa6f8), so that every model shares
one larger set. Only three Fable 5.2 test runs were made on that set before the switch (404: 1.00,
418: 0.26, 500: 0.86); they stay in `metrics.json` as round 15 and are not part of any table.

Known limit: the agent's container reaches the internet, because OpenCode calls the model API
from it, and this repository is public, so an agent could try to download the reference and run it
(at best the reference's 1.00, since the score is clipped at 1). `extra_hosts` in
`task/environment/docker-compose.yaml` points GitHub's download hosts, common mirrors and the replay
site at localhost, which is why the agent's image is Alpine: there Harbor installs OpenCode's Node
from the distro instead of from GitHub. Another mirror could still serve the code. Harbor 0.25's
`allowlist` network mode would close it fully, but it needs an egress sidecar and nftables support
on the host's Docker, so the shipped task stays on `public` rather than risk failing on a judge's
machine. A production benchmark would keep its reference and evaluation seeds private
(`redteam/REPORT.md`).

## A smaller model learns from it

Gemma 4 26B-A4B with a LoRA adapter trained on the reference's shifts (`rl/`), run the way Opus was:
OpenCode in Harbor 0.25.0 against a local vLLM server, three runs on each of shifts 1-3.

| Level 4, seeds 101-103, Harbor + OpenCode (9 runs each) | Mean |
| --- | --- |
| Gemma 4 26B-A4B, untrained | 0.06 |
| Gemma 4 26B-A4B + SFT on the reference's shifts | 0.26 (0.88/0.14/0.00, 0.00/0.26/0.00, 0.00/0.65/0.41) |
| Opus 5.5 | 0.32 |

Copying the reference took Gemma from 0.06 to about Opus's level in the judges' harness. Its
scores in our own training runner (`rl/env.py`: a capped number of replies, a shorter context) are
higher and are not comparable with Harbor's; they stay in `rl/RESULTS.md`, in their own tables.

## Reproduce

Needs Docker with Compose v2 (`docker compose version` must work; on Ubuntu's `docker.io` install
`docker-compose-v2`), `uv`, Harbor 0.25.0 (`uv tool install harbor==0.25.0`; `run.sh` fetches it
by itself) and, for the Opus runs only, an `ANTHROPIC_API_KEY` in the environment. No Python
install is needed: without `python3`, `run.sh` uses uv's, and the other `python3 <script>.py`
commands here run as `uv run --no-project --python 3.13 python3 <script>.py`. AfterQuery
provides no inference credits. A run downloads the base images from Docker Hub, `mcp` from PyPI and, for the agent,
OpenCode through Harbor's installer. Run everything from this folder (`projects/oncallbench`).

The reported seeds ship as ready-to-run Harbor tasks: `tasks/shift-1`, `shift-2` and `shift-3` are
seeds 101, 102 and 103 at level 4, with the briefing and the verifier's calibration filled in
(`./export-tasks.sh` writes them). Plain Harbor 0.25.0
runs them as they are (`alias harbor='uvx --from harbor==0.25.0 harbor'`):

```
harbor run -p tasks/shift-1 -a opencode -m anthropic/claude-opus-5-5   # the judged agent
harbor run -p tasks/shift-1 -a oracle                                  # the reference, 1.00
harbor run -p tasks/shift-1 -a oracle --ae POLICY=stop-early           # stop-early, 0.00
harbor run -p tasks/shift-1 -a nop                                     # do-nothing, 0.00
```

On a busy machine Harbor's six minutes for installing OpenCode in the container can run out before
the shift starts (`AgentSetupTimeoutError`); add `--agent-setup-timeout-multiplier 2`.

Shifts 1-3 are the seeds we report. To check that we did not tune for them, export any other seed:
`./export-tasks.sh 4 <seed>...` writes `tasks-custom/seed-<seed>` and never touches `tasks/`; run it
the same way (`harbor run -p tasks-custom/seed-777 ...`), or use `SEED=<seed> ./run.sh ...`.

`run.sh` does the same for any seed and runs several at once. One command runs the reference, both
baselines and Opus on the committed run's seed:

```
LEVEL=4 SEED=101 ./run.sh reference nop stop-early opus
```

Expect 1.00, 0.00, 0.00 and, for Opus, anything from 0.0 to 0.7 on this seed (0.11, 0.18 and 0.73
in three runs; 0.32 mean over nine runs on 101-103). A rerun of this command from a clean clone
in a fresh Ubuntu container with only Docker and uv, before the agent's image moved to Alpine,
gave 1.00, 0.00, 0.00 and 0.00: Opus cleared every fault and wasted no mitigation, but its
rollback of quotes-svc set off a retry storm and the shift cost $245,607 against $232,523 for
doing nothing (`runs/repro-l4-s101-opus-204757/`). The runs go side by side: the first call spends
about 5 minutes building the images, then the scripted runs take about a minute and an Opus run
5-8. Each run's score is in `jobs/<name>/<trial>/verifier/reward.txt`, its cost breakdown next to
it in `reward.json`. `run.sh` writes a Harbor task for the episode to `jobs/variants/` and calls
`harbor run -p <task> -a opencode -m anthropic/claude-opus-5-5`, so a judge can rerun that folder
with plain Harbor. Stop-early and the other scripted policies run as Harbor's `oracle` agent with
`POLICY=<name>`. `SEED` picks the episode (the reported seeds are 101-106); `ATTEMPTS=3` gives three Opus runs.

Committed run logs, each trial with its transcript in `agent/opencode.txt`, its action log in
`artifacts/ledger/receipt.json` and its score in `verifier/reward.txt`:

- `runs/rerun-l4-shift1-opus-x2/`: `harbor run -p tasks/shift-1 -a opencode -m
  anthropic/claude-opus-5-5 -k 2` on the task as shipped, from a fresh copy of this repository on
  a machine that had never run it (Sat 14 Nov, 4 vCPU, Harbor 0.25.0): 0.53 and 0.26. On the same
  machine `run.sh reference nop stop-early opus` gave 1.00, 0.00, 0.00 and 0.20 (5m36s), and the
  reference again through plain Harbor 1.00 at the same cost to the cent ($85,246.31).
- `runs/r4-l4-s101-opus-130256/`: Opus 5.5, seed 101, 0.5728, recorded before the instruction
  gained its sentence on the healthy baseline.

`./eval.sh <round> <level> <seed> <run>...` does the same as `run.sh` and records the result in
`metrics.json`.

## Test

```
uv run --no-project --python 3.13 python3 eval.py --fuzz 200
```

(`python3 eval.py --fuzz 200` with a Python 3.13 of your own; about 4 minutes, exit status 0 on a
pass.)

Plays every scripted policy on build seeds 1-5 and reported seeds 101-103, checks that each replay is
byte-identical, that stopping early and the try-everything exploiter stay below the reference, and
that 200 random episodes per seed never beat it.

## Roadmap

Three fault types from SREGym (arXiv 2605.07161v3) are not in the shipped level. Two were built
as a level 6 on top of level 4 and reverted: [what we tried and why it was not
kept](LOOP.md#roadmap-what-we-tried-and-why-it-was-not-kept).

- **Capacity that never arrives.** A bad quota or placement change on a node pool: a `scale` is
  accepted and its replicas stay pending. The one fault that produced a new mistake: an Opus
  run scaled before its rollback, did not check that the replicas were ready, and rolled back
  into the retry storm. Next in line.
- **A correlated failure with one cause.** A shared DNS resolver fails every service behind it.
  Opus found it in 9 of 9 runs, because the resolver alerted under its own name; it needs a
  resolver that looks healthy by its own telemetry before it tests anything.
- **Background noise.** Blips that heal by themselves. Not built.

None can ship before the reference has room: it avoids 0.75 of what an oracle avoids on level 4
and fell to 0.57 with both faults added, because it reads one thing at a time and the oracle
fixes these faults for free.

## Layout

- `sim/incident.py`: the simulator, shared by the MCP sidecar and the verifier.
- `sim/policies.py`: reference, do-nothing, stop-early, one-fix and exploiter policies.
- `task/`: the Harbor task template (instruction, MCP sidecar, verifier, solution). `sync.sh` copies
  the simulator into it; it is not runnable until a seed is filled in.
- `tasks/shift-N/`: the template filled in for one reported seed each, ready for plain Harbor
  (`export-tasks.sh`).
- `runs/`: committed Harbor run logs (the agent's OpenCode state database left out).
- `parity.py`: fails if any tool reply or cost on levels 0-5 moves; run it after changing the
  simulator or the policies.
- `explain.py`: prints what an agent did, step by step, from its action log, with the episode's
  hidden faults: `python3 explain.py 101 4 <trial>/artifacts/ledger/receipt.json`.
