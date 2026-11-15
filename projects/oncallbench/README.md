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

Every run behind the scores above, with its cost: `metrics.json` (the clean-machine reruns under
Reproduce are in `runs/` instead); how each level was built and checked: `LOOP.md`.

**Common seeds.** Every model is compared on the same 24 level-4 seeds, **200000-200023**, kept out
of all training and model selection: no demo, tuning or training run used them, and the Gemma
checkpoint was not chosen on them (the base and SFT models had been evaluated there in our own runner,
`rl/RESULTS.md`). Every result goes into `metrics.json` (round 16) and this section whatever it is.

| Agent (level 4, seeds 200000-200023) | Harness | Runs / seeds | Mean (95% CI) | Median | Solve rate | Worse than doing nothing |
| --- | --- | --- | --- | --- | --- | --- |
| Reference (expert script) | scripted, replayed in the simulator | 24 / 24 | 1.00 (1.00-1.00) | 1.00 | 100% | 0% |
| **Opus 5.5** | Harbor + OpenCode | 48 / 24 | **0.45 (0.35-0.54)** | 0.54 | 2% | 21% |
| Gemma 4 26B-A4B, untrained | Harbor + OpenCode | 48 / 24 | 0.05 (0.02-0.07) | 0.00 | 0% | 38% |
| Nemotron 3.5 Lightning 30B-A3B, untrained | Harbor + OpenCode | 24 / 24 | 0.04 (0.01-0.08) | 0.00 | 0% | 67% |
| Nemotron 3.5 Super VL (NVFP4), untrained, served with vLLM | Harbor + OpenCode | 48 / 24 | 0.03 (0.01-0.06) | 0.00 | 0% | 90% |
| Gemma 4 26B-A4B + our SFT adapter alone (no RL) | Harbor + OpenCode | 48 / 24 | 0.39 (0.32-0.47) | 0.41 | 0% | 15% |
| Gemma 4 26B-A4B + our adapter (SFT, then RL on the score) | Harbor + OpenCode | 48 / 24 | 0.44 (0.35-0.53) | 0.45 | 4% | 17% |
| `shotgun` script: finds the cause, guesses the fix | scripted, replayed in the simulator | 24 / 24 | 0.47 (0.36-0.57) | 0.55 | 0% | 12% |
| Do-nothing | scripted, replayed in the simulator | 24 / 24 | 0.00 (0.00-0.00) | 0.00 | 0% | 0% |

Partial, so not in the table: Fable 5.2, 13 runs on 13 of the 24 seeds (mean 0.88, 95% CI
0.81-0.93); an Anthropic usage limit cut the other eleven.

Exclusions: runs cut by something outside the agent were excluded and rerun. Untrained Gemma lost 88
attempts: 44 whose agent never reached the model endpoint (no tool call), 41 whose agent container's
Docker network failed and 3 whose verifier container's did (`audit/GEMMA.md`); the adapter row lost
none. Opus lost 3 and Fable 11 to an Anthropic usage limit (Fable's were not rerun). Those were partly
played, and their partial scores stay in `metrics.json`, marked `infrastructure:`: Opus's were 0.64,
0.21 and 0.00, and counting them as well, Opus would average 0.44 over 51 attempts instead of 0.45
over the 48 in the table. Timeouts (Gemma with the adapter 8, untrained 2) and context overflows were
kept and scored as the shifts they left. The SFT-alone row lost 12 attempts to a full disk on the runner
and reran them. The replay site shows seed 200019, one of these seeds; the task blocks that host, and
none of the SFT-alone row's counted runs fetched it. Round 16 ran
every model, Opus included, from task folders named `tasks-custom/seed-2000NN`; folder names are
random since 0d92463f. No transcript mentions a seed.

How the runs end, from each run's signed receipt replayed in the simulator. The fault counter is the
verifier's and leaves overload faults out (`task/tests/grade.py`):

| Agent | Every counted fault fixed | Ended by `finish` | Reached the shift's end | Stopped mid-shift |
| --- | --- | --- | --- | --- |
| Opus 5.5 | 48 of 48 | 33 | 15 | 0 |
| Gemma 4 26B-A4B, untrained | 0 of 48 | 30 | 8 | 10 (minute 20, 26, 27, 71, 76, 83, 85, 87, 104, 118) |
| Nemotron 3.5 Lightning 30B-A3B, untrained | 0 of 24 | 11 | 13 | 0 |
| Nemotron 3.5 Super VL (NVFP4), untrained, served with vLLM | 9 of 48 | 8 | 35 | 5 (minute 114, 116, 117, 119, 119) |
| Gemma 4 26B-A4B + our SFT adapter alone (no RL) | 13 of 48 | 1 | 47 | 0 |
| Gemma 4 26B-A4B + our adapter (SFT, then RL on the score) | 23 of 48 | 0 | 47 | 1 (minute 54) |

Not calling `finish` costs nothing extra: the rest of the shift is simulated and charged either way.
Timeouts at the task's 30-minute agent limit: Gemma with the adapter 8, of which one came
mid-incident (seed 200019, run 2, minute 54, scored 0.00) and seven after the shift had already
reached minute 120 (the model kept making rejected calls; the score covers the whole shift); the SFT adapter alone
8; untrained Gemma 2.

Inference settings. Every round-16 run got the same task message (sha256 `36c50158a50d...`) through
OpenCode 1.19.5 in Harbor 0.25.0, with OpenCode's own system prompt for the provider and no sampling
settings of ours. Opus 5.5 and Fable 5.2: the Anthropic API with OpenCode's defaults. Gemma 4
26B-A4B (all three rows): vLLM with the `gemma4` tool-call and reasoning parsers, the adapter as
a LoRA module, sampling from the model's generation config; untrained and SFT-then-RL on Verda
(`rl/serve.sh`, vLLM 0.33, `--max-model-len 262144`), SFT alone on Modal (`rl/modal_app.py`). Nemotron
3.5 Lightning: vLLM 0.33 on the BF16 weights, 256k context, the `qwen3_coder` tool parser and
`nemotron_v3` reasoning parser. Nemotron 3.5 Super VL: vLLM on NVIDIA's NVFP4 release (no FP8 build
is published).

