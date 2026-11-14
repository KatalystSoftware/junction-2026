#!/usr/bin/env bash
# Put Kutsu on the Verda runner: https://kutsu.katalyst.fyi (the shared proxy forwards to port 8046 here)
#
#   sops exec-env ../../secrets/secrets.yaml ./deploy.sh
#
# Checks the page and stops if the check fails. Then builds it, copies it with the code and the stored briefs to /srv/talent-brief, adds this
# machine's request cache to the server's (when there is one here; the cache is not in git), writes the three API
# keys and the demo key (KUTSU_KEY) from the environment into a root-only file there, and (re)starts a systemd
# service that runs serve.py as its own user. It listens only on the proxy's Docker network (HOST below):
# ports 80 and 443 belong to the shared proxy, which is the only way in. Temporary: `systemctl disable --now
# talent-brief` takes it down.
set -euo pipefail
cd "$(dirname "$0")"
HOST=root@31.22.104.106
SSH=(ssh -i "${VERDA_SSH_KEY:-$HOME/.ssh/id_ed25519_verda}" -o BatchMode=yes)
DIR=/srv/talent-brief

# nothing is built or copied unless the page passes its check: a restart interrupts whoever is on the page
npm --prefix ui ci --no-audit --no-fund >/dev/null
npm --prefix ui run check
npm --prefix ui run build >/dev/null
"${SSH[@]}" "$HOST" "id talentbrief >/dev/null 2>&1 || useradd --system --home $DIR --shell /usr/sbin/nologin talentbrief; mkdir -p $DIR/ui; rm -f $DIR/index.html"
rsync -az -e "${SSH[*]}" \
  lib.py signals.py serve.py monitors.py person.py presets.json pool.json applications.json companies.json roles.json "$HOST:$DIR/"
# The request cache is not in git, so a checkout may not have it. What is here is added to the server's copy; nothing
# on the server is ever deleted or replaced by an older file, so a deploy from a bare checkout leaves that copy whole.
if [ -d api-cache ]; then rsync -az --update -e "${SSH[*]}" api-cache "$HOST:$DIR/"; fi
# No --delete: a tab opened before a redeploy still asks for the old hashed files under assets/, and
# deleting them leaves that tab blank until it is reloaded.
rsync -az -e "${SSH[*]}" ui/dist "$HOST:$DIR/ui/"
# The first applicant pages (projects/espoo-recruitment/app), which serve.py serves under /apply/ (the folder keeps its old name)
rsync -az --delete -e "${SSH[*]}" ../espoo-recruitment/app/ "$HOST:$DIR/esittely/"
# The pitch deck (projects/espoo-recruitment/pitch), which serve.py serves under /pitch/
rsync -az --delete -e "${SSH[*]}" ../espoo-recruitment/pitch/ "$HOST:$DIR/pitch/"
# signals.json grows on the server with every live search: ours replace the same ids, the rest stay
rsync -az -e "${SSH[*]}" signals.json "$HOST:$DIR/signals.ours.json"
"${SSH[@]}" "$HOST" "cd $DIR && python3 -" <<'PY'
import json, os
ours = json.load(open("signals.ours.json"))
theirs = json.load(open("signals.json")) if os.path.exists("signals.json") else []
ids = {b["id"] for b in ours}
out = sorted(ours + [b for b in theirs if b["id"] not in ids], key=lambda b: b["name"].lower())
json.dump(out, open("signals.json", "w"), ensure_ascii=False, indent=1)
PY
# HOST: the gateway of the proxy's Docker network, so only the proxy reaches the app (sites/kutsu.caddy)
printf 'EXA_API_KEY=%s\nCONTEXT_DEV_API_KEY=%s\nANTHROPIC_API_KEY=%s\nKUTSU_KEY=%s\nHOST=172.19.0.1\n' \
  "$EXA_API_KEY" "$CONTEXT_DEV_API_KEY" "$ANTHROPIC_API_KEY" "${KUTSU_KEY:?KUTSU_KEY from secrets.yaml}" |
  "${SSH[@]}" "$HOST" "umask 077; cat > /etc/talent-brief.env"
"${SSH[@]}" "$HOST" "chown -R talentbrief: $DIR && cat > /etc/systemd/system/talent-brief.service && systemctl daemon-reload && systemctl enable --now talent-brief && systemctl restart talent-brief && sleep 2 && systemctl is-active talent-brief" <<UNIT
[Unit]
Description=Kutsu demo (junction2026 projects/kutsu)
After=network-online.target

[Service]
User=talentbrief
WorkingDirectory=$DIR
EnvironmentFile=/etc/talent-brief.env
ExecStart=/usr/bin/python3 serve.py
Restart=on-failure
# the proxy's network may come up after this does; the address is then not there yet to listen on
RestartSec=5
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
ReadWritePaths=$DIR

[Install]
WantedBy=multi-user.target
UNIT
curl -s -o /dev/null -w "page: http %{http_code}\n" --max-time 10 https://kutsu.katalyst.fyi/
