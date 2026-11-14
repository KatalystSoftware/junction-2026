# aq-incident/rl: can a small open model learn on-call from this environment?

Post-trains open models on the aq-incident simulator and measures their score on the held-out seeds
101-106 before and after: Qwen3.5-2B (every weight; levels 0-3) and Gemma 4 26B-A4B (a LoRA adapter;
levels 3-4). Training ran on a Verda GPU instance, and the Gemma adapter's evaluations and RL on Modal.
Results: [`RESULTS.md`](RESULTS.md).

## Run

On a machine with one 80 GB+ GPU, from this folder:

```
./setup.sh && . .venv/bin/activate && python3 demos.py --seeds 1-12,200-349 --out cache/demos.jsonl \
  && python3 run.py eval --tag base && python3 run.py sft --tag sft && python3 run.py rl --model ckpt/sft --tag rl --lr 1e-6
```

`eval` plays 8 episodes per held-out seed and level (0-2); `sft` trains on reference demos;
`rl` runs group-relative policy gradient on the environment's score over training seeds 1000+,
evaluating the held-out seeds every 10 steps. Everything lands in `out/` (curves, summaries) and
`ckpt/` (weights, not in git).

## Test

```
python3 demos.py --levels 0,1,2 --seeds 1-12
```

Renders the reference's decisions as demos and replays them through the wrapper: level 0 must
score 1.00 and levels 1-2 about 0.97 (the demos check in every 10 minutes, the reference every
minute).

## How it works

- `env.py`: the environment. System prompt = `task/instruction.md` with `briefing(level)`; tools =
  the MCP tools as JSON function schemas; an episode ends at `finish`, at the shift's end, or after
  40 replies (then the shift is finished for the agent and the rest is charged). Reward = the
  environment's score of the replayed action log. The simulator is imported read-only from
  `../sim`; `AQ_SIM` points at a pinned snapshot instead.
- `demos.py`: the scripted reference's decisions as compact tool-call conversations: idle one-minute
  waits become waits to the next 10-minute check-in, and free calls that change nothing are dropped.
- `core.py`: one token sequence per episode, built from the model's own chat template, so rollouts,
  SFT and RL see identical tokens; batched rollouts on vLLM; the policy-gradient step; in-place
  weight sync from the trainer into vLLM.
- `run.py`: `eval`, `sft`, `rl`.
- `verda.py`, `grab.py`: create, list and delete the temporary GPU instance through the Verda API
  (only hostnames starting `aq-rl-`); credentials only via `sops exec-env`.
