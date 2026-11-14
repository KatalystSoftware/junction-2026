# Results: can an open model learn on-call from aq-incident?

Yes. Qwen3.5-2B, trained by reinforcement learning on nothing but the environment's own score,
goes from 0.59 / 0.16 / 0.08 to 0.97 / 0.34 / 0.23 on the held-out seeds at levels 0 / 1 / 2 in 20
steps (about 70 GPU-minutes). With the reference's trajectories as SFT data first it reaches 1.00 /
0.96 / 0.93, and RL on the score then lifts that model on level 3, where it saw no demos, from 0.16
to 0.29. All numbers are the environment's score, `clip((cost_null - cost) / (cost_null - cost_ref), 0, 1)`,
on held-out seeds 101-106: do-nothing is 0.00, the scripted reference 1.00.

**Two harnesses, never mixed.** Every score in the Qwen and Gemma tables up to "Gemma 4 26B-A4B in
Harbor" comes from our own runner (`env.py`: the simulator in process, at most 40 or 48 replies of up
to 4 tool calls, a 16k or 32k context). It is the same reward against the same reference, but not the
Harbor + OpenCode harness that produced the README's Opus numbers, so those scores are **not
comparable** with Opus's. The Harbor + OpenCode runs are in their own tables in the last sections.

**"Held-out" means held out from training.** Seeds 101-106 were in no demo and no RL batch. They are
not unseen by the project: the Opus runs in the README used them, and 101-103 measured the gap
between Opus and the reference while level 4 was built.

## Qwen3.5-2B (levels 0-2, simulator pinned at `aec3d09`)

Our own runner (`env.py`, 40 replies, 16k context), not Harbor + OpenCode; not comparable with the
README's Opus numbers. Mean score over 8 sampled episodes per held-out seed (48 per level; T 0.7,
top-p 0.8, top-k 20, Qwen's non-thinking settings), ± one standard error.

| Model | Level 0 | Level 1 | Level 2 | Level 3 |
| --- | --- | --- | --- | --- |
| Do-nothing | 0.00 | 0.00 | 0.00 | 0.00 |
| Reference (scripted) | 1.00 | 1.00 | 1.00 | 1.00 |
| Qwen3.5-2B, untrained | 0.586 ± 0.070 | 0.156 ± 0.032 | 0.079 ± 0.019 | 0.016 ± 0.006 |
| + RL on the score (20 steps) | **0.967 ± 0.021** | **0.341 ± 0.028** | **0.231 ± 0.037** | |
| + SFT on reference demos | **0.999 ± 0.001** | **0.959 ± 0.021** | **0.928 ± 0.028** | 0.158 ± 0.027 |
| + SFT, then RL on level 3 (20 steps) | | | | **0.288 ± 0.021** |

Level 3 (60 services, partial alert list, `get_diff`, $10,000 per wasted mitigation) was never in
the SFT data; its row shows what RL on the score adds where imitation stops.

### What changed the result

- **RL on the plain score works from the untrained model.** The untrained model reasons sensibly
  but writes long explanations (most episodes hit the 16k context before the shift ends) and picks
  wrong mitigations (a rollback on a datastore whose primary is down). Group-relative policy
  gradient on the clipped score taught it to act in short replies: context overflows fell from 52
  of 64 episodes per step to 6-13, and the training reward rose from 0.15-0.18 to about 0.6.
- **The unclipped score as a training reward made things worse.** With `(cost_null - cost) /
  (cost_null - cost_ref)` left unclipped (floored at -2), held-out scores fell after 10 steps
  (0.54 / 0.05 / 0.08 against 0.94 / 0.27 / 0.25 for the clipped score on the same seeds). The
  large negative rewards of episodes that waste mitigations dominate the advantages, and the
  cheapest way to avoid them is to do less. Stopped at step 10.
- **Full-parameter RL turned unstable after step 20.** Without a KL term at lr 2e-6, replies without
  a tool call climbed from ~250 per step to over 1,100 at step 24 and the reward fell to 0.25. The
  step-20 checkpoint is the one reported; a KL anchor or a lower rate after step 15 is the obvious
  fix and was not tried.
- **SFT on reference demos is most of the gain on the levels it covers.** 484 demos (levels 0-2,
  build seeds 1-12 and training seeds 200-349) of the reference's decisions, two epochs. The demos
  check in every 10 minutes instead of the reference's every minute, so they score 0.97 rather
  than 1.00 at levels 1-2, and the SFT model matches them.
