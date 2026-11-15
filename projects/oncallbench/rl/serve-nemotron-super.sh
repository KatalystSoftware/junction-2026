#!/bin/sh
# serve.sh for NVIDIA Nemotron 3.5 Super VL 120B-A12B (NVFP4, untrained) as "nemotron-super" on one
# B200, at 256k context like Gemma. NVIDIA ships Super VL only as BF16 (249 GB, too big for one GPU)
# and NVFP4 (75 GB); there is no FP8 checkpoint. Flags follow the model card's one-H200 vLLM recipe,
# without its video options: qwen3_coder tool calls, nemotron_v3 reasoning, the native MTP head for
# speculative decoding. Runs in the foreground; start it with nohup. Then, for the common seeds:
#   NAME=nemotron-super ./spread.sh base nemotron-super <tasks-custom dir> 2 $(seq 200000 200023)
#
#   VENV=<dir with vllm> ./serve-nemotron-super.sh
set -e
here=$(cd "$(dirname "$0")" && pwd)
. "${VENV:-$here/.venv}/bin/activate"
port=${PORT:-8100}
if curl -sf "localhost:$port/v1/models" >/dev/null; then echo "port $port is already serving" >&2; exit 1; fi
CUDA_VISIBLE_DEVICES=${GPU:-0} exec vllm serve nvidia/NVIDIA-Nemotron-3.5-Super-VL-120B-A12B-NVFP4 \
  --served-model-name nemotron-super --host 0.0.0.0 --port $port --max-model-len 262144 \
  --trust-remote-code --gpu-memory-utilization ${MEM:-0.9} --max-num-seqs 128 \
  --max-num-batched-tokens 16384 --enable-prefix-caching --block-size 64 --prefix-match-unit 64 \
  --mamba-backend flashinfer --mamba-ssm-cache-dtype float16 --enable-mamba-cache-stochastic-rounding \
  --mamba-cache-philox-rounds 5 --enable-mamba-shared-prefix-checkpoint --mamba-cache-mode align \
  --speculative-config.method mtp --speculative-config.num_speculative_tokens 3 \
  --enable-auto-tool-choice --tool-call-parser qwen3_coder --reasoning-parser nemotron_v3
