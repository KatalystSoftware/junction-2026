#!/usr/bin/env bash
# Runs on the Verda machine (deploy.sh ships this folder and calls it): starts the proxy, or
# applies a changed proxy.env or sites/ file to the running one.
set -euo pipefail
cd "$(dirname "$0")"
docker network inspect proxy >/dev/null 2>&1 || docker network create proxy
docker compose up -d
docker compose exec -T caddy caddy reload --config /etc/caddy/Caddyfile
