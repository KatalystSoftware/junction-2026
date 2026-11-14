#!/bin/sh
# Promotes the demo snapshot and this branch's code to the live machine, or goes back.
#
#   sh projects/mariadb-wikipedia/demo/promote.sh                    # dry run: print each action
#   sh projects/mariadb-wikipedia/demo/promote.sh --run              # do it
#   sh projects/mariadb-wikipedia/demo/promote.sh --rollback         # dry run of going back
#   sh projects/mariadb-wikipedia/demo/promote.sh --rollback --run   # go back
#
# Run from a checkout of demo/mariadb-overnight on hestia. What it changes on live, and what it
# assumes about live that nobody could check under the read-only rule, is in HANDOFF.md.
# Written overnight and checked with `sh -n`, shellcheck and the dry run only; never run on live.
set -eu

SNAPSHOT=${SNAPSHOT:-$HOME/junction2026-data/mariadb/snapshot-demo-20261114-0730/gapfinder.sql.zst}
LIVE_SSH=${LIVE_SSH:-$HOME/junction2026-data/mariadb/bin/live-ssh}
SITE=${SITE:-https://31-22-104-106.sslip.io}
BRANCH=${BRANCH:-HEAD}

run=0 rollback=0
for arg in "$@"; do
  case $arg in
    --run) run=1 ;;
    --rollback) rollback=1 ;;
    *) echo "usage: $0 [--rollback] [--run]" >&2; exit 2 ;;
  esac
done

root=$(git rev-parse --show-toplevel)
here=$root/projects/mariadb-wikipedia/demo

step() {  # step "what it does" command…: print it, and with --run do it
  echo "==> $1"
  shift
  if [ "$run" = 1 ]; then "$@"; else echo "    would run: $*"; fi
}