- **RL on the score keeps improving the SFT model where its demos stop.** At level 3 the SFT model
  scores 0.158; 20 steps of RL on level-3 training seeds (about 30 GPU-minutes) took it to 0.288 on
  8 samples per held-out seed (4-sample evals during training: 0.17 at step 0, 0.35 at step 10,
  0.35 at step 20). Five of six held-out seeds improved and the sixth held: seeds 101-106 went
  from 0.03 / 0.21 / 0.09 / 0.01 / 0.46 / 0.15 to 0.17 / 0.43 / 0.32 / 0.09 / 0.44 / 0.28.

### Learning curves

Training reward per step (64 episodes: 8 training seeds × 8 samples, T 1.0), and held-out evals
every 10 steps (4 samples per seed).

`rl-base`, from the untrained model, levels 0-2, clipped score, lr 2e-6:

| Step | 1 | 5 | 10 | 13 | 15 | 16 | 18 | 20 | 22 | 24 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Train reward | 0.18 | 0.15 | 0.39 | 0.61 | 0.57 | 0.69 | 0.63 | 0.63 | 0.61 | 0.25 |
| Context overflows / 64 | 52 | 61 | 50 | 27 | 20 | 11 | 6 | 10 | 20 | 45 |

| Held-out (4 samples) | Level 0 | Level 1 | Level 2 |
| --- | --- | --- | --- |
| Step 0 | 0.610 | 0.174 | 0.139 |
| Step 10 | 0.945 | 0.275 | 0.252 |
| Step 20 | 0.948 | 0.345 | 0.225 |

`rl-sft-l3`, from the SFT model, level 3 only, clipped score, lr 2e-6: training reward 0.15-0.24
over steps 1-8, 0.26-0.41 over steps 9-21; held-out 0.171 (step 0), 0.346 (step 10), 0.349 (step 20).

`rl-base-raw` (unclipped score): training reward 0.09-0.18 over 10 steps, no trend; held-out at
step 10 0.539 / 0.051 / 0.080.

## Gemma 4 26B-A4B (levels 3-4)

Gemma 4 26B-A4B (`google/gemma-4-26B-A4B-it`), post-trained with a rank-32 LoRA adapter on the
reference's demos, goes from 0.10 / 0.04 to **0.75 / 0.55** on the held-out seeds at levels 3 / 4,
the two hardest levels. The adapter was trained on Verda and evaluated on Modal; it is public at
<https://storage.googleapis.com/katalyst-fyi-models/oncallbench/gemma4-26b-a4b-sft/> (sha256 below).

Every score here comes from our own runner (env.py): the simulator in-process, at most 48 replies of
up to 4 tool calls, a 32k context. It is the same reward against the same reference, but not the
Harbor + OpenCode harness that produced the Opus numbers in the README, so the two are not
comparable. The Harbor + OpenCode runs of the same two models are in their own table below. Every Gemma row below uses the same simulator build (`sim`
`eb8d08f157d7` in `out/evals.jsonl` and in the Modal run summaries), sampling at T 1.0 and a 32k
context. The mean score is ± one standard error.

| Model | Seeds | Samples per seed | Level 3 | Level 4 |
| --- | --- | --- | --- | --- |
| Gemma 4 26B-A4B, untrained (16k context) | held-out 101-106 | 8 | 0.088 ± 0.014 | 0.030 ± 0.007 |
| Gemma 4 26B-A4B, untrained | held-out 101-106 | 8 | 0.102 ± 0.019 | 0.037 ± 0.009 |
| Gemma 4 26B-A4B, untrained | fresh 200000+ | 4 | 0.103 ± 0.014 | 0.067 ± 0.008 |
| + SFT (LoRA) | held-out 101-106 | 8 | **0.749 ± 0.035** | **0.546 ± 0.040** |
| + SFT (LoRA) | fresh 200000+ | 4 | 0.726 ± 0.026 | 0.587 ± 0.030 |
| + SFT (LoRA) | its own training seeds 200+ | 4 | 0.772 ± 0.027 | 0.574 ± 0.034 |

The adapter `ckpt/gemma26-sft` (`adapter_model.safetensors`, sha256
`588e977f6446b7363f979ace352410d9d299910b196eb95296dd780126b046b6`) was trained on
`cache/demos-l34.jsonl`. That file, like every other demo file (`demos.jsonl`, `demos-l3.jsonl`,
`demos-l4.jsonl`), contains no seed from 101-106 and none from 200000 up.
The fresh seeds were never in any demo or evaluation before this run. The adapter scores the same
on its training seeds, the held-out seeds and the fresh ones, so the gain does not come from
remembering seeds. It also reads each incident rather than replaying the reference's routine
(`audit.py`):

