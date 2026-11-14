# Results: can a small open model learn on-call from aq-incident?

Yes. Qwen3.5-2B, trained by reinforcement learning on nothing but the environment's own score,
goes from 0.59 / 0.16 / 0.08 to 0.97 / 0.34 / 0.23 on the held-out seeds at levels 0 / 1 / 2 in 20
steps (about 70 GPU-minutes). With the reference's trajectories as SFT data first it reaches 1.00 /
0.96 / 0.93, and RL on the score then lifts that model on level 3, where it saw no demos, from 0.16
to 0.29. All numbers are the environment's score, `clip((cost_null - cost) / (cost_null - cost_ref), 0, 1)`,
on held-out seeds 101-106: do-nothing is 0.00, the scripted reference 1.00.

## Qwen3.5-2B (levels 0-2, simulator pinned at `aec3d09`)

Mean score over 8 sampled episodes per held-out seed (48 per level; T 0.7, top-p 0.8, top-k 20,
Qwen's non-thinking settings), ± one standard error.

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

GEMMA_SECTION

## Setup

- **Environment**: `env.py` wraps the in-process `Estate`. System prompt = `task/instruction.md` +
  `briefing(level)`; tools = the MCP tools as JSON function schemas; reward = the environment's score
  of the replayed action log. The one change from the MCP task: a shift accepts at most 40 replies
  (48 for Gemma at levels 3-4) of up to 4 tool calls each, instead of 400 calls, and the
  conversation is cut at 16k tokens (32k for Gemma); either cut finishes the shift for the agent and
  charges the rest, as `finish` does. The reference polls every minute (about 480 calls a shift),
  which no context holds.
- **Seeds**: held-out 101-106 are only evaluated. SFT demos come from build seeds 1-12 and training
  seeds 200-399; RL draws training seeds from 1000 up.
- **Training**: one token sequence per episode built from the model's own chat template, so rollouts,
  SFT and RL see identical tokens. RL is group-relative policy gradient: 8 seeds × 8 rollouts per
  step, advantage = reward − group mean, one on-policy step per batch, token-averaged loss, no KL,
  no std normalisation. Qwen trains every weight (fp32 master weights) next to a vLLM engine on the
  same GPU and copies the weights into it after every step.

## Compute and cost

COMPUTE_SECTION