# The part that runs on live. It is copied there as a file and run from the file: read from
# standard input, `docker exec -i` and `docker compose exec -T` would swallow the rest of it.
remote_script() {
  cat <<EOF
set -euo pipefail
ROLLBACK=$rollback
EOF
  cat <<'EOF'
cd ~/promote
deploy=$(docker inspect gapfinder-api-1 --format '{{ index .Config.Labels "com.docker.compose.project.working_dir" }}')
root=${deploy%/projects/mariadb-wikipedia/deploy}
if [ "$root" = "$deploy" ] || [ ! -f "$deploy/.env" ] || [ ! -x "$deploy/deploy.sh" ]; then
  echo "The api container was not started from projects/mariadb-wikipedia/deploy with a .env: $deploy" >&2
  exit 1
fi
current=$(sed -n 's/^DB_NAME=//p' "$deploy/.env"); current=${current:-gapfinder}
echo "Deploy directory $deploy, serving $current"
sql() { docker exec -i gapfinder-db-1 sh -c 'exec mariadb -uroot -p"$MARIADB_ROOT_PASSWORD" "$@"' sh "$@"; }

if [ "$ROLLBACK" = 1 ]; then
  [ -f db-before ] && [ -f code-before.tgz ] || { echo "no ~/promote/db-before: nothing was promoted from here" >&2; exit 1; }
  before=$(cat db-before)
  [ -n "$(sql -N -e "SHOW DATABASES LIKE '$before'")" ] || { echo "$before is gone" >&2; exit 1; }
  tar -xzf code-before.tgz -C "$root"
  cd "$deploy"
  (umask 077; grep -v '^DB_NAME=' .env > .env.new || true; echo "DB_NAME=$before" >> .env.new; mv .env.new .env)
  # Builds the previous code again and restarts the API on the previous database.
  ./deploy.sh
  echo "Back on $before with the code of before the promotion"
  exit 0
fi

# deploy.sh keeps the database in use before the load and the new one, and drops the other
# gapfinder_* databases. A second promotion would therefore drop the one to go back to.
if [ -f db-before ] && [ "$(cat db-before)" != "$current" ]; then
  echo "Already promoted from here: live was on $(cat db-before) and serves $current now. Stopping," >&2
  echo "because another load would drop $(cat db-before). To go back: promote.sh --rollback --run" >&2
  exit 1
fi
sha256sum -c SHA256SUMS
# Once: the database and the code as they are now, for the rollback.
if [ ! -f db-before ]; then
  tar -czf code-before.tgz -C "$root" gapfinder differences ui \
    projects/mariadb-wikipedia/deploy/deploy.sh projects/mariadb-wikipedia/deploy/compose.yaml \
    projects/mariadb-wikipedia/deploy/Dockerfile
  echo "$current" > db-before
fi
tar -xf code.tar -C "$root"
cd "$deploy"

# The SELECT-only user of the Run button (demo/live-sql.md, "For the integrator").
grep -q '^DB_RO_PASSWORD=' .env || printf 'DB_RO_USER=gapfinder_ro\nDB_RO_PASSWORD=%s\n' \
  "$(head -c 24 /dev/urandom | od -An -tx1 | tr -d ' \n')" >> .env
set -a; . ./.env; set +a
docker exec -i -e DB_RO_USER -e DB_RO_PASSWORD gapfinder-db-1 sh -c 'exec mariadb -uroot -p"$MARIADB_ROOT_PASSWORD" -e "
  CREATE USER IF NOT EXISTS \"$DB_RO_USER\"@\"%\" IDENTIFIED BY \"$DB_RO_PASSWORD\" WITH MAX_STATEMENT_TIME 5;
  GRANT SELECT ON \`gapfinder\`.* TO \"$DB_RO_USER\"@\"%\";
  GRANT SELECT ON \`gapfinder\\_%\`.* TO \"$DB_RO_USER\"@\"%\";"' </dev/null

# Builds the image, loads the snapshot into gapfinder_<UTC time>, points the API at it, drops
# the gapfinder_* databases other than that one and the one in use until now, and warms up.
./deploy.sh ~/promote/gapfinder.sql.zst </dev/null
echo "Promoted. Now serving $(sed -n 's/^DB_NAME=//p' .env)"
EOF
}

send() {  # send <remote file under ~/promote>: standard input into that file on live
  "$LIVE_SSH" "mkdir -p ~/promote && cat > ~/promote/$1"
}
send_snapshot() { send gapfinder.sql.zst < "$SNAPSHOT"; }
send_sums() { send SHA256SUMS < "$(dirname "$SNAPSHOT")/SHA256SUMS"; }
send_code() {
  git -C "$root" archive --format=tar "$BRANCH" gapfinder differences ui \
    projects/mariadb-wikipedia/deploy/deploy.sh projects/mariadb-wikipedia/deploy/compose.yaml \
    projects/mariadb-wikipedia/deploy/Dockerfile | send code.tar
}
send_script() { remote_script | send promote-remote.sh; }
run_remote() { "$LIVE_SSH" 'bash ~/promote/promote-remote.sh' </dev/null; }
check_presets() { curl -fsS "$SITE/api/sql/presets" | grep -o '"enabled": *[a-z]*'; }
check_site() { sh "$here/hero-history-check.sh" "$SITE"; }

if [ "$rollback" = 1 ]; then
  echo "Going back to the database and the code of before the promotion, on $SITE"
  step "copy the rollback script to live (~/promote/promote-remote.sh)" send_script
  step "on live: restore the code from ~/promote/code-before.tgz, set DB_NAME in .env back to the name in ~/promote/db-before, run deploy.sh without a snapshot" run_remote
  step "check: the site answers" curl -fsS -o /dev/null -w '%{http_code}\n' "$SITE/api/queue?limit=1"
else
  [ -f "$SNAPSHOT" ] || { echo "No snapshot at $SNAPSHOT (set SNAPSHOT=…)" >&2; exit 1; }
  (cd "$(dirname "$SNAPSHOT")" && sha256sum -c SHA256SUMS >/dev/null) || { echo "$SNAPSHOT does not match its SHA256SUMS" >&2; exit 1; }
  echo "Promoting $SNAPSHOT and the code of $(git -C "$root" rev-parse --short "$BRANCH") to $SITE"
  step "copy the snapshot to live (~/promote/gapfinder.sql.zst, $(du -h "$SNAPSHOT" | cut -f1))" send_snapshot
  step "copy its checksum to live (~/promote/SHA256SUMS)" send_sums
  step "copy the code to live (~/promote/code.tar: gapfinder, differences, ui and three deploy files of $BRANCH)" send_code
  step "copy the script for live (~/promote/promote-remote.sh)" send_script
  step "on live: stop if a promotion from here already happened; check the checksum; keep the name of the database in use in ~/promote/db-before and the present code in ~/promote/code-before.tgz; unpack the new code; add DB_RO_USER and DB_RO_PASSWORD to .env and create the SELECT-only user gapfinder_ro; run deploy.sh with the snapshot" run_remote
  step "check: the Run button is on (\"enabled\": true)" check_presets
  step "check: 54 compare views and 8 first sentences on live" check_site
fi

if [ "$run" = 0 ]; then
  echo
  echo "Dry run: nothing was sent and nothing was changed. The script that would run on live:"
  echo
  remote_script | sed 's/^/    /'
  echo
  echo "Add --run to do it."
fi
