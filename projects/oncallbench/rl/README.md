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

### On Modal

`modal_app.py` runs `run.py` on Modal, one container per run: two GPUs (vLLM on `cuda:0`, the LoRA
trainer on `cuda:1`), B200s when free and H200s otherwise. The simulator is pinned at `AQ_SIM_REF`
(default `3bac4f4`, as on Verda) and `AQ_MAX_TURNS=48`. Weights, demos, checkpoints and curves live on
the `aq-rl` Volume: `ckpt/<tag>/` and `out/<tag>/`. The first lines of `out/<tag>/run.log` are the
container's `nvidia-smi -L`. From the repo root:

```
direnv exec . sops exec-env secrets/secrets.yaml 'cd projects/oncallbench/rl && sh -c "
  G=\"rl --model google/gemma-4-26B-A4B-it --adapter ckpt/gemma26-sft --lora 32 --train-device cuda:1 --groups 4 --per 8 --steps 60 --overlap --max-ctx 32768 --gpu-mem 0.85 --eval-every 15 --eval-samples 8 --eval-temp 1.0 --save-every 5 --final-samples 8\"
  ~/.local/bin/modal run --detach modal_app.py --runs \"\$G --levels 3,4 --lr 1e-5 --tag gemma26-rl-m; \$G --levels 4 --lr 1e-5 --tag gemma26-rl-l4\"
"'
```

Each `;`-separated run gets its own container; `--gpus 1` puts each on one GPU (Qwen). Before the
first run: `modal run modal_app.py::fetch --model <hf id>` downloads the weights into the Volume
without a GPU, and `modal volume put aq-rl <local dir> /ckpt/<tag>` (or `/cache/`) uploads adapters
and demos. To follow a run: `modal app logs <app id>`, or `modal volume get aq-rl /out/<tag> out/`.

Measured on 2× H200 (Gemma 4 26B-A4B, level 4, 4 groups × 8, 32k context, `--overlap`): rollouts take
53–66 s per step and the LoRA trainer 667–758 s, so a step takes 11–12.5 min at $9.08/h (about $1.80
per step). B200s were never free on 14 Nov; H200s started in 4–12 s.

## Test

```
python3 demos.py --levels 0,1,2 --seeds 1-12
```

Renders the reference's decisions as demos and replays them through the wrapper: level 0 must
score 1.00 and levels 1-2 about 0.97 (the demos check in every 10 minutes, the reference every
minute).

## Download and check the trained adapter

The Gemma 4 SFT adapter and its training demos are public, no account needed:
https://storage.googleapis.com/katalyst-fyi-models/oncallbench/gemma4-26b-a4b-sft/ (`README.md`,
`adapter_config.json`, `adapter_model.safetensors`, `SHA256SUMS`) and
https://storage.googleapis.com/katalyst-fyi-models/oncallbench/demos/demos-l34.jsonl. Download them into
one folder, then:

```
sha256sum --check --strict SHA256SUMS                                           # every file: OK
jq .seed demos-l34.jsonl | awk '$1>=101&&$1<=106 || $1>=200000' | wc -l           # 0 held-out demos
```

[`oncallbench-model.yml`](../../../.github/workflows/oncallbench-model.yml) does this on a clean CRACI
runner (32 vCPU, no GPU). It also fetches `google/gemma-4-26B-A4B-it` anonymously (the model is not
gated) and checks each weight file against Hugging Face's sha256. It converts base and adapter to GGUF
with llama.cpp `b12017`, serves them on CPU, and asserts through `/lora-adapters` that the adapter is
applied. Then it plays one held-out episode through Harbor 0.25.0 + OpenCode, as the judged agents
do. The job summary lists every hash, the held-out count, the base revision, the score and the time
per step. The runs are in the team's private CI; the latest passing one (run 43651780827) showed:
level 0, seed 101, score 0.89. It scaled the overloaded profile-db, the right fix, but also made two
unneeded config reverts, in 44 tool calls over 12 minutes. The run before it
(run 43650015008) played the
same episode, rolled profile-db back instead of scaling it, and scored 0.00, the same as doing nothing.
The job is a smoke test that the published files load and drive the environment. One level-0
episode does not measure the adapter: it was trained on levels 3 and 4, which take too long on CPU.

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
- `modal_app.py`: the same commands on Modal GPUs (above).
- `verda.py`, `grab.py`: create, list and delete the temporary GPU instance through the Verda API
  (only hostnames starting `aq-rl-`); credentials only via `sops exec-env`.
