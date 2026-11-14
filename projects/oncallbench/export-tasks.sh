#!/usr/bin/env bash
# Writes ready-to-run Harbor tasks: full copies of task/ with seed, level, briefing and verifier
# calibration filled in, so plain `harbor run -p <folder> ...` plays the same episode as
# `SEED=<seed> ./run.sh`. The seed lives only in the MCP server and the verifier, which the agent
# cannot read.
#
#   ./export-tasks.sh                 the shipped tasks: tasks/shift-1..3 = level 4, seeds 101-103
#                                     (folder names do not say the seed)
#   ./export-tasks.sh <level> <seed>...   any other episode, as tasks-custom/seed-<seed>; never
#                                     touches tasks/
set -euo pipefail
cd "$(dirname "$0")"
./sync.sh
if command -v python3 >/dev/null; then python=(python3)
elif command -v uv >/dev/null; then python=(uv run --no-project --python 3.13 python3)
else python=(nix shell nixpkgs#python313 -c python3); fi

if [ $# -le 1 ]; then
  [ $# -eq 1 ] && [ "$1" != 4 ] && { echo "custom episodes need seeds: $0 <level> <seed>..." >&2; exit 2; }
  level=4 shipped=1
  set -- 101 102 103
  rm -rf tasks && mkdir tasks
else
  level=$1 shipped=0
  shift
  mkdir -p tasks-custom
fi

n=0
for seed in "$@"; do
  n=$((n + 1))
  if [ "$shipped" = 1 ]; then out=tasks/shift-$n; else out=tasks-custom/seed-$seed; rm -rf "$out"; fi
  cp -r task "$out"
  sed -i "s/^SEED = .*/SEED = $seed/; s/^LEVEL = .*/LEVEL = $level/" "$out/environment/mcp-server/server.py"
  "${python[@]}" -B -c "
import sys; sys.path.insert(0, 'sim'); import incident; from pathlib import Path
p = Path('$out/instruction.md')
p.write_text(p.read_text().replace('<!-- BRIEFING -->\n', incident.briefing($level)))
"
  "${python[@]}" -B -c "
import eval, json, sys
r = eval.evaluate($seed, $level)
json.dump({k: r[k] for k in ('seed', 'level', 'cost_null', 'cost_ref')}, sys.stdout)
" >"$out/tests/calibration.json"
  echo "$out: level $level, seed $seed"
done
