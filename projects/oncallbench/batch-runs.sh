#!/usr/bin/env bash
# Runs a list of Harbor trials in parallel on a CRACI runner (.github/workflows/batch.yml), never on
# a shared workstation. Each line of the list file is: <round> <tag> <provider/model> <seed>.
# Tasks are exported for the listed seeds; finished job folders land in $BATCH_OUT/jobs for the
# workflow's artifact (collect them with collect.py and archive_runs.py on the checkout).
#
#   gh workflow run batch.yml -f size=32 -f timeout=240 \
#     -f command='projects/oncallbench/batch-runs.sh projects/oncallbench/batch/<list>.txt 8'
set -euo pipefail
list=$(realpath "$1")
parallel=${2:-6}
cd "$(dirname "$0")"
command -v uv >/dev/null || { curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null; }
export PATH="$HOME/.local/bin:$PATH"
unset ANTHROPIC_BASE_URL ANTHROPIC_AUTH_TOKEN
uv tool install -q harbor==0.25.0

./export-tasks.sh 4 $(awk '{print $4}' "$list" | sort -un) >/dev/null

one() {
  local round=$1 tag=$2 model=$3 seed=$4 extra=()
  sleep $((RANDOM % 20))
  local job="r$round-l4-s$seed-$tag-$(date +%H%M%S)"
  [ "$tag" = gemini ] && extra=(--ae "GOOGLE_GENERATIVE_AI_API_KEY=${GEMINI_API_KEY:-}")
  harbor run -p "tasks-custom/seed-$seed" -a opencode -m "$model" --agent-setup-timeout-multiplier 3 \
    -o jobs --job-name "$job" "${extra[@]}" >"jobs-$job.log" 2>&1 || true
  local f
  f=$(ls jobs/"$job"/*/result.json 2>/dev/null | head -1)
  echo "$job $(jq -c '{r: .verifier_result.rewards.reward, ex: (.exception_info.exception_type // null)}' "$f" 2>/dev/null)"
}
export -f one
mkdir -p jobs
xargs -P "$parallel" -L 1 bash -c 'one "$@"' _ <"$list"

out=${BATCH_OUT:-out}
mkdir -p "$out"
cp -r jobs "$out/"
cp jobs-*.log "$out/" 2>/dev/null || true
