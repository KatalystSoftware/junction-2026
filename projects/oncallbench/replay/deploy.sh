#!/usr/bin/env bash
# Ships the viewer and its committed bundles to the Verda machine, into the folder the shared
# proxy serves as incident.<base domain> (infra/verda/proxy/sites/incident.caddy). Copies files
# only and replaces the data folder there, so a bundle dropped here is dropped there: nothing is
# restarted. Needs SSH access: VERDA_HOST, or `junction-runner` in ~/.ssh/config.
set -euo pipefail
cd "$(dirname "$0")"
host=${VERDA_HOST:-junction-runner}
dir=/srv/katalyst/proxy/static/incident
# a bundle of a shipped task's seed is that task's answer key: never put one on the public site
shipped=" 101 102 103 $(sed -n 's/^SEED = \([0-9]*\).*/\1/p' ../tasks/*/environment/mcp-server/server.py | tr '\n' ' ')"
for f in data/l*-s*.js; do
  seed=${f##*-s}; seed=${seed%.js}
  if [[ $shipped == *" $seed "* ]]; then echo "refused: $f is the bundle of a shipped task's seed" >&2; exit 1; fi
done
# the scores band only ever ships real runs: export.py --metrics marks anything else a placeholder
if grep -q '"placeholder":true' data/spread.js 2>/dev/null; then
  echo "refused: data/spread.js holds placeholder scores. Run python3 export.py --spread first." >&2; exit 1
fi
tar -c index.html app.js phone.js style.css logo.svg fonts data/index.js data/spread.js data/l*-s*.js \
  | ssh "$host" "mkdir -p $dir && rm -rf $dir/data && tar -x --no-same-owner -C $dir && chmod -R a+rX $dir"
echo "shipped to $host:$dir"
