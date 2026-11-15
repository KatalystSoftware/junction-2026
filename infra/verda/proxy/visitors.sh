#!/usr/bin/env bash
# Who visited our sites in the last N minutes (default 15): per site, page loads and distinct visitors
# (by IP address, so people behind one shared network count once). Our own curl checks and bots are left out.
#   ./visitors.sh [minutes]
# Reads the proxy's access log (the `access` snippet in the Caddyfile) over SSH; needs jq here.
set -euo pipefail
host=${VERDA_HOST:-junction-runner}
ssh "$host" "docker logs --since ${1:-15}m proxy-caddy-1 2>&1" \
  | grep '"handled request"' \
  | jq -r 'select((.resp_headers["Content-Type"][0] // "") | startswith("text/html")) | select((.request.headers["User-Agent"][0] // "") | test("curl|bot|Bot|Headless|python|Go-http") | not) | [.request.host, .request.remote_ip] | @tsv' \
  | awk -F'\t' '{loads[$1]++; if (!seen[$1 FS $2]++) people[$1]++} END {for (h in loads) printf "%-32s %4d page loads, %3d visitors\n", h, loads[h], people[h]}' \
  | sort
