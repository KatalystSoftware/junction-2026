#!/usr/bin/env bash
# Publish the hosted demo: Kutsu's built page at the root of https://kutsu.duckymcduck2.workers.dev/ (the product has ONE name, Kutsu:
# the user, 2026-11-14; the old worker name esittely.duckymcduck2.workers.dev gets the same deploy so old links work), this app under /apply/,
# and the same tree as the tailnet copy. Kutsu is built in the team repo clone on swarm1 (projects/kutsu, `npm --prefix ui run build`).
set -euo pipefail
cd "$(dirname "$0")/.."
K='~/projects/junction2026/projects/kutsu'
rsync -a --delete --exclude __pycache__ app/ swarm1:~/projects/esittely-worker/public/apply/
rsync -a --delete ../pitch/ swarm1:~/projects/esittely-worker/public/pitch/   # the pitch deck, at /pitch/
ssh swarm1 "set -e; W=~/projects/esittely-worker; cp -r $K/ui/dist/. \$W/public/; cp $K/signals.json $K/presets.json $K/pool.json $K/applications.json \$W/public/; cd \$W && export PATH=\$HOME/.npm-global/bin:\$PATH && wrangler deploy --name kutsu 2>&1 | tail -2 && wrangler deploy 2>&1 | tail -1"
rsync -a --delete --exclude __pycache__ app/ ~/swarm-dash/static/apply/
rsync -a --delete ../pitch/ ~/swarm-dash/static/pitch/
curl -s -o /dev/null -w "root %{http_code}, " https://kutsu.duckymcduck2.workers.dev/; curl -s -o /dev/null -w "apply %{http_code}, " https://kutsu.duckymcduck2.workers.dev/apply/; curl -s -o /dev/null -w "old address %{http_code}\n" https://esittely.duckymcduck2.workers.dev/; curl -s -o /dev/null -w "pitch %{http_code}\n" https://kutsu.duckymcduck2.workers.dev/pitch/
