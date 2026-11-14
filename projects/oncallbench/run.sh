#!/usr/bin/env bash
# Usage: ./run.sh [reference|nop|stop-early|one-fix|exploiter|opus|sonnet|gemini]...
#   reference  = scripted on-call policy (solution/solve.sh), expect 1.0
#   nop        = do-nothing baseline, expect 0.0
#   stop-early, one-fix, exploiter, no-late, loudest-first, thorough = the other scripted
#     policies in solution/policies.py
#   opus, sonnet, gemini = OpenCode with claude-opus-5-5, claude-sonnet-5-5, gemini-3.1-pro-preview
# SEED=n and LEVEL=n pick the episode (default seed 1, the submitted level), ATTEMPTS=n the agent
# attempts (default 1), JOB_PREFIX names the job folders, HARBOR_ARGS adds flags to every run.
# The runs of one call go side by side.
# Credentials come from the environment only (ANTHROPIC_API_KEY, GEMINI_API_KEY).
set -euo pipefail
cd "$(dirname "$0")"
./sync.sh

# NixOS keeps uv on system Python, as before; everywhere else uv may fetch one.
[ ! -e /etc/NIXOS ] || export UV_PYTHON_PREFERENCE=only-system
harbor() {
  if command -v uvx >/dev/null; then
    uvx --from harbor==0.25.0 harbor "$@"
  else
    nix shell nixpkgs#uv nixpkgs#python313 -c uvx --from harbor==0.25.0 harbor "$@"
  fi
}
if command -v python3 >/dev/null; then python=(python3)
elif command -v nix >/dev/null; then python=(nix shell nixpkgs#python313 -c python3)
else python=(uv run --no-project --python 3.13 python3); fi
read -ra extra <<<"${HARBOR_ARGS:-}"

# Each episode is a copy of the task with its own hidden seed, calibration and level rules. The folder name is
# random, so neither the seed nor the level shows in anything the agent can read: Harbor names the
# containers after the folder, and Docker's DNS gives those names to anyone in the task's network.
# jobs/variants/index.tsv says which copy holds which level and seed.
SEED=${SEED:-1}
LEVEL=${LEVEL:-$("${python[@]}" -B -c "import sys; sys.path.insert(0, 'sim'); import incident; print(incident.SUBMITTED)")}
mkdir -p jobs/variants
task=jobs/variants/episode-$(od -An -N4 -tx1 /dev/urandom | tr -d ' \n')
cp -r task "$task"
printf '%s\t%s\t%s\n' "${task#jobs/variants/}" "$LEVEL" "$SEED" >>jobs/variants/index.tsv
echo "$task: level $LEVEL, seed $SEED"
sed -i "s/^SEED = .*/SEED = $SEED/; s/^LEVEL = .*/LEVEL = $LEVEL/" "$task/environment/mcp-server/server.py"
"${python[@]}" -B -c "
import sys; sys.path.insert(0, 'sim'); import incident; from pathlib import Path
p = Path('$task/instruction.md')
p.write_text(p.read_text().replace('<!-- BRIEFING -->\n', incident.briefing($LEVEL)))
"
"${python[@]}" -B -c "
import eval, json, sys
r = eval.evaluate($SEED, $LEVEL)
json.dump({k: r[k] for k in ('seed', 'level', 'cost_null', 'cost_ref')}, sys.stdout)
" >"$task/tests/calibration.json"

[ $# -eq 0 ] && set -- reference nop stop-early one-fix exploiter
for run in "$@"; do
  case "$run" in
    nop) args=(-a nop) ;;
    opus) args=(-a opencode -m anthropic/claude-opus-5-5 -k "${ATTEMPTS:-1}") ;;
    sonnet) args=(-a opencode -m anthropic/claude-sonnet-5-5 -k "${ATTEMPTS:-1}") ;;
    gemini)
      args=(-a opencode -m gemini/gemini-3.1-pro-preview -k "${ATTEMPTS:-1}"
        --ae "GOOGLE_GENERATIVE_AI_API_KEY=${GEMINI_API_KEY:?GEMINI_API_KEY is not set}")
      ;;
    *) args=(-a oracle --ae "POLICY=$run") ;;
  esac
  harbor run -p "$task" -o jobs --job-name "${JOB_PREFIX:-run}-l$LEVEL-s$SEED-$run-$(date +%H%M%S)" \
    "${args[@]}" "${extra[@]}" &
  sleep 2
done
wait
