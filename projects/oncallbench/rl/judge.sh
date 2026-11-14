#!/bin/sh
# Like-for-like with the judged runs: one vLLM OpenAI-compatible server for the base model (served as
# "<name>-base") and, with an adapter, the LoRA on top of it (served as "<name>-sft"); OpenCode in Harbor
# on every variant, ATTEMPTS attempts each (default 3), for each served model, all at once.
#
#   ./judge.sh <model> <adapter dir or -> <name> <job prefix> <variant dir>...
#
# Variants come from run.sh (LEVEL=4 SEED=101 ./run.sh nop). MODELS=base or MODELS=sft runs one side only.
# Tabulate with: python3 judge.py <jobs dir>/<job prefix>-*
set -e
model=$1 adapter=$2 name=$3 prefix=$4
shift 4
here=$(cd "$(dirname "$0")" && pwd)
. "$here/.venv/bin/activate"
lora="" models="base"
if [ "$adapter" != "-" ]; then
  lora="--enable-lora --max-lora-rank 64 --max-loras 1 --lora-modules $name-sft=$adapter"
  models="base sft"
fi
models=${MODELS:-$models}
port=${PORT:-8100}
CUDA_VISIBLE_DEVICES=${GPU:-0} vllm serve "$model" --served-model-name "$name-base" --host 0.0.0.0 --port $port \
  --max-model-len 131072 --gpu-memory-utilization ${MEM:-0.9} --enable-auto-tool-choice --tool-call-parser gemma4 \
  --reasoning-parser gemma4 --limit-mm-per-prompt '{"image":0,"audio":0,"video":0}' $lora \
  > "$here/serve-$prefix.log" 2>&1 &
server=$!
trap 'kill $server 2>/dev/null' EXIT
until curl -sf localhost:$port/v1/models >/dev/null; do
  kill -0 $server 2>/dev/null || { echo "vllm exited"; tail -30 "$here/serve-$prefix.log"; exit 1; }
  sleep 10
done
curl -s localhost:$port/v1/models | python3 -c "import json,sys; print([m['id'] for m in json.load(sys.stdin)['data']])"
export PATH="$HOME/.local/bin:$PATH" UV_PYTHON_PREFERENCE=only-system
for task in "$@"; do
  for m in $models; do
    (cd "$(dirname "$task")/../.." && uvx --from harbor==0.25.0 harbor run -p "$task" -o jobs \
      --job-name "$prefix-$m-$(basename "$task")" -a opencode -m "vllm/$name-$m" -k "${ATTEMPTS:-3}" -n "${ATTEMPTS:-3}" \
      --base-url "http://172.17.0.1:$port/v1" --api-format openai_chat_completions --api-key-name VLLM_API_KEY \
      --ae VLLM_API_KEY=local > "$here/judge-$prefix-$m-$(basename "$task").log" 2>&1) &
    sleep 5
  done
done
wait