Scope: these are 24 new seeds of one simulator. They recombine its eight symptom and harmful-change
templates (`sim/incident.py`), so a score here measures how a model handles new incidents of this
kind, not on-call skill in general.

Definitions for this table's calculations: the score is the share of the avoidable cost
avoided, `(cost_do_nothing - cost) / (cost_do_nothing - cost_reference)` clipped to 0..1; a run
**solves** the shift when it scores at least 0.95 of the expert; **worse than doing nothing** means
its cost is strictly above the do-nothing cost on its seed; the 95% CI is a cluster bootstrap over
seeds (seeds drawn with replacement, every run of a drawn seed kept; 10,000 resamples); a row needs
runs on all 24 seeds. Stop-early and "every mitigation on everything that fires" also score 0.00 on
every seed. Generated by `python3 results_table.py` into `results.json`, which the deck renders from.

Gemma's results on other seeds and in our own training runner are in `rl/RESULTS.md`.

**Opus 5.5 averages 0.45 on 24 fresh seeds: all 48 runs below the expert, and 10 cost more than doing
nothing, every one of them through an unprotected rollback** (41 of its 48 runs roll back a hot
service at least once without scaling or throttling it first; it wastes 0.17 mitigations per run).
Fable 5.2 makes the same mistake (9 of 13 runs) but recovers from it far better: the newest model
nearly closes the gap, so level 4 separates Opus-class agents, and a harder level is the next step
(Roadmap). Fable's other eleven runs, and three Opus runs, were cut by an Anthropic usage limit and
are marked as infrastructure failures, not scores; the three Opus runs were rerun and are in the table. This set replaced an earlier pre-registered
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

Gemma 4 26B-A4B with a LoRA adapter trained on OnCallBench (`rl/`): first by imitating the scripted
reference's shifts (SFT), then by reinforcement learning on the score. The RL checkpoint was picked
on held-out seeds 101-106 by a rule committed before the final candidate's evaluation and before the
fine-tuned Harbor runs; the 24 common seeds were not used for the choice, though the base and SFT
models had been evaluated on them first (`rl/RESULTS.md`). Run the way Opus was, OpenCode in Harbor
0.25.0 against a local vLLM server, two runs on each common seed (table above).

Imitating our scripted expert and then fine-tuning on the score took Gemma 4 26B-A4B from **0.05 to
0.44** in the judges' Harbor + OpenCode harness, on 24 seeds kept out of all training and model
selection: a gain of +0.39 (95% interval +0.30 to +0.48), ahead of the untrained model on all 24
seeds. That is statistically indistinguishable from Opus 5.5's 0.45 (paired difference -0.01, 95%
interval -0.15 to +0.13; the adapter is ahead on 13 of 24 seeds), though it gets there differently:
it fixes every fault in 23 of 48 runs where Opus does in 48 of 48, and it rolls back without
protecting the service less often (36 of 95 undos without capacity first, against Opus's 80 of
122). It remains well below the expert it copied. The SFT adapter alone, run the same way, averages
0.39 (0.32-0.47): RL on the score adds about 0.05 to the mean, inside overlapping intervals, and its
clearer effect is on finishing the job, every counted fault fixed in 23 of 48 runs against 13 of 48
without it. None of this shows equivalence to Opus. One shift shows the difference: on seed 200009 the
fine-tuned Gemma reads sms-svc's metrics, scales it from 8 to 13 replicas, reads the diff, and rolls
back once the capacity is there (`r16-l4-s200009-gemma-ft-231645`, steps 15-19); Opus on the same
seed rolls back unprotected at step 13 and the storefront's errors reach about 52%
(`r16-l4-s200009-opus-215320`). Its scores in our own training
runner (`rl/env.py`: a capped number of replies, a shorter context) are higher and not comparable
with Harbor's; they stay in `rl/RESULTS.md`. The adapter is public, with its sha256 and a model card:
https://storage.googleapis.com/katalyst-fyi-models/oncallbench/gemma4-26b-a4b-rl/.

