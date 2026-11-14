#!/usr/bin/env bash
# Writes ready-to-run Harbor tasks: full copies of task/ with seed, level, briefing and verifier
# calibration filled in, so plain `harbor run -p <folder> ...` plays the same episode as
# `SEED=<seed> ./run.sh`. The seed lives only in the MCP server and the verifier, which the agent
# cannot read. Folder names must not say it either: Harbor names the containers after the folder,
# and Docker's DNS gives those names to anyone in the task's network.
#
#   ./export-tasks.sh                 the shipped tasks: tasks/shift-1..3 = level 4, seeds 101-103
#   ./export-tasks.sh <level> <seed>...   any other episode, as tasks-custom/episode-<random>; never
#                                     touches tasks/. tasks-custom/index.tsv says which folder holds
#                                     which level and seed, and exporting a seed again reuses its folder.
set -euo pipefail
cd "$(dirname "$0")"
./sync.sh
if python3 -c '' 2>/dev/null; then python=(python3)  # macOS has a python3 stub that only offers to install
elif command -v nix >/dev/null; then python=(nix shell nixpkgs#python313 -c python3)
else python=(uv run --no-project --python 3.13 python3); fi

if [ $# -le 1 ]; then
  [ $# -eq 1 ] && [ "$1" != 4 ] && { echo "custom episodes need seeds: $0 <level> <seed>..." >&2; exit 2; }
  level=4 shipped=1
  set -- 101 102 103
  rm -rf tasks && mkdir tasks
else
  level=$1 shipped=0
  shift
  mkdir -p tasks-custom
  touch tasks-custom/index.tsv
fi

n=0
for seed in "$@"; do
  n=$((n + 1))
  if [ "$shipped" = 1 ]; then
    out=tasks/shift-$n
  else
    name=$(awk -F'\t' -v l="$level" -v s="$seed" '$2 == l && $3 == s { print $1 }' tasks-custom/index.tsv | tail -1)
    if [ -z "$name" ]; then
      name=episode-$(od -An -N4 -tx1 /dev/urandom | tr -d ' \n')
      printf '%s\t%s\t%s\n' "$name" "$level" "$seed" >>tasks-custom/index.tsv
    fi
    out=tasks-custom/$name
    rm -rf "$out"
  fi
  cp -r task "$out"
  sed -i.bak "s/^SEED = .*/SEED = $seed/; s/^LEVEL = .*/LEVEL = $level/" "$out/environment/mcp-server/server.py"
  rm "$out/environment/mcp-server/server.py.bak"  # -i.bak: the form both GNU and BSD (macOS) sed accept
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
