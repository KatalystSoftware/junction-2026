#!/usr/bin/env bash
# Ships the viewer and its committed bundles to the Verda machine, into the folder the shared
# proxy serves as incident.<base domain> (infra/verda/proxy/sites/incident.caddy). Copies files
# only and replaces the data folder there, so a bundle dropped here is dropped there: nothing is
# restarted. Needs SSH access: VERDA_HOST, or `junction-runner` in ~/.ssh/config.
set -euo pipefail
cd "$(dirname "$0")"
host=${VERDA_HOST:-junction-runner}
dir=/srv/katalyst/proxy/static/incident
tar -c index.html app.js style.css fonts data/index.js data/l*-s*.js \
  | ssh "$host" "mkdir -p $dir && rm -rf $dir/data && tar -x --no-same-owner -C $dir && chmod -R a+rX $dir"
echo "shipped to $host:$dir"
