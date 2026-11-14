#!/usr/bin/env bash
# Runs on the Verda machine (deploy.sh ships the project and calls it): builds and starts Since When.
#
#   ./up.sh                          # build and start
#   ./up.sh /path/gapfinder.sql.zst  # first replace the database with this snapshot
#
# Passwords are made here on first run and stay in .env on the machine.
set -euo pipefail
cd "$(dirname "$0")"

secret() { head -c 16 /dev/urandom | od -An -tx1 | tr -d ' \n'; }
if [ ! -f .env ]; then
  umask 077
  printf 'DB_PASSWORD=%s\nDB_ROOT_PASSWORD=%s\nDB_RO_PASSWORD=%s\n' "$(secret)" "$(secret)" "$(secret)" > .env
fi
sql() { docker compose exec -T db sh -c 'exec mariadb -uroot -p"$MARIADB_ROOT_PASSWORD" "$@"' sh "$@"; }

docker network inspect proxy >/dev/null 2>&1 || docker network create proxy
docker compose build
docker compose up -d --wait db

if [ $# -gt 0 ]; then
  echo "Loading $1 (the app answers errors until it is in)"
  sql -e "DROP DATABASE IF EXISTS since_when; CREATE DATABASE since_when; GRANT ALL ON since_when.* TO 'since_when'@'%';"
  zstd -dc "$1" | sql since_when
fi

# The Run button's user may only SELECT. Its password goes from .env to the server through the
# container's environment, never on a command line.
docker compose exec -T -e RO="$(sed -n 's/^DB_RO_PASSWORD=//p' .env)" db sh -c 'exec mariadb -uroot -p"$MARIADB_ROOT_PASSWORD" -e "
  CREATE USER IF NOT EXISTS since_when_ro@\"%\" IDENTIFIED BY \"$RO\";
  ALTER USER since_when_ro@\"%\" IDENTIFIED BY \"$RO\";
  GRANT SELECT ON since_when.* TO since_when_ro@\"%\";"'

docker compose up -d --remove-orphans
echo "Since When is up behind the proxy (infra/verda/proxy) as since-when-app:8078"
