#!/bin/sh
# Judge-style run: serve a model from vLLM's OpenAI-compatible endpoint and point OpenCode in Harbor
# at it, on a task variant made by run.sh (e.g. LEVEL=4 SEED=101 ./run.sh nop).
#
#   GPU=0 ./harbor.sh <model path or HF id> <served name> <task variant dir> <job name> [lora adapter dir]
#
# The agent's container reaches the server over the Docker bridge (172.17.0.1). The provider is
# named "vllm": OpenCode's built-in "openai" provider calls the Responses API, which vLLM's
# chat-completions tool calling does not go through. PARSER/REASONING/MEM/PORT override the defaults
# (Gemma 4's parsers, 0.9 of the GPU, port 8100).
set -e
model=$1 name=$2 task=$3 job=$4 adapter=${5:-}
here=$(cd "$(dirname "$0")" && pwd)
. "$here/.venv/bin/activate"
lora=""
[ -n "$adapter" ] && lora="--enable-lora --max-lora-rank 64 --lora-modules $name=$adapter"
port=${PORT:-8100}
reasoning=""
[ "${REASONING-gemma4}" ] && reasoning="--reasoning-parser ${REASONING-gemma4}"
CUDA_VISIBLE_DEVICES=${GPU:-0} vllm serve "$model" --served-model-name "$name" --host 0.0.0.0 --port $port \
  --max-model-len 65536 --gpu-memory-utilization ${MEM:-0.9} --enable-auto-tool-choice \
  --tool-call-parser ${PARSER:-gemma4} $reasoning --limit-mm-per-prompt '{"image":0,"audio":0,"video":0}' $lora \
  > "$here/serve-$job.log" 2>&1 &
server=$!
trap 'kill $server 2>/dev/null' EXIT
until curl -sf localhost:$port/v1/models >/dev/null; do
  kill -0 $server 2>/dev/null || { echo "vllm exited"; tail -20 "$here/serve-$job.log"; exit 1; }
  sleep 10
done
cd "$(dirname "$task")/../.."
export PATH="$HOME/.local/bin:$PATH" UV_PYTHON_PREFERENCE=only-system
uvx --from harbor==0.25.0 harbor run -p "$task" -o jobs --job-name "$job" -a opencode -m "vllm/$name" \
  --base-url http://172.17.0.1:$port/v1 --api-format openai_chat_completions --api-key-name VLLM_API_KEY \
  --ae VLLM_API_KEY=local
