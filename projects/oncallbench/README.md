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

The MCP server signs a log of every action. The verifier replays that log in the same
deterministic simulator and totals the shift's cost: lost revenue, extra replica-minutes and
$10,000 per wasted mitigation. Nothing the agent writes or says is scored, and a missing or
tampered log grades as doing nothing.

`score = (cost_do_nothing - cost) / (cost_do_nothing - cost_reference)`, clipped to 0..1, written
to `/logs/verifier/reward.txt` (the full cost breakdown goes to `reward.json`). The reference is a
scripted on-call expert (`task/solution/policies.py`) that uses only the same MCP tools over HTTP.
Its rule: a service is a cause when it fails more than its dependencies explain, and it undoes a
change only after reading its diff. On 200 seeds nobody tuned on (3000-3199) it avoids 0.54-0.86
of what an oracle that knows the faults avoids (mean 0.75) and is never worse than doing nothing
(`python3 generality.py --seeds 3000-3199`).

| Level 4, held-out seeds | Score |
| --- | --- |
| Reference | 1.00 |
| Do-nothing (`nop` agent) | 0.00 |
| Stop-early (looks at the dashboards, then ends the shift) | 0.00 |
| Try every mitigation on everything that fires | 0.00 |
| **Opus 5.5** (9 runs, three on each of seeds 101-103) | **0.32** mean, median 0.18 (0.03-0.80) |
| Gemini 3.1 Pro (seed 101) | 0.00 |
| Sonnet 5.5 (seed 101) | 0.02 |

Those are runs on the task as shipped. Before the instruction stated the healthy baseline, Opus
averaged 0.58 on seeds 101-103 (four runs) and 0.45 over seven runs on seeds 101-106, Gemini 0.00
(three runs) and Sonnet 0.26.

Every run with its cost: `metrics.json`; how each level was built and checked: `LOOP.md`.

## Reproduce

Needs Docker, `uv` and an `ANTHROPIC_API_KEY` in the environment. AfterQuery provides no inference
credits.

The reported seeds ship as ready-to-run Harbor tasks: `tasks/shift-1`, `shift-2` and `shift-3` are
seeds 101, 102 and 103 at level 4, with the briefing and the verifier's calibration filled in
(`./export-tasks.sh` writes them; `./export-tasks.sh 4 <seed>...` writes others). Plain Harbor runs
them as they are:

```
harbor run -p tasks/shift-1 -a opencode -m anthropic/claude-opus-5-5   # the judged agent
harbor run -p tasks/shift-1 -a oracle                                  # the reference, 1.00
harbor run -p tasks/shift-1 -a oracle --ae POLICY=stop-early           # stop-early, 0.00
harbor run -p tasks/shift-1 -a nop                                     # do-nothing, 0.00
```

`run.sh` does the same for any seed and runs several at once. One command runs the reference, both
baselines and Opus on the committed run's seed:

```
LEVEL=4 SEED=101 ./run.sh reference nop stop-early opus
```

Expect 1.00, 0.00, 0.00 and, for Opus, anything from 0.1 to 0.7 on this seed (0.11, 0.18 and 0.73
in three runs; 0.32 mean over nine runs on 101-103). Results land in
`jobs/<name>/`. `run.sh` writes a Harbor task for the episode to `jobs/variants/` and calls
`harbor run -p <task> -a opencode -m anthropic/claude-opus-5-5`, so a judge can rerun that folder
with plain Harbor. Stop-early and the other scripted policies run as Harbor's `oracle` agent with
`POLICY=<name>`. `SEED` picks the episode (held-out 101-106); `ATTEMPTS=3` gives three Opus runs.

Committed run log: `runs/r4-l4-s101-opus-130256/` (Opus 5.5, level 4, seed 101, score 0.5728,
recorded before the instruction gained its sentence on the healthy baseline;
transcript in `agent/opencode.txt`, signed action log in `artifacts/ledger/receipt.json`).

`./eval.sh <round> <level> <seed> <run>...` does the same as `run.sh` and records the result in
`metrics.json`.

## Test

```
python3 eval.py --fuzz 200
```

Plays every scripted policy on the build and held-out seeds, checks that each replay is
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
- `explain.py`: prints what an agent did, step by step, from its signed action log.
