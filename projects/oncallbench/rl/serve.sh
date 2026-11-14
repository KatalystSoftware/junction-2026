#!/bin/sh
# One vLLM OpenAI-compatible server for the judge-style runs (judge.sh, spread.sh): Gemma 4 26B-A4B as
# "gemma26-base" plus any LoRA adapters given as name=dir, at Gemma 4's full 256k context. More adapters
# can be loaded while it runs:
#   curl -X POST localhost:8100/v1/load_lora_adapter -H 'Content-Type: application/json' \
#     -d '{"lora_name": "gemma26-ft", "lora_path": "/abs/dir"}'
# Runs in the foreground; start it with nohup. Refuses to start if the port is taken.
#
#   ./serve.sh [name=adapter dir]...
set -e
here=$(cd "$(dirname "$0")" && pwd)
. "$here/.venv/bin/activate"
port=${PORT:-8100}
if curl -sf "localhost:$port/v1/models" >/dev/null; then echo "port $port is already serving" >&2; exit 1; fi
lora=""
[ $# -gt 0 ] && lora="--enable-lora --max-lora-rank 64 --max-loras 2 --lora-modules $*"
VLLM_ALLOW_RUNTIME_LORA_UPDATING=True CUDA_VISIBLE_DEVICES=${GPU:-0} exec vllm serve google/gemma-4-26B-A4B-it \
  --served-model-name gemma26-base --host 0.0.0.0 --port $port --max-model-len 262144 \
  --gpu-memory-utilization ${MEM:-0.9} --enable-auto-tool-choice --tool-call-parser gemma4 --reasoning-parser gemma4 \
  --limit-mm-per-prompt '{"image":0,"audio":0,"video":0}' $lora
