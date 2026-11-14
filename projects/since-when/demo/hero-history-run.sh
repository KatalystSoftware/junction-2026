#!/bin/sh
# Runs a gapfinder module from this checkout against the scratch database, in a capped container:
#   sh projects/mariadb-wikipedia/demo/hero-history-run.sh <container suffix> <memory> <module and arguments>
#   sh projects/mariadb-wikipedia/demo/hero-history-run.sh load 2g gapfinder.revisions load Q1412941
# The container is gapfinder-a1-<suffix>. No --user: Docker is rootless here, and --user made the
# mounted folders unreadable. SINCE passes through from the caller's environment.
M=${M:-$HOME/junction2026-data/mariadb}
R=$(cd "$(dirname "$0")" && git rev-parse --show-toplevel)
name=$1 mem=$2; shift 2
exec docker run --rm --name gapfinder-a1-$name --memory $mem --network gapfinder-scratch-net \
  --env-file $M/scratch.env -e DB_HOST=gapfinder-scratch-db -e DB_PORT=3306 \
  -e REVISIONS=/revisions -e PYTHONUNBUFFERED=1 -e SINCE -e HF_HUB_OFFLINE=1 \
  -v $R/gapfinder:/app/gapfinder:ro -v $R/differences:/app/differences:ro \
  -v $M/revisions:/revisions -v gapfinder-scratch-models:/models \
  gapfinder-app:live-09f2a79 python -m "$@"
