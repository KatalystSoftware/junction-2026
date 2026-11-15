# Independent audit of the Gemma benchmark claim

Audited 15 November 2026. The requested claim and calculations were inspected at
`8d8d658b`; this is an evidence review, with no benchmark, training or serving changes.
All times below are UTC. No Harbor jobs, Docker containers, training or model evaluations
were launched. Replaying saved action logs in Python is the only simulator execution used.

## Verdict

**The numerical result holds. The strongest wording about previously unseen seeds,
pre-registration and identical model inputs does not.**

The retained round-16 records really contain 48 runs per Gemma model, exactly two on
each of seeds 200000–200023. Independently calculated means are 0.0463167 untrained
and 0.4354542 with the adapter, with seed-bootstrap intervals that round to
0.02–0.07 and 0.35–0.53. Opus's 0.4479604 rounds to 0.45. All 144 retained receipts
have valid signatures and replay to the archived costs and rewards. The checkpoint
selection arithmetic and the adapter loaded for `gemma26-ft` are corroborated by the
original evaluation records, serving log and matching adapter hashes.

There is no common-seed overlap in the four available SFT demo files or in the RL
training pool. **There were earlier base-model and SFT-adapter evaluations on every
one of these seeds.** The result supports improvement after the combined SFT/RL
training pipeline on seeds held out from optimization. It is not a blind first
evaluation, an estimate of RL's incremental contribution, or a demonstration of
statistical equivalence to Opus.

## Findings, in severity order

### 1. High: these were training-held-out seeds, not previously unevaluated seeds

I parsed every record in every `cache/demos*.jsonl` under
`/home/mikaelsiidorow/junction2026-data/oncallbench/`:

| File | Episodes | Distinct seeds | Seed range | Intersection with 200000–200023 |
| --- | ---: | ---: | --- | --- |
| `demos.jsonl` | 484 | 162 | 1–349 | empty |
| `demos-l3.jsonl` | 211 | 211 | 1–399 | empty |
| `demos-l4.jsonl` | 212 | 212 | 1–399 | empty |
| `demos-l34.jsonl` | 423 | 212 | 1–399 | empty |

The SFT checkpoint's documented input is `demos-l34.jsonl`. Its SHA-256 is
`6c3ad8facb416bfc4e39e06be31ce798bae52751df0ebc118d76eb7ae2cc7c46`.
[run.py](../rl/run.py)'s RL pool is explicitly `range(1000, 100000)`, so its
largest possible training seed is 99999. The historical implementation already
used that bound in `fc78c17a`, before the Gemma runs. `--seeds` controls standalone
evaluation, not that training pool. The SFT and RL code trains only assistant
tokens, with RL advantages calculated from episode rewards; tool observations
are not optimization targets ([core.py](../rl/core.py)).

The stronger no-earlier-evaluation check **fails**, with primary evidence from the
Modal `aq-rl` Volume, retrieved read-only:

| Original Volume directory | Evaluation ended | Episodes | Seeds and levels |
| --- | --- | ---: | --- |
| `/out/audit-sft-fresh/` | 2026-11-14 18:45:06 | 192 | 4 samples on every seed 200000–200023, at each of levels 3 and 4 |
| `/out/audit-base-fresh/` | 2026-11-14 19:09:42 | 192 | the same |

Both directories contain `evals.jsonl`, the corresponding `eval-<tag>.jsonl` with
per-episode conversations and seed fields, and `run.log`. I parsed the 384 episode
records; all 24 common seeds appear in both files. The SFT level-4 mean is 0.5871;
the base mean is 0.0670. These precede the first common-seed Opus Harbor job
(21:44:03), first base Harbor job (21:54:21), and first fine-tuned Harbor job
(23:16:10). They also precede the common-seed run-list commit `ad7d8e1a` at
21:51:44. [RESULTS.md](../rl/RESULTS.md)'s earlier “fresh 200000+” evaluations are
therefore literal earlier exposures, not merely a different range with similar names.

This is evidence of prior evaluation exposure, **not evidence that these episodes
were used for gradient updates**. The available code, demos and training summaries
support their exclusion from optimization. Because outcomes were available before
the common seed set was adopted, the Harbor result should not be advertised as an
untouched test set. I cannot infer from these artifacts whether knowledge of those
outcomes influenced that adoption.