- **A replayed routine scores nothing.** The reference's own calls from one seed, replayed unchanged
  on another, score 0.00 on all 20 level-4 pairs tried (raw −0.28: worse than doing nothing). Only 4 of
  71 replayed undos hit a fault. Nearby seeds are unrelated incidents (each seed is hashed per draw),
  and no held-out or fresh seed has the same set of faults as any demo seed.
- **It acts on what it observed.** In 96 fresh level-4 episodes, every one of its 317 rollbacks and
  config reverts came after it had read that service's diff. 97% of its undos hit a planted fault.
  5 of its 337 mitigations went to a service that is a fault in another evaluated seed but not in this one.
- **Edited observations change its action.** At 30 decision points in 10 level-4 transcripts, one tool
  result was edited and the adapter asked for its next reply at T 0:
  - Swap the name of the service it was about to mitigate with that of a healthy one, everywhere in
    the conversation: it mitigates the new service 10 times out of 10.
  - Remove the harmful hunk from the diff it was about to undo: 8 out of 10 times it skips the undo
    and reads the other change's diff.
  - Make the metrics calm before a scale-up: it still scales 7 times out of 10. The alerts and the
    retry-storm logs in the same conversation still show overload, so this edit is not decisive.

  Without edits, it repeats the transcript's action at all 30 points. The untrained model mitigates at
  none of them, edited or not: it keeps querying.
- **What it does not do.** It writes no reasoning text, only tool calls, and it follows the
  reference's procedure: logs, then changes, then the diff, then the undo, then a one-minute throttle
  to drain the retries. Its misses are faults that this procedure handles badly. An overload with a
  retry storm gets throttled for a minute instead of scaled (the worst fresh seed, 0.34). A batch job's
  saturation gets scaled. At level 4, 31 of 96 episodes run out of their 48 replies around minute 88
  (0.42, against 0.67 for the rest). It makes about one call per reply, as the demos do, and these
  episodes spend more replies on queries. A simple scripted policy, the simulator's `alerts_only`
  (the reference without tracing from the failing edge), still scores 0.74 at level 4 on the same seeds.
- **Where the adapter changed Gemma.** Layers 11-23 changed most, through every module, and
  `q_proj` changed most of all; layers 0-7 changed least (`out/lora-sft.png`). The updates use
  about 10-16 of the 32 ranks for 90% of their size.

### RL on the score, from the SFT adapter

Two runs start from the SFT adapter: 4 groups × 8 episodes per step on training seeds 1000+, lr 1e-5,
T 1.0, 32k context, rollouts overlapped with training (`--overlap`), same simulator build
(`eb8d08f157d7`). Held-out evals use 8 samples per seed on seeds 101-106 (48 episodes per level).

| Run | Step | Level 3 | Level 4 |
| --- | --- | --- | --- |
| `gemma26-rl-l4`: level 4 only, 24 steps, one B200 | 0 | | 0.475 ± 0.047 |
| | 6 | | 0.585 ± 0.042 |
| | 12 | | 0.627 ± 0.042 |
| | 18 | | 0.695 ± 0.040 |
| | 24 | | 0.640 ± 0.043 |
| | 24, second eval | | **0.752 ± 0.041** |
| `gemma26-rl`: levels 3+4, 60 steps, two RTX PRO 6000 | 0 | 0.739 ± 0.033 | 0.554 ± 0.050 |
| | 15 | 0.802 ± 0.034 | 0.568 ± 0.039 |
| | 30 | **0.880 ± 0.019** | **0.643 ± 0.037** |

- **Level 4 rises from about 0.5 to about 0.7 in 24 steps.** The two step-0 evals of the same
  adapter (0.475 and 0.554) and the two evals of the same step-24 weights (0.640 and 0.752) differ by
  about 0.1. That is the noise of one 48-episode eval, so read the trend across several evals, not
  any single step. The training reward of `gemma26-rl-l4` went from 0.57 (mean of steps 1-5) to
  0.71 (steps 20-24).
- **More of its episodes end at the reply cap as it trains.** Of the 48 held-out level-4 episodes,
  14 / 6 / 16 / 27 / 34 hit the 48-reply cap at steps 0 / 6 / 12 / 18 / 24 (28 on the second step-24
  eval). The policy spends more replies before the shift ends; whether on queries or on mitigations
  is not yet checked. Episodes cut by the cap are charged for the rest of the shift.
