#!/usr/bin/env bash
# Publish the hosted demo: Kutsu's built page at the root of https://esittely.duckymcduck2.workers.dev/, this app under /esittely/,
# and the same tree as the tailnet copy. Kutsu is built in the team repo clone on swarm1 (projects/kutsu, `npm --prefix ui run build`).
set -euo pipefail
cd "$(dirname "$0")/.."
K='~/projects/junction2026/projects/kutsu'
rsync -a --delete --exclude __pycache__ app/ swarm1:~/projects/esittely-worker/public/esittely/
ssh swarm1 "set -e; W=~/projects/esittely-worker; cp -r $K/ui/dist/. \$W/public/; cp $K/signals.json $K/presets.json $K/pool.json \$W/public/; cd \$W && export PATH=\$HOME/.npm-global/bin:\$PATH && wrangler deploy 2>&1 | tail -2"
rsync -a --delete --exclude __pycache__ app/ ~/swarm-dash/static/esittely/
curl -s -o /dev/null -w "root %{http_code}, " https://esittely.duckymcduck2.workers.dev/; curl -s -o /dev/null -w "esittely %{http_code}\n" https://esittely.duckymcduck2.workers.dev/esittely/
