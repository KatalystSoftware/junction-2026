#!/bin/sh
# Bring every seed of a spread up to N verified runs: jobs whose verifier never ran because of an
# infrastructure failure move to jobs-infra-failed/ and are run again (one Harbor job per run).
#   ./fill.sh <base|ft> <served model> <tasks-custom dir> <runs per seed> <seed>...
kind=$1 served=$2 tasks=$3 n=$4
shift 4
jobs="$tasks/../jobs"
mkdir -p "$tasks/../jobs-infra-failed"
for j in "$jobs"/${ROUND:-r16}-l4-s*-gemma-$kind-*; do
  [ -d "$j" ] || continue
  if ! ls "$j"/*/verifier/reward.json >/dev/null 2>&1 && grep -qs "address pools\|Docker compose command failed" "$j"/*/exception.txt; then
    mv "$j" "$tasks/../jobs-infra-failed/"
  fi
done
for seed in "$@"; do
  have=$(ls -d "$jobs"/${ROUND:-r16}-l4-s$seed-gemma-$kind-*/*/verifier/reward.json 2>/dev/null | wc -l)
  [ "$have" -lt "$n" ] && ./spread.sh "$kind" "$served" "$tasks" $((n - have)) "$seed" &
  sleep 3
done
wait