- **`gemma26-rl` is still running** (60 steps, finishing about 01:10 on 15 Nov); this table stops
  at its step-30 eval.
- **Speed:** on one B200 (vLLM at half the memory, the LoRA trainer beside it), a step took about
  200 s, about 3.3 minutes. On two RTX PRO 6000s (vLLM on one, the trainer on the other), about 263 s. On
  Modal's two H200s the same step took 11-12.5 minutes, measured from the untrained model, whose
  episodes all run to the reply cap.
- **The harness is ours, not Harbor's.** These scores come from `env.py`, not from the OpenCode
  agent the judges run, and are not comparable with the README's Opus numbers. The same models
  through Harbor + OpenCode are in the next section.

- **SFT:** `run.py sft --model google/gemma-4-26B-A4B-it --lora 32 --train-device cuda:1` on
  the reference's demos, 2 epochs, 100 optimiser steps. The loss fell from 0.30 at step 5 to 0.011 at
  step 100 (`out/sft-gemma26-sft.jsonl`). It ran on a Verda GPU instance (`verda.py`, `grab.py`) in
  about 90 minutes (its log runs from 18:23 to 19:53 on 14 Nov).
- **Evaluation and RL on Modal:** `modal_app.py` runs `run.py` in a Modal container with two H200s:
  vLLM on one, the LoRA trainer on the other. The adapter's three evaluations above and the fresh-seed
  baseline ran there. RL from the untrained model ran 2 steps at level 4 as a smoke test (training
  reward 0.068, then 0.088). The RL results above ran on Verda.
- **Where the code is:** `modal_app.py` (the Modal runner) and `audit.py` (the audit) are in this
  folder. The adapter (`ckpt/gemma26-sft`) and the per-episode transcripts are on the Modal Volume
  `aq-rl`, not in git.

## Gemma 4 26B-A4B in Harbor, the way the judged models run

Copying the reference took Gemma from 0.06 to about Opus's level in the judges' harness.

These runs use the judges' harness: OpenCode in Harbor 0.25.0 against a vLLM OpenAI-compatible
endpoint serving the base model and the SFT adapter (`serve.sh`, `judge.sh`), on `tasks/shift-1..3`
(level 4, seeds 101-103, the current `main` simulator), three attempts per shift. The agent sees
OpenCode's own prompt and the MCP tools under OpenCode's names, not the prompt and tool names the
adapter was trained on. Opus 5.5's row is its nine runs on the same three shifts in `metrics.json`
(round 10). Rescored against the current reference it is still 0.32.

| Model (Harbor + OpenCode) | Runs | Mean ± s.e. | Shift 1 | Shift 2 | Shift 3 |
| --- | --- | --- | --- | --- | --- |
| Gemma 4 26B-A4B, untrained | 9 | 0.06 ± 0.02 | 0.10 / 0.20 / 0.10 | 0.00 / 0.00 / 0.00 | 0.00 / 0.11 / 0.00 |
| + SFT adapter | 9 | **0.26 ± 0.11** | 0.88 / 0.14 / 0.00 | 0.00 / 0.26 / 0.00 | 0.00 / 0.65 / 0.41 |
| + SFT adapter, second set of 9 | 9 | 0.34 ± 0.12 | 0.23 / 0.63 / 0.60 | 0.00 / 0.71 / 0.85 | 0.00 / 0.00 / 0.00 |
| Opus 5.5 (`metrics.json`, round 10) | 9 | 0.32 | 0.11 / 0.73 / 0.18 | 0.04 / 0.03 / 0.80 | 0.17 / 0.20 / 0.59 |

The like-for-like comparison holds in the sense of the headline: with the adapter, Gemma scores
about what Opus scores, with error bars that overlap. It does not hold as "Gemma beats Opus": 0.26
and 0.34 (0.30 over all 18 runs) against 0.32.

Per trial (`judge.py`, which replays each signed action log): the untrained model wasted 1
mitigation in 9 runs and left 2-3 of the 3 faults unfixed in every run. It mostly queried and then
waited out the shift or called `finish`. The adapter wasted 1 mitigation in 18 runs and fixed every
fault in 8 of them. Of its rollbacks and restarts on services whose callers retry, it protected
about half first with a scale-up or throttle (9 of 17). None of its runs called `finish`; they
ended at the shift's end (11), with the agent ending its session between minutes 91 and 105 (6),
or at the 30-minute agent timeout (1).

