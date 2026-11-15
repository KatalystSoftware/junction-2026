#!/usr/bin/env bash
# Runs on the Verda machine (deploy.sh ships the project and calls it): builds and starts Since When.
#
#   ./up.sh                          # build and start
#   ./up.sh /path/gapfinder.sql.zst  # also load this snapshot and switch the app to it
#
# A snapshot goes into a new database and the app switches to it once it is loaded, so the site
# keeps answering meanwhile. The database before it is kept; older ones are dropped.
#
# Passwords are made here on first run and stay in .env on the machine.
set -euo pipefail
cd "$(dirname "$0")"

secret() { head -c 16 /dev/urandom | od -An -tx1 | tr -d ' \n'; }
if [ ! -f .env ]; then
  umask 077
  printf 'DB_PASSWORD=%s\nDB_ROOT_PASSWORD=%s\nDB_RO_PASSWORD=%s\n' "$(secret)" "$(secret)" "$(secret)" > .env
fi
setenv() {  # setenv KEY VALUE: replace or add a line in .env
  grep -v "^$1=" .env > .env.new || true
  echo "$1=$2" >> .env.new
  mv .env.new .env
}
sql() { docker compose exec -T db sh -c 'exec mariadb -uroot -p"$MARIADB_ROOT_PASSWORD" "$@"' sh "$@"; }

docker network inspect proxy >/dev/null 2>&1 || docker network create proxy
docker compose build
docker compose up -d --wait db

current=$(sed -n 's/^DB_NAME=//p' .env); current=${current:-since_when}
if [ $# -gt 0 ]; then
  next=since_when_$(date -u +%Y%m%d_%H%M)
  echo "Loading $1 into $next (the app keeps using $current meanwhile)"
  sql -e "CREATE DATABASE $next; GRANT ALL ON $next.* TO 'since_when'@'%';"
  zstd -dc "$1" | sql "$next"
  setenv DB_NAME "$next"
  for old in $(sql -N -e "SHOW DATABASES LIKE 'since\\_when%'"); do
    [ "$old" = "$next" ] || [ "$old" = "$current" ] || sql -e "DROP DATABASE $old"
  done
  current=$next
fi

# The Run button's user may only SELECT. Its password goes from .env to the server through the
# container's environment, never on a command line.
docker compose exec -T -e RO="$(sed -n 's/^DB_RO_PASSWORD=//p' .env)" -e DB="$current" db sh -c 'exec mariadb -uroot -p"$MARIADB_ROOT_PASSWORD" -e "
  CREATE USER IF NOT EXISTS since_when_ro@\"%\" IDENTIFIED BY \"$RO\";
  ALTER USER since_when_ro@\"%\" IDENTIFIED BY \"$RO\";
  GRANT SELECT ON \`$DB\`.* TO since_when_ro@\"%\";"'

# What a review decided after reading both articles (demo/hand-checked.json): on every deploy, since
# a snapshot loaded from scratch does not carry it.
docker compose run --rm -T app python -m gapfinder.checked hand - < ../demo/hand-checked.json

docker compose up -d --remove-orphans
echo "Since When is up behind the proxy (infra/verda/proxy) as since-when-app:8078"

# The first answer for a topic with its full history walks every version of its passages (a few
# seconds); ask for the three on the front page once, so no visitor waits for it.
docker compose exec -T app python -c '
import time, urllib.request
for _ in range(60):
    try:
        for q in ("Q1412941", "Q736268", "Q2457646"):
            urllib.request.urlopen(f"http://127.0.0.1:8078/api/topics/{q}", timeout=60).read()
        break
    except Exception:
        time.sleep(2)
' && echo "Front-page topics warmed"
