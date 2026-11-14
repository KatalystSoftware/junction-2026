#!/usr/bin/env bash
# Writes the ready-to-run Harbor tasks under tasks/: one folder per shift, each a full copy of task/
# with its seed, level, briefing and verifier calibration filled in, so plain `harbor run -p
# tasks/shift-1 ...` plays the same episode as `SEED=101 ./run.sh`. The folder names do not say the
# seed; the seed lives only in the MCP server and the verifier, which the agent cannot read.
# Usage: ./export-tasks.sh [level] [seed...]   (default: level 4, seeds 101 102 103)
set -euo pipefail
cd "$(dirname "$0")"
./sync.sh
python=(python3); command -v python3 >/dev/null || python=(nix shell nixpkgs#python313 -c python3)

level=${1:-4}
shift || true
[ $# -eq 0 ] && set -- 101 102 103

rm -rf tasks && mkdir tasks
n=0
for seed in "$@"; do
  n=$((n + 1))
  out=tasks/shift-$n
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
