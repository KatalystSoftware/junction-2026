#!/bin/sh
# spread.sh for a hosted OpenAI-compatible endpoint instead of our own vLLM: one Harbor + OpenCode job
# per run on the common seeds, at most MAXPAR (default 3) at once, so collect.py picks each up.
#
#   KEY_ENV=<env var holding the key> ./hosted.sh <run name> <base url> <served model> <tasks-custom dir> <seed>...
#
# The key is read from the named env var by Harbor (--api-key-name), never passed on a command line.
# The provider is named "vllm" with the chat-completions format, as for Gemma: OpenCode's built-in
# "openai" provider calls the Responses API. Jobs are named <ROUND>-l4-s<seed>-<run name>-HHMMSS
# (ROUND defaults to r16) and land in <tasks-custom dir>/../jobs.
set -e
run=$1 url=$2 served=$3 tasks=$4
shift 4
: "${KEY_ENV:?set KEY_ENV to the name of the env var holding the endpoint key}"
here=$(cd "$(dirname "$0")" && pwd)
export PATH="$HOME/.local/bin:$PATH" UV_PYTHON_PREFERENCE=only-system
cd "$tasks/.."
pids=""
for seed in "$@"; do
  while [ "$(for p in $pids; do kill -0 "$p" 2>/dev/null && echo; done | wc -l)" -ge "${MAXPAR:-3}" ]; do sleep 10; done
  # each trial's containers take about 1 GB while OpenCode installs; a full disk fails them (ENOSPC)
  # and takes down whatever else the machine serves, so wait for MINFREE_GB (default 6) free first
  while [ "$(df -BG --output=avail "$tasks" | tail -1 | tr -dc 0-9)" -lt "${MINFREE_GB:-6}" ]; do sleep 30; done
  job="${ROUND:-r16}-l4-s$seed-$run-$(date +%H%M%S)"
  echo "$(date -u +%H:%M:%S) $job"
  uvx --from harbor==0.25.0 harbor run -p "$tasks/seed-$seed" -o jobs --job-name "$job" -a opencode \
    -m "vllm/$served" --base-url "$url" --api-format openai_chat_completions \
    --api-key-name "$KEY_ENV" --agent-setup-timeout-multiplier 3 > "$here/hosted-$job.log" 2>&1 &
  pids="$pids $!"
  sleep 2  # distinct HHMMSS per job
done
wait $pids
