#!/bin/sh
# Like-for-like with the judged runs: OpenCode in Harbor against the endpoint serve.sh runs, on every
# task, ATTEMPTS attempts each (default 3) in one job per task and served model, all at once.
#
#   ./judge.sh <job prefix> <served model>... -- <task dir>...
#
# Tasks are tasks/shift-N or run.sh variants. Jobs are named <prefix>-<served model>-<task folder>.
# The server must allow Gemma 4's full 256k context (serve.sh does): at 128k long shifts overflowed,
# and Harbor reports an overflow as ApiRateLimitError. Tabulate with: python3 judge.py <jobs dir>/<prefix>-*
set -e
prefix=$1
shift
models=""
while [ "$1" != "--" ]; do models="$models $1"; shift; done
shift
here=$(cd "$(dirname "$0")" && pwd)
port=${PORT:-8100}
export PATH="$HOME/.local/bin:$PATH" UV_PYTHON_PREFERENCE=only-system
pids=""
for task in "$@"; do
  for m in $models; do
    curl -sf "localhost:$port/v1/models" | grep -q "\"$m\"" || { echo "$m is not served on $port" >&2; exit 1; }
    (cd "$(dirname "$task")/.." && uvx --from harbor==0.25.0 harbor run -p "$task" -o jobs \
      --job-name "$prefix-$m-$(basename "$task")" -a opencode -m "vllm/$m" -k "${ATTEMPTS:-3}" -n "${ATTEMPTS:-3}" \
      --base-url "http://172.17.0.1:$port/v1" --api-format openai_chat_completions --api-key-name VLLM_API_KEY \
      --ae VLLM_API_KEY=local --agent-setup-timeout-multiplier 3 > "$here/judge-$prefix-$m-$(basename "$task").log" 2>&1) &
    pids="$pids $!"
    sleep 5
  done
done
wait $pids
