#!/usr/bin/env bash
# Execute the exact captured run.sh; all its task copies and job output stay in audit/runtime.
set -euo pipefail
cd "$(dirname "$0")/runtime"
export LEVEL=4
export HARBOR_ARGS="--quiet"
for repeat in 1 2 3; do
  for seed in 101 104 105; do
    export SEED="$seed" JOB_PREFIX="audit-r$repeat"
    printf 'repeat=%s seed=%s started=%s\n' "$repeat" "$seed" "$(date -u +%FT%TZ)"
    ./run.sh reference nop stop-early
  done
done