The checkpoint rule also was not fixed “before any evaluation run.” Commit
`53589a88326c9fbdc3583348e9018612131f5e74` at 21:32:29 records the B200 candidate's
already completed final evaluations. Its step-24 and final evaluations ended at
19:29:50 and 19:30:20. The rule did precede the RTX candidate's final evaluations
(22:49:06 and 22:53:50), the recorded winner, and the fine-tuned Harbor jobs.
“Fixed before the final candidate's evaluations and the fine-tuned Harbor runs”
is the supportable chronology.

### 2. Medium: a shared harness does not mean an identical system prompt or token budget

The task and user-supplied limits match. For all 144 retained trials:

- OpenCode reports version **1.19.5**; every `extra_instruction_paths`,
  `extra_instructions`, agent `skills`, and agent `kwargs` list/object is empty.
- The task instruction recovered in `agent/trajectory.json` is byte-identical
  across all models, SHA-256
  `36c50158a50d91fb9fb659ca6dafe397c590b4ed8c777fd167dd6af9bc36c456`.
- The durable `lock.json` task digest matches across all three models for each
  seed, including the four early retained base trials. The older
  `result.json.task_checksum` strings differ, so I checked the durable digest
  rather than assuming those strings proved a task change.
- Timeout multiplier is 1, with no agent timeout override. The task gives the
  agent 1800 seconds, the separate verifier 120 seconds, a 120-minute simulated
  shift and 400 counted tool calls. All models have the same 3× installation
  timeout multiplier. That last multiplier changes installation time, not thinking
  or incident time.
- The same `ops` MCP interface and ordinary OpenCode tools are available. There
  is no configured Gemma-only task hint or custom prompt. The native training
  harness's extra nudge and 48-reply cap are not injected into these Harbor runs.

