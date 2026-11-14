#!/usr/bin/env bash
# Put the talent brief page on the Verda runner: http://31.22.104.106:8046
#
#   sops exec-env ../../secrets/secrets.yaml ./deploy.sh
#
# Builds the page, copies it with the code, the stored briefs and the request cache to /srv/talent-brief, writes the three API
# keys from the environment into a root-only file there, and (re)starts a systemd service that runs
# serve.py as its own user. Ports 80 and 443 on that machine belong to the gap finder, so this stays
# on plain http on its own port. Temporary: `systemctl disable --now talent-brief` takes it down.
set -euo pipefail
cd "$(dirname "$0")"
HOST=root@31.22.104.106
SSH=(ssh -i "${VERDA_SSH_KEY:-$HOME/.ssh/id_ed25519_verda}" -o BatchMode=yes)
DIR=/srv/talent-brief

"${SSH[@]}" "$HOST" "id talentbrief >/dev/null 2>&1 || useradd --system --home $DIR --shell /usr/sbin/nologin talentbrief; mkdir -p $DIR/ui; rm -f $DIR/index.html"
npm --prefix ui ci --no-audit --no-fund >/dev/null
npm --prefix ui run build >/dev/null
rsync -az -e "${SSH[*]}" \
  lib.py signals.py serve.py presets.json companies.json roles.json api-cache "$HOST:$DIR/"
rsync -az --delete -e "${SSH[*]}" ui/dist "$HOST:$DIR/ui/"
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
printf 'EXA_API_KEY=%s\nCONTEXT_DEV_API_KEY=%s\nANTHROPIC_API_KEY=%s\nHOST=0.0.0.0\n' \
  "$EXA_API_KEY" "$CONTEXT_DEV_API_KEY" "$ANTHROPIC_API_KEY" |
  "${SSH[@]}" "$HOST" "umask 077; cat > /etc/talent-brief.env"
"${SSH[@]}" "$HOST" "chown -R talentbrief: $DIR && cat > /etc/systemd/system/talent-brief.service && systemctl daemon-reload && systemctl enable --now talent-brief && systemctl restart talent-brief && sleep 2 && systemctl is-active talent-brief" <<UNIT
[Unit]
Description=Talent brief demo (junction2026 spikes/espoo-companies)
After=network-online.target

[Service]
User=talentbrief
WorkingDirectory=$DIR
EnvironmentFile=/etc/talent-brief.env
ExecStart=/usr/bin/python3 serve.py
Restart=on-failure
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
ReadWritePaths=$DIR

[Install]
WantedBy=multi-user.target
UNIT
curl -s -o /dev/null -w "page: http %{http_code}\n" --max-time 10 http://31.22.104.106:8046/