**Try it on Modal.** The same adapter is served from Modal behind an OpenAI-compatible endpoint
(`rl/modal_serve.py`, one H200 or B200), as `gemma26-rl`, beside the untrained `gemma26-base` and
the SFT-only `gemma26-sft`. The logs print each served adapter's sha256, and `gemma26-rl`'s matches
the published one (`f9536c41…`). It scales to zero, so the first request starts a GPU and takes
about six minutes. `curl -L` follows Modal's redirect while it waits:

    URL=https://mikael-87302--oncallbench-gemma-serve.us-east.modal.run
    curl -L $URL/v1/models
    harbor run -p tasks/shift-1 -a opencode -m vllm/gemma26-rl --base-url $URL/v1 \
      --api-format openai_chat_completions --api-key-name VLLM_API_KEY --ae VLLM_API_KEY=none

## Reproduce

Needs Docker with Compose v2 (`docker compose version` must work; on Ubuntu's `docker.io` install
`docker-compose-v2`), `uv`, Harbor 0.25.0 (`uv tool install harbor==0.25.0`; `run.sh` fetches it
by itself) and, for the Opus runs only, an `ANTHROPIC_API_KEY` in the environment. No Python
install is needed: without `python3`, `run.sh` uses uv's, and the other `python3 <script>.py`
commands here run as `uv run --no-project --python 3.13 python3 <script>.py`. AfterQuery
provides no inference credits. A run downloads the base images from Docker Hub, `mcp` from PyPI
and, for the agent, OpenCode through Harbor's installer. Run everything from this folder
(`projects/oncallbench`).

The reported seeds ship as ready-to-run Harbor tasks: `tasks/shift-1`, `shift-2` and `shift-3` are
seeds 101, 102 and 103 at level 4, with the briefing and the verifier's calibration filled in
(`./export-tasks.sh` writes them). Plain Harbor 0.25.0 runs them as they are
(`alias harbor='uvx --from harbor==0.25.0 harbor'`):

```
harbor run -p tasks/shift-1 -a opencode -m anthropic/claude-opus-5-5   # the judged agent
harbor run -p tasks/shift-1 -a oracle                                  # the reference, 1.00
harbor run -p tasks/shift-1 -a oracle --ae POLICY=stop-early           # stop-early, 0.00
harbor run -p tasks/shift-1 -a nop                                     # do-nothing, 0.00
```

On a busy machine Harbor's six minutes for installing OpenCode in the container can run out before
the shift starts (`AgentSetupTimeoutError`); add `--agent-setup-timeout-multiplier 2`.

Shifts 1-3 are the seeds we report. To check that we did not tune for them, export any other seed
and run it the same way, or use `SEED=<seed> ./run.sh ...`:

```
./export-tasks.sh 4 777        # prints e.g. tasks-custom/episode-3f9a2b1c: level 4, seed 777
harbor run -p tasks-custom/episode-3f9a2b1c -a oracle --ae POLICY=stop-early
```

The folder name is random so that the agent cannot learn the seed from it (Harbor names the
containers after the folder); `tasks-custom/index.tsv` lists which folder holds which seed, and
`tasks/` is never touched. On any seed the reference scores 1.00 and doing nothing 0.00 by
construction, since the score is scaled between those two; stop-early and the agents are the runs
worth comparing.

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
it in `reward.json`. `run.sh` writes a Harbor task for the episode to
`jobs/variants/episode-<random>` (it prints which; `jobs/variants/index.tsv` lists them all) and
calls `harbor run -p <task> -a opencode -m anthropic/claude-opus-5-5`, so a judge can rerun that
folder with plain Harbor. Stop-early and the other scripted policies run as Harbor's `oracle` agent
with `POLICY=<name>`. `SEED` picks the episode (the reported seeds are 101-106); `ATTEMPTS=3` gives
three Opus runs.

Committed run logs, each trial with its transcript in `agent/opencode.txt`, its action log in
`artifacts/ledger/receipt.json` and its score and cost breakdown in `verifier/reward.json`:

- `runs/rerun-l4-shift1-opus-x2/`: `harbor run -p tasks/shift-1 -a opencode -m
  anthropic/claude-opus-5-5 -k 2` from a fresh copy of this repository on a machine that had never
  run it (Sat 14 Nov, 4 vCPU, Harbor 0.25.0), before the agent's image moved to Alpine: 0.53 and
  0.26. On the same machine `run.sh reference nop stop-early opus` gave 1.00, 0.00, 0.00 and 0.20
  (5m36s), and the reference again through plain Harbor 1.00 at the same cost to the cent
  ($85,246.31); the logs of those two were not kept.
- `runs/repro-l4-s101-opus-204757/`: the clean-clone rerun of the one command described above,
  Opus 0.00.
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
