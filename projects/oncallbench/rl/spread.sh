#!/bin/sh
# The scores spread: one Harbor job per run on pre-registered seeds, so collect.py picks each up, with
# OpenCode against the endpoint serve.sh runs (served model gemma26-base, or a loaded adapter's name).
#
#   ./spread.sh <base|ft> <served model> <tasks-custom dir> <runs per seed> <seed>...
#
# Jobs are named r15-l4-s<seed>-gemma-<base|ft>-HHMMSS and land in <tasks-custom dir>/../jobs.
set -e
kind=$1 served=$2 tasks=$3 runs=$4
shift 4
here=$(cd "$(dirname "$0")" && pwd)
port=${PORT:-8100}
curl -sf "localhost:$port/v1/models" | grep -q "\"$served\"" || { echo "$served is not served on $port" >&2; exit 1; }
export PATH="$HOME/.local/bin:$PATH" UV_PYTHON_PREFERENCE=only-system
cd "$tasks/.."
pids=""
for seed in "$@"; do
  for _ in $(seq "$runs"); do
    job="r15-l4-s$seed-gemma-$kind-$(date +%H%M%S)"
    echo "$job"
    uvx --from harbor==0.25.0 harbor run -p "$tasks/seed-$seed" -o jobs --job-name "$job" -a opencode \
      -m "vllm/$served" --base-url "http://172.17.0.1:$port/v1" --api-format openai_chat_completions \
      --api-key-name VLLM_API_KEY --ae VLLM_API_KEY=local --agent-setup-timeout-multiplier 3 \
      > "$here/spread-$job.log" 2>&1 &
    pids="$pids $!"
    sleep 2  # distinct HHMMSS per job
  done
done
wait $pids
