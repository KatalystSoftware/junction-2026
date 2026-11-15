#!/bin/sh
# serve.sh for NVIDIA Nemotron 3.5 Lightning 30B-A3B (BF16, untrained) as "nemotron-lightning", at
# 256k context like Gemma, with the parsers its model card gives for vLLM: qwen3_coder for tool calls,
# nemotron_v3 for reasoning. Runs in the foreground; start it with nohup. Then, for the common seeds:
#   NAME=nemotron-lightning ./spread.sh base nemotron-lightning <tasks-custom dir> 1 $(seq 200000 200023)
#
#   VENV=<dir with vllm> ./serve-nemotron.sh
set -e
here=$(cd "$(dirname "$0")" && pwd)
. "${VENV:-$here/.venv}/bin/activate"
port=${PORT:-8100}
if curl -sf "localhost:$port/v1/models" >/dev/null; then echo "port $port is already serving" >&2; exit 1; fi
CUDA_VISIBLE_DEVICES=${GPU:-0} exec vllm serve nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16 \
  --served-model-name nemotron-lightning --host 0.0.0.0 --port $port --max-model-len 262144 \
  --gpu-memory-utilization ${MEM:-0.9} --enable-prefix-caching --mamba-backend flashinfer \
  --enable-auto-tool-choice --tool-call-parser qwen3_coder --reasoning-parser nemotron_v3
