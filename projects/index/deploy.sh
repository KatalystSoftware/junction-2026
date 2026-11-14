#!/usr/bin/env bash
# Ships site/ to the Verda machine, into the folder the shared proxy serves on the bare domain
# (infra/verda/proxy/sites/index.caddy). Copies files only: nothing is restarted or reloaded.
# Needs SSH access to the machine: VERDA_HOST, or a `junction-runner` entry in ~/.ssh/config.
set -euo pipefail
cd "$(dirname "$0")/site"
host=${VERDA_HOST:-junction-runner}
dir=/srv/katalyst/proxy/static/index
tar -c . | ssh "$host" "mkdir -p $dir && tar -x --no-same-owner -C $dir && chmod -R a+rX $dir"
