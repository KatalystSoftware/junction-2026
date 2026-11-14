#!/bin/sh
# The scores spread: one Harbor job per run on pre-registered seeds, so collect.py picks each up, with
# OpenCode against the endpoint serve.sh runs (served model gemma26-base, or a loaded adapter's name).
#
#   ./spread.sh <base|ft> <served model> <tasks-custom dir> <runs per seed> <seed>...
#
# Jobs are named <ROUND>-l4-s<seed>-gemma-<base|ft>-HHMMSS (ROUND defaults to r16, the common seeds)
# and land in <tasks-custom dir>/../jobs.
set -e
kind=$1 served=$2 tasks=$3 runs=$4
shift 4
here=$(cd "$(dirname "$0")" && pwd)
port=${PORT:-8100}
# the agent containers reach the host over the Docker bridge, wherever the daemon put it
bridge=$(ip -4 -o addr show docker0 | awk '{print $4}' | cut -d/ -f1)
curl -sf "localhost:$port/v1/models" | grep -q "\"$served\"" || { echo "$served is not served on $port" >&2; exit 1; }
export PATH="$HOME/.local/bin:$PATH" UV_PYTHON_PREFERENCE=only-system
cd "$tasks/.."
pids=""
for seed in "$@"; do
  for _ in $(seq "$runs"); do
    job="${ROUND:-r16}-l4-s$seed-gemma-$kind-$(date +%H%M%S)"
    echo "$job"
    uvx --from harbor==0.25.0 harbor run -p "$tasks/seed-$seed" -o jobs --job-name "$job" -a opencode \
      -m "vllm/$served" --base-url "http://$bridge:$port/v1" --api-format openai_chat_completions \
      --api-key-name VLLM_API_KEY --ae VLLM_API_KEY=local --agent-setup-timeout-multiplier 3 \
      > "$here/spread-$job.log" 2>&1 &
    pids="$pids $!"
    sleep 2  # distinct HHMMSS per job
  done
done
wait $pids
