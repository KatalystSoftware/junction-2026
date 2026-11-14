#!/usr/bin/env bash
# Deploys the committed Since When (HEAD of this checkout) to the Verda machine.
#
#   deploy/deploy.sh                            # redeploy the code
#   deploy/deploy.sh path/to/gapfinder.sql.zst  # also replace the database with this snapshot
#
# Needs SSH access to the machine: VERDA_HOST, or a `junction-runner` entry in ~/.ssh/config for
# root@31.22.104.106. The machine keeps its own .env; nothing secret is sent.
set -euo pipefail
cd "$(dirname "$0")/.."
host=${VERDA_HOST:-junction-runner}
dir=/srv/katalyst/since-when

snapshot=
if [ $# -gt 0 ]; then
  snapshot=/srv/katalyst/since-when-snapshot.sql.zst
  ssh "$host" 'mkdir -p /srv/katalyst'
  scp -q "$1" "$host:$snapshot"
fi

# A fresh copy of the project replaces the old one, so files deleted here are gone there too.
git archive HEAD . | ssh "$host" "set -e
  rm -rf $dir.new && mkdir -p $dir.new && tar -x -C $dir.new
  if [ -f $dir/deploy/.env ]; then cp -p $dir/deploy/.env $dir.new/deploy/.env; fi
  rm -rf $dir.old
  if [ -d $dir ]; then mv $dir $dir.old; fi
  mv $dir.new $dir
  $dir/deploy/up.sh $snapshot"
