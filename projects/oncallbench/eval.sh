#!/usr/bin/env bash
# One measurement: plays the given runs on one episode and appends a record per run to
# metrics.json (round, commit, level, seed, run, score, cost_usd, duration, failure category).
#
# Usage: ./eval.sh <round> <level> <seed> <run>...
#   runs: reference nop stop-early one-fix exploiter (scripted) | opus sonnet gemini (OpenCode)
# Agent runs need the keys in the environment:
#   sops exec-env ../../secrets/secrets.yaml './eval.sh 1 1 101 opus gemini'
set -euo pipefail
cd "$(dirname "$0")"
round=$1 level=$2 seed=$3
shift 3
python=(python3); command -v python3 >/dev/null || python=(nix shell nixpkgs#python313 -c python3)
SEED=$seed LEVEL=$level JOB_PREFIX=r$round ./run.sh "$@" || true
"${python[@]}" -B collect.py "$(git rev-parse --short HEAD)"