Harness errors, all reported, none rerun:

- 4 of the adapter's runs ended in a `ContextOverflowError`: the conversation passed the 131,072-token
  context the server was started with. Gemma 4 takes 256k, and `serve.sh` now serves that, but these
  18 runs were at 128k. Harbor files the overflow as `ApiRateLimitError`, because its error
  classifier matches "rate limit" and "too many requests" anywhere in the output, and the
  simulator's own logs say "429 Too Many Requests: rate limiter bucket empty". The verifier still
  scored each run (0.00, 0.00, 0.23 and 0.60).
- 3 runs hit the task's 30-minute agent timeout (`AgentTimeoutError`): one untrained, two with the
  adapter. Their logged actions were scored as usual.
- The first judge-style run (one untrained run, not in the table) failed before any action: OpenCode's
  built-in `openai` provider calls the Responses API. A provider named `vllm` with the
  chat-completions format fixed it.

### Which fine-tuned checkpoint runs the scores spread (fixed before those runs)

The spread's seeds were first 404, 418, 500, 502, 503 and 504. Before any run on them finished they
were replaced by one common set for every model: level 4, seeds 200000-200023. 21 Harbor jobs started
on the first set were cancelled within a minute of starting, with no finished trial, and are not
results. The rule below did not change.

Rule (the orchestrator's, written here before any fine-tuned run on the spread seeds): for each candidate RL run, take the mean of its last two held-out level-4 evals
(seeds 101-106, 8 samples each); the higher mean wins, and a tie goes to `gemma26-rl-l4`, which
trained on level 4 only, the environment we submit. Both runs log an eval at their last step and an
end-of-run eval of the same weights, so for both "the last two" are those two rows of
`out/evals.jsonl`.

| Candidate | Trained on | Last step eval | End-of-run eval | Mean |
| --- | --- | --- | --- | --- |
| `gemma26-rl-l4` (B200) | level 4, 24 steps from the SFT adapter | 0.640 (step 24) | 0.752 | **0.696** |
| `gemma26-rl` (RTX PRO 6000) | levels 3+4, 60 steps from the SFT adapter | RTX_LAST | RTX_FINAL | RTX_MEAN |

Winner: WINNER.

## Setup

- **Environment**: `env.py` wraps the in-process `Estate`. System prompt = `task/instruction.md` +
  `briefing(level)`; tools = the MCP tools as JSON function schemas; reward = the environment's score
  of the replayed action log. The one change from the MCP task: a shift accepts at most 40 replies
  (48 for Gemma at levels 3-4) of up to 4 tool calls each, instead of 400 calls, and the
  conversation is cut at 16k tokens (32k for Gemma); either cut finishes the shift for the agent and
  charges the rest, as `finish` does. The reference polls every minute (about 480 calls a shift),
  which no context holds.
- **Seeds**: held-out 101-106 are held out from training: no demo, RL rollout or tuning of the
  reference used them. They are the seeds the frontier models were run on while the levels were
  built. SFT demos come from build seeds 1-12 and training seeds 200-399; RL draws training seeds
  from 1000 up.
- **Training**: one token sequence per episode built from the model's own chat template, so rollouts,
  SFT and RL see identical tokens. RL is group-relative policy gradient: 8 seeds × 8 rollouts per
  step, advantage = reward − group mean, one on-policy step per batch, token-averaged loss, no KL,
  no std normalisation. Qwen trains every weight (fp32 master weights) next to a vLLM engine on the
  same GPU and copies the weights into it after every step.

## Compute and cost

- **Verda:** the Qwen runs (evaluation, SFT and RL) and the Gemma SFT and baselines ran on
  temporary GPU instances, rented and deleted through the Verda API (`verda.py`, `grab.py`). The Qwen
  RL runs took about 70 GPU-minutes (from untrained) and 30 (level 3, from SFT). The Gemma SFT took
  90 minutes, and an untrained Gemma evaluation 9 minutes (16k context) or 35 (32k).
- **Modal:** two H200s per container ($9.08/h; no B200s were free on 14 Nov, and H200s started in
  4-12 s). An adapter evaluation of 96-192 episodes took 1.5-2.5 minutes, and the untrained model's
  192 episodes on fresh seeds took 27 minutes. A Gemma RL
  step (4 groups × 8 episodes at level 4) took 11-12.5 minutes: 53-66 s of rollouts and 667-758 s
  of LoRA training, about $1.80 per step.