But OpenCode itself selects model-dependent prompts. In the exact
[v1.19.5 system-prompt dispatcher](https://github.com/anomalyco/opencode/blob/v1.19.5/packages/opencode/src/session/system.ts),
an ID containing `claude` gets `prompt/anthropic.txt`; `gemma26-base` and
`gemma26-ft` fall through to `prompt/default.txt`. Their first sentences differ:
“You are OpenCode, the best coding agent on the planet” versus “You are opencode,
an interactive CLI tool…”. These are ordinary coding-agent prompts; neither
contains incident-specific hints. Consequently, “no extra task prompt” passes;
“the same system prompt” does not.

The original vLLM log confirms **262144 tokens**, bfloat16, vLLM **0.33.0**, the
base model `google/gemma-4-26B-A4B-it`, Gemma tool/reasoning parsers, and no
quantization. It records the model's generation defaults as **temperature 1.0,
top-k 64, top-p 0.95**. Both Gemma conditions use this server. The custom model
entries supplied by Harbor do not declare OpenCode context/output limits; Opus
uses its provider's catalog and API defaults. The archived records do not preserve
the complete resolved Opus request settings or model catalog, so equal context,
output-token and sampling limits cannot be certified. No retained Gemma trial has
a context-overflow exception; the 2 base and 8 adapter wall-time timeouts remain
scored results.

This is a reasonable comparison of systems using the judges' ordinary harness,
with the particularly strong base-versus-adapter comparison sharing server defaults.
It is not a controlled comparison with every prompt and token budget held constant.

### 3. Medium: exclusions are supported, but the missing-result description is too broad

I read the trial results, exception messages, agent logs and receipt/reward
presence for **all 88 archived failed untrained jobs**, not just the 44 marked
in `metrics.json`. The exhaustive run inventory is below.

| Failure | Jobs | Evidence in each job |
| --- | ---: | --- |
| Agent environment could not start | 41 | Docker reports “all predefined address pools have been fully subnetted”; no agent execution, receipt or verifier reward |
| Agent ran; separate verifier environment could not start | 3 | the same Docker network error when creating `__verifier__trial_default`; saved receipts contain 59, 34 and 85 actions; no verifier reward |
| Agent could not reach vLLM after the bridge changed | 44 | configured URL is `http://172.17.0.1:8100/v1`; OpenCode reports `ETIMEDOUT: Unable to connect`; no tool-use events, no model input-token result, zero receipt actions, reward 0 |

For the first 44, Harbor's `verifier.started_at` exists in the three cases where
it entered verifier orchestration; the verifier container itself failed to start.
“44 never produced a score” is accurate. “All 44 agents never ran” is not.
For the second 44, the verifier did run and correctly scored an empty action log.
These are the 44 `infrastructure:` Gemma metric rows.

The three recoverable receipts are:

| Job / trial | Actions | Independently replayed score |
| --- | ---: | ---: |
| `r16-l4-s200000-gemma-base-215422/seed-200000__ZdnAcbi` | 59 | 0.1392445720 |
| `r16-l4-s200001-gemma-base-215424/seed-200001__NmtVAeE` | 34 | 0 |
| `r16-l4-s200001-gemma-base-215426/seed-200001__NW3xWm2` | 85 | 0 |

All three signatures validate. Adding all three to the 48 retained base runs
gives **0.0463224 over 51 runs**, still 0.05 rounded. This is an unbalanced
sensitivity check, not a replacement for the two-runs-per-seed estimate. There
is no evidence of a real low Gemma score being relabelled to raise the mean:
the two model-side base timeouts, including a score of zero, were retained.

The policy estimates performance conditional on working infrastructure. Replacing
endpoint failures before any model response is defensible; treating those as
model zeros would instead measure availability. Rerunning after a verifier failure
can introduce selection if failure depends on run duration or behavior, and
concurrency changed after the failed batch. Regrading available receipts would
avoid discarding completed behavior. Here the three recoverable omissions have
negligible effect, so I find no numerical evidence that the policy explains the
base/adapter gap. It is not a guarantee that such a policy is unbiased generally.

The other **14** `infrastructure:` metric rows also have a real external error:
every agent log contains Anthropic's “You have reached your specified API usage
limits” message and Harbor reports `ApiUsageLimitError`. They are not all
zero-action or unscored runs: seven have partial action logs and valid rewards,
including two Fable rewards near 1. The full list is below. In particular, the
three excluded Opus rewards are 0.6431, 0.2124 and 0; including all 51 scored
Opus attempts gives 0.4384 rather than 0.4480. This does not change the Gemma
rows, but “infrastructure” must explicitly include externally interrupted partial
trajectories, with their original scores retained in the evidence.

I also scanned trial configs throughout the supplied data tree for missing
`verifier/reward.json`, rather than treating file absence as proof of a failure.
There are 99 such trial folders in the inspected archive: the 44 Docker failures,
27 trials in `jobs-cancelled/`, 4 later Nemotron trials, and 24 later SFT-only
trials under `sft-runs/`. The latter include 7 with disk-full logs, 13 agent-install
failures and 4 cancellations. The Nemotron four have 3 disk-full failures and
1 installer failure. The 27 earlier cancelled trials are 18 round-15 jobs on
404/418/500/502/503/504 plus 9 `like4c` SFT trials on 101–103; some have already
executed an agent, and some have incomplete result files. Cancellation is not
itself proof of a pre-action infrastructure failure. These other conditions do
not supply or replace any `gemma-base`/`gemma-ft` table observation. I do not
certify every missing verifier file anywhere in the tree as one of the 88 failures.

### 4. Medium: the combined training result is real; the table does not isolate RL

[run.py](../rl/run.py), [demos.py](../rl/demos.py), the SFT loss records and the
60-step RL reward/evaluation records support the stated training history: reference
trajectory imitation, followed by updates using the simulator score. The winning
adapter is not the SFT adapter. However, the table lacks an SFT-only condition on
the same 24 seeds with the same completed Harbor protocol. The earlier SFT
results on 101–103 and the native-runner results cannot measure RL's incremental
contribution to this Harbor row. “SFT then RL produced this checkpoint” holds;
“RL caused the 0.05→0.44 improvement” is not established separately.

The eight final-adapter transcripts below show observation-dependent diagnosis
within a recognizable learned procedure. They do not establish general reasoning
outside this environment or rule out template learning. Conversely, a fixed
sequence of service names and mitigations does not describe what these runs do.

## Which adapter was actually served

The rule in `53589a8` chooses the mean of each candidate's last step and final
held-out level-4 evaluations on 101–106, with eight samples per seed. Raw summaries
give:

| Candidate | Last-step mean | Final mean | Selection mean |
| --- | ---: | ---: | ---: |
| `gemma26-rl-l4` | 0.6396 | 0.7524 | 0.69600 |
| `gemma26-rl` | 0.8083 | 0.7764 | 0.79235 |

The RTX summaries are preserved in `rl/out/evals.jsonl` and
`~/junction2026-data/oncallbench/out-verda/`. I also read the original B200
`/root/aq/spikes/aq-incident/rl/out/evals.jsonl` on `95.133.252.163`.
Commit `e03a30d5d8b6e6a2e9555cb2ffed4494cf98bc13`, at 22:58:43, records the correct
winner before the fine-tuned Harbor batch.

More decisively, the original server on that machine retains
`/root/aq/spikes/aq-incident/rl/serve-main.log`. At line 7162 it says:

> INFO 11-14 23:16:08 … Loaded new LoRA adapter: name 'gemma26-ft', path
> '/root/aq/spikes/aq-incident/rl/ckpt/gemma26-rl-rtx'

The next line records HTTP 200 for `/v1/load_lora_adapter`. There is no subsequent
adapter reload/unload in that log. All 48 target trial configs and trajectories
name `vllm/gemma26-ft`; their first job starts at 23:16:10.848486. The loaded file,
hashed read-only on the original server, is:

```text
f9536c413988047e1b0092f1ac49fe24f3604ab274bb470403f6c3f1914f2082
```

That exactly matches the local archived
`ckpt-verda/gemma26-rl-final-0049/adapter_model.safetensors` and the documented
`f9536c41…` checkpoint. It differs from the SFT hash `588e977f…` and the archived
midrun checkpoint `759be744…`. The server log's own SHA-256 is
`2f6284f7074b97250440381583c9efe70b28d1fdf9e8d9ea85fbdfaf5087edbe`.
This is strong affirmative provenance, although the individual trial receipts
do not themselves sign a model-weight digest.

## Transcript findings

I read eight `gemma-ft` and four `gemma-base` OpenCode event transcripts, including
their observations and rejected calls. Repeated identical failure loops are
counted below rather than reproduced. These are purposive examples across seeds
and score levels, not a random estimate of behavior frequency.

Every link below points to the committed copy of `agent/opencode.txt`; I checked
that all 144 retained transcripts and receipts match their full-job archive
copies byte for byte. Closing messages in `loop-evidence/final-messages/` exist
for all 144; those messages are evidence of what the agent said, not its grade.

| Model | Seed | Score | Transcript and observed behavior |
| --- | ---: | ---: | --- |
| ft | 200000 | 0 | [231610 / eD67rp4](../runs/common/r16-l4-s200000-gemma-ft-231610/seed-200000__eD67rp4/agent/opencode.txt): traces `wishlist-svc → stock-svc`, reads the currency-key diff and rolls it back; leaves `audit-svc` throttled at 71% through minute 120; then 572 rejected log calls |
| ft | 200003 | 0.3961 | [231620 / qc9cHjP](../runs/common/r16-l4-s200003-gemma-ft-231620/seed-200003__qc9cHjP/agent/opencode.txt): reads the TTL deploy diff on `bundles-svc`, later finds `risk-svc`'s pool-size regression; repeatedly scales a leaking service and a harmless batch-job service; 541 log calls after shift end |
| ft | 200005 | 1.0000 | [231628 / QHsr53F](../runs/common/r16-l4-s200005-gemma-ft-231628/seed-200005__QHsr53F/agent/opencode.txt): primary-node error leads to failover; follows `reviews-svc → profile-svc`, scales before rollback; rejects a benign late deploy diff and undoes the bad TTL config instead |
| ft | 200008 | 0.7833 | [231641 / T4wLDyY](../runs/common/r16-l4-s200008-gemma-ft-231641/seed-200008__T4wLDyY/agent/opencode.txt): scales `promo-cache` before rollback; compares deploy and config on `sitemap-svc`, reverting the currency-field config, not the benign deploy |
| ft | 200012 | 0.7575 | [231737 / 89Tohbf](../runs/common/r16-l4-s200012-gemma-ft-231737/seed-200012__89Tohbf/agent/opencode.txt): diagnoses different deploy/config faults from diffs; protects `events-queue` with scale, but rolls back `payments-svc` unprotected |
| ft | 200015 | 0.1935 | [231811 / oek3Qez](../runs/common/r16-l4-s200015-gemma-ft-231811/seed-200015__oek3Qez/agent/opencode.txt): correct scope-removal diagnosis, unprotected `checkout-svc` rollback, capacity added much later; repeatedly investigates a leak without restarting it |
| ft | 200019 | 0 | [231847 / 7XpRYta](../runs/common/r16-l4-s200019-gemma-ft-231847/seed-200019__7XpRYta/agent/opencode.txt): distinguishes a TLS config fault from a benign deploy; reduces `geo-svc` capacity before fixing its deploy; times out at simulated minute 54 |
| ft | 200023 | 0.9827 | [231931 / U7KJDor](../runs/common/r16-l4-s200023-gemma-ft-231931/seed-200023__U7KJDor/agent/opencode.txt): finds primary failure, wire-schema config and quiet currency-key deploy; scales the quiet fault before rollback; later follows a new upstream error to a scope-removal deploy |
| base | 200000 | 0 | [215420 / o2M7aAr](../runs/common/r16-l4-s200000-gemma-base-215420/seed-200000__o2M7aAr/agent/opencode.txt): reads a bad deploy diff but first reverts config; then rolls back unprotected and makes 1048 rejected scale calls while the rollback is in progress |
| base | 200001 | 0 | [224423 / nsiu2UQ](../runs/common/r16-l4-s200001-gemma-base-224423/seed-200001__nsiu2UQ/agent/opencode.txt): 43 metrics calls; first scale only at minute 85; finishes with underlying faults still present |
| base | 200008 | 0.3350 | [224444 / CNTiayy](../runs/common/r16-l4-s200008-gemma-base-224444/seed-200008__CNTiayy/agent/opencode.txt): correctly reverts two bad configs; leaves a 50% throttle active after retry load drains |
| base | 200023 | 0.2209 | [224531 / xFZyYHS](../runs/common/r16-l4-s200023-gemma-base-224531/seed-200023__xFZyYHS/agent/opencode.txt): finds wire-schema config and primary failure, but spends 37 calls on metrics and scales the residual storm only at minute 93 |

Short passages that support diagnosis rather than a seed-independent replay:

- **Different diffs produce different fixes.** Seed 200008, lines 87–93: the
  `sitemap-svc` deploy changes logging/dependencies, whereas its config says
  `price_fields: [amount, currency, vat] -> [amount, vat]`; the next action is
  `ops_revert_config`. Seed 200023, lines 71–74, instead shows
  `cur = row.get("currency", "EUR")` becoming `cur = row["currency"]`, followed
  by `ops_rollback` on `vouchers-svc`.
- **A primary failure produces a different action.** Seed 200005, lines 23–26:
  “primary node unreachable, write rejected” from `events-queue`, followed by
  `ops_failover`, not rollback.
- **It still makes Opus's unprotected-rollback mistake.** Seed 200015, lines
  20–29: `checkout-svc` logs “retry storm: 71% of incoming requests are retries”
  and “scope 'orders.write' missing”; after reading the matching deploy diff,
  it calls `ops_rollback` at minute 14 without scaling or throttling that service.
  At lines 137–143, minute 77 metrics still show about 40% errors and 99% CPU;
  it finally scales at minute 80. The earlier throttle was on **cart-svc**, not
  checkout. Opus's two runs on this same seed also roll back checkout without
  protecting it, at pre-call minutes 12 and 14.
- **The base can diagnose, but often too late.** Its seed-200001 closing message
  admits: “I scaled `ranking-svc` from 4 to 8 replicas at minute 85 … reduced
  its error rate from ~86% to ~65%”. Its seed-200008 message says it applied a
  50% throttle “to allow the service to recover”; the transcript shows it never
  lifts that throttle before finishing.

As a broader check, I independently walked all retained receipts in order,
reconstructing clock advances and the scale/throttle guard definition in
`judge.py`. The final adapter has **27 unprotected rollback/restart actions in
22/48 runs**, versus **66 in 41/48** for Opus and **24 in 19/48** for base.
This measures whether a prior above-normal scale or nonzero throttle was still
recorded for that service; it does not prove that the guard was adequate. Every
adapter rollback/config revert was preceded by a diff read on that service
(129/129), versus 56/60 for base and 150/168 for Opus. This supports tool-dependent
behavior but is not a causal counterfactual test. The original SFT counterfactual
probes in `audit.py` concern a different checkpoint unless explicitly rerun for RL.

## Independent numbers and grading integrity

I independently selected round 16, the three named model conditions and seeds
200000–200023, excluding only `failure.startswith("infrastructure:")`. Each
condition has exactly two retained trials on each seed; there are no duplicate
trial IDs. I did not import or execute `results_table.py` to obtain these numbers.

| Model | Runs / seeds | Mean | 95% seed-bootstrap interval | Worse than nothing | Median | Score ≥0.95 |
| --- | --- | ---: | --- | --- | ---: | --- |
| Gemma base | 48 / 24 | 0.0463166667 | 0.0245875000–0.0706687500 | 18/48 = 37.5% | 0.00125 | 0/48 |
| Gemma adapter | 48 / 24 | 0.4354541667 | 0.3462958333–0.5254770833 | 8/48 = 16.6667% | 0.44535 | 2/48 |
| Opus | 48 / 24 | 0.4479604167 | 0.3508145833–0.5420625000 | 10/48 = 20.8333% | 0.53955 | 1/48 |

These match `results.json` and the requested README row, including rounding
37.5% to 38%. Bootstrap units are seeds, not 48 independent episodes. The
interval is conditional on this model/checkpoint, selected seeds and exclusion
policy; it does not include uncertainty from their selection or earlier exposures.

This standalone calculation reproduces the two Gemma rows from this folder's
parent (`projects/oncallbench`), using only the standard library and the saved
do-nothing costs. Equal run counts let seed means be resampled directly:

```python
import json, random, statistics
from pathlib import Path

metrics = json.loads(Path("metrics.json").read_text())
null = {r["seed"]: r["cost_null"] for r in json.loads(
    Path("loop-evidence/common-scripted.json").read_text())}
seeds = list(range(200000, 200024))
for model in ("gemma-base", "gemma-ft"):
    rows = [r for r in metrics if r["round"] == 16 and r["run"] == model
            and r["seed"] in seeds
            and not r.get("failure", "").startswith("infrastructure:")]
    assert len(rows) == 48 and len({r["trial"] for r in rows}) == 48
    by_seed = {s: [r["score"] for r in rows if r["seed"] == s]
               for s in seeds}
    assert all(len(v) == 2 for v in by_seed.values())
    rng = random.Random(0)
    boot = sorted(sum(sum(by_seed[rng.choice(seeds)]) for _ in seeds) / 48
                  for _ in range(10000))
    print(model, statistics.mean(r["score"] for r in rows),
          (boot[250], boot[9749]),
          sum(r["sim_cost"] > null[r["seed"]] for r in rows) / 48)
```

For all 144 retained trials I also verified the receipt signature, replayed its
actions in the deterministic simulator and compared total cost and reward to
`verifier/reward.json`, the Harbor trial result and the metric row. Every receipt
passes. Metrics round rewards to four decimals and costs to cents; discrepancies
are within that rounding. The 144 committed receipt and OpenCode transcript
copies match the full-job originals byte for byte.

The verifier uses the action log, not the agent's reported success or closing
message. [grade.py](../task/tests/grade.py) checks the signature, replays and
settles the shift, and calculates the normalized score. The sidecar writes
`/ledger/receipt.json`; the agent mounts the ledger read-only, and the verifier
runs in a separate container ([docker-compose.yaml](../task/environment/docker-compose.yaml),
[test.sh](../task/tests/test.sh), [server.py](../task/environment/mcp-server/server.py)).
Thus the evidence supports “the model cannot set its reward by writing a score
or claiming success.” It should not be presented as the HMAC alone preventing
forgery: its key is public source, and the write boundary is container/volume
isolation. The README already acknowledges that and the remaining public-reference
download shortcut. This review found no score tampering; it is not an exhaustive
new sandbox exploit audit.

## Exhaustive excluded-run inventory

For the next table, every entry expands to
`~/junction2026-data/oncallbench/jobs-infra-failed/r16-l4-s<seed>-gemma-base-<suffix>/`.
Each folder's one `seed-<seed>__*` trial was inspected. **D** means the Docker
address-pool failure above (41 before agent start, 3 at verifier-container
creation); **B** means endpoint timeout with zero tool-use events/actions.
There are 44 suffixes in each column. Both retained Gemma conditions have exactly
two valid trials per seed in every row.

| Seed | D: Docker failure job suffixes | B: unreachable endpoint job suffixes |
| --- | --- | --- |
| 200000 | 215422 | 222503 |
| 200001 | 215424, 215426 | 222506, 222508 |
| 200002 | 215428, 215430 | 222509, 222511 |
| 200003 | 215432, 215434 | 222512, 222514 |
| 200004 | 215436, 215438 | 222515, 222517 |
| 200005 | 215440, 215442 | 222518, 222520 |
| 200006 | 215444, 215446 | 222521, 222523 |
| 200007 | 215448, 215450 | 222524, 222526 |
| 200008 | 215452, 215454 | 222527, 222529 |
| 200009 | 215456, 215458 | 222530, 222532 |
| 200010 | 215500, 215502 | 222533, 222535 |
| 200011 | 215506 | 222536 |
| 200012 | 215510 | 222539 |
| 200013 | 215512, 215514 | 222542, 222544 |
| 200014 | 215516 | 222545 |
| 200015 | 215520, 215522 | 222548, 222550 |
| 200016 | 215524, 215526 | 222551, 222553 |
| 200017 | 215528, 215530 | 222554, 222556 |
| 200018 | 215532, 215534 | 222557, 222559 |
| 200019 | 215536, 215538 | 222600, 222602 |
| 200020 | 215540, 215542 | 222603, 222605 |
| 200021 | 215544, 215546 | 222606, 222608 |
| 200022 | 215548, 215550 | 222609, 222611 |
| 200023 | 215552, 215554 | 222612, 222614 |

The other 14 excluded metric rows are in `~/junction2026-data/oncallbench/jobs/`.
Each has the explicit API-usage-limit error, a verifier reward and the following
accepted-action count. Positive rewards here are partial trajectories, not zeros
invented by the table script.

| Job | Actions | Archived reward |
| --- | ---: | ---: |
| `r16-l4-s200011-fable-220224` | 70 | 0.7034 |
| `r16-l4-s200013-fable-220243` | 37 | 1.0000 |
| `r16-l4-s200014-fable-220325` | 47 | 0.9989 |
| `r16-l4-s200016-fable-220550` | 8 | 0.0345 |
| `r16-l4-s200017-fable-220622` | 0 | 0 |
| `r16-l4-s200018-fable-220642` | 0 | 0 |
| `r16-l4-s200019-fable-220647` | 0 | 0 |
| `r16-l4-s200020-fable-220726` | 0 | 0 |
| `r16-l4-s200021-fable-220730` | 0 | 0 |
| `r16-l4-s200021-opus-220425` | 40 | 0.6431 |
| `r16-l4-s200022-fable-220723` | 0 | 0 |
| `r16-l4-s200022-opus-220453` | 21 | 0.2124 |
| `r16-l4-s200023-fable-220727` | 0 | 0 |
| `r16-l4-s200023-opus-220517` | 14 | 0 |

## Required wording

Keep the table's Gemma numbers. A defensible statement is:

> A Gemma 4 26B-A4B LoRA checkpoint trained by SFT on scripted-reference
> trajectories and then RL on the environment score averaged 0.44 (95% seed-
> bootstrap CI 0.35–0.53) in 48 Harbor + OpenCode runs, two on each of 24 level-4
> seeds held out from training. Untrained Gemma averaged 0.05; Opus averaged
> 0.45 in the same task and harness. Base and SFT Gemma had previously been
> evaluated on these seeds in our native runner. The RL checkpoint was selected
> using seeds 101–106 by a rule committed before the final candidate's evaluations
> and the fine-tuned Harbor runs. This comparison measures the combined training
> pipeline and does not isolate RL's contribution or establish equivalence to Opus.

Also say that ordinary model-specific OpenCode prompts and serving defaults apply,
and that 88 base attempts were replaced for documented infrastructure failures:
41 agent-container network failures, 3 verifier-container network failures, and
44 endpoint failures before any tool use. Say that the grader replays a sidecar-
written, read-only-to-agent action log; do not credit the public HMAC key with
being an independent security boundary.

Upstream `8d0b00bb` already narrows the training/previous-evaluation and checkpoint
wording. That improves the claim relative to the inspected starting revision;
the evidence and remaining qualifications above still apply. This audit changes
only this report.

For reproducibility, the inspected `metrics.json` SHA-256 was
`4acf2e4453ee118578b87e648fd50d6a73c302b8d774848bf0960910fc49fd81`;
`results.json` was
`e21a7f4b4cb2399efc90d1aa1a43fc75844b9554b483fa1157e69223e9b0f11b`.
Subsequent rows added for other model conditions are outside this audit.
