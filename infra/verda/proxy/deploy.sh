#!/usr/bin/env bash
# Ships this folder to the Verda machine and applies it. Needs SSH access to the machine:
# VERDA_HOST, or a `junction-runner` entry in ~/.ssh/config for root@31.22.104.106.
set -euo pipefail
cd "$(dirname "$0")"
host=${VERDA_HOST:-junction-runner}
tar -c Caddyfile compose.yaml proxy.env sites up.sh \
  | ssh "$host" 'mkdir -p /srv/katalyst/proxy && tar -x -C /srv/katalyst/proxy && /srv/katalyst/proxy/up.sh'
