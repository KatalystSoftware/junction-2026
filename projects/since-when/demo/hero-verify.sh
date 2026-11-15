#!/bin/sh
# Check the classifier's rows claim by claim against the whole other article (differences/claims.py).
#
#   sh demo/hero-verify.sh NAME PAIRS.jsonl ROWS.jsonl [--extract] [--offline]
#
# Run from projects/since-when/ on hestia. PAIRS.jsonl is what `python -m gapfinder pairs` wrote and
# ROWS.jsonl what hero_classify.py wrote for it (differences.jsonl). Five steps:
#
#   1. claims    the rows' claims and, with --extract, each passage's figures and dates (model)
#   2. search    every claim looked up in the other edition as of the pair's date (MariaDB, in the
#                project image, which has the embedding model for the claims)
#   3. reverse   one verdict per claim (model); each contradicted claim is turned round
#   4. search    the reverse claims looked up in the first edition
#   5. findings  their verdicts (model), and from all verdicts the finding rows
#
# Everything lands in $HERO_CLASSIFY/verify/NAME/ (default ~/junction2026-data/mariadb/classify):
# claims.jsonl, evidence.jsonl, reverse.jsonl, reverse-evidence.jsonl, differences.jsonl (the
# finding rows), set-aside.jsonl, verdicts.jsonl and judge.log. Model answers are cached in
# verify/cache/$JUDGE/, so a second run of the same claims sends nothing; --offline never sends
# anything.
#
#   JUDGE=super         Nemotron 3.5 Super VL on the dedicated Verda container (default); no
#                       per-minute limit, shared with the gap finder's run: keep WORKERS moderate
#   JUDGE=super-nvidia  the same model on NVIDIA Build's free tier
#   JUDGE=lightning     Nemotron 3.5 Lightning on NVIDIA Build
#   JUDGE=haiku         Claude Haiku 5.5, a second opinion
#   IMAGE=since-when (the project image), WORKERS=12, RETRIES=60, BATCH=6, and RPM, requests a
#   minute: 20 on NVIDIA Build, 600 elsewhere
#
# The model key comes from the environment: run this through
#   nix develop -c sops exec-env ../../secrets/secrets.yaml 'sh demo/hero-verify.sh ...'
# or with --offline. The database login comes from $M/scratch.env.
#
# Another database, such as a copy on the Verda machine: DB_ENV (the login file), NETWORK, DB_HOST,
# MODELS (the volume holding bge-m3) and CPUS (a cap for the search container). PYTHON runs the
# model steps, python3 by default; a command such as `docker run … since-when python` runs them in
# a container, which then needs the DIFFERENCES_* variables passed through and $out mounted at the
# same path.
set -eu

name=$1 pairs=$2 rows=$3
shift 3
extract="" offline=""
for arg in "$@"; do
  case $arg in
    --extract) extract=--extract ;;
    --offline) offline=--offline ;;
    *) echo "unknown option $arg" >&2; exit 2 ;;
  esac
done

M=${M:-$HOME/junction2026-data/mariadb}
root=${HERO_CLASSIFY:-$M/classify}/verify
out=$root/$name
judge=${JUDGE:-super}
rpm=600
case $judge in
  super) export DIFFERENCES_PROVIDER=verda-super DIFFERENCES_MODEL=nemotron-3.5-super-vl
         export DIFFERENCES_TIMEOUT="${DIFFERENCES_TIMEOUT:-1800}" ;;   # a busy container queues for minutes
  super-nvidia) export DIFFERENCES_PROVIDER=nvidia DIFFERENCES_MODEL=nvidia/nemotron-3.5-super-vl-120b-a12b; rpm=20 ;;
  lightning) export DIFFERENCES_PROVIDER=nvidia DIFFERENCES_MODEL=nvidia/nemotron-3.5-lightning-30b-a3b; rpm=20 ;;
  haiku) export DIFFERENCES_PROVIDER=anthropic DIFFERENCES_MODEL=claude-haiku-5-5 ;;
  *) echo "JUDGE is super, super-nvidia, lightning or haiku" >&2; exit 2 ;;
esac
export DIFFERENCES_CLAIMS_CACHE="$root/cache/$judge" DIFFERENCES_RPM="${RPM:-$rpm}"
if [ -n "$offline" ]; then   # the cache key needs the endpoint and the model, not the key
  [ "$DIFFERENCES_PROVIDER" = verda-super ] && export VERDA_INFERENCE_KEY="${VERDA_INFERENCE_KEY:-offline}"
  [ "$DIFFERENCES_PROVIDER" = nvidia ] && export NVIDIA_API_KEY="${NVIDIA_API_KEY:-offline}"
  [ "$DIFFERENCES_PROVIDER" = anthropic ] && export ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-offline}"
fi
mkdir -p "$out" "$DIFFERENCES_CLAIMS_CACHE"

model="--workers ${WORKERS:-12} --retries ${RETRIES:-60} --batch ${BATCH:-6} $offline"
py=${PYTHON:-python3}

search() {   # search IN OUT: the claims of $out/IN with their evidence, as $out/OUT
  docker run --rm --name "since-when-verify-$name" --network "${NETWORK:-gapfinder-scratch-net}" \
    --env-file "${DB_ENV:-$M/scratch.env}" -e DB_HOST="${DB_HOST:-gapfinder-scratch-db}" -e DB_PORT=3306 \
    -e HF_HUB_OFFLINE=1 -v "$PWD/gapfinder:/app/gapfinder:ro" -v "$PWD/differences:/app/differences:ro" \
    -v "${MODELS:-gapfinder-scratch-models}:/models" -v "$out:/work" --memory 3500m ${CPUS:+--cpus "$CPUS"} \
    "${IMAGE:-since-when}" sh -c "python -m gapfinder.evidence search /work/$1 > /work/$2"
}

# A step that fails stops the run (set -e); the model's progress and errors are in judge.log.
# shellcheck disable=SC2086
$py -m differences.claims claims "$pairs" "$rows" $extract $model > "$out/claims.jsonl"
search claims.jsonl evidence.jsonl
# shellcheck disable=SC2086
$py -m differences.claims reverse "$out/evidence.jsonl" $model > "$out/reverse.jsonl" 2> "$out/judge.log"
search reverse.jsonl reverse-evidence.jsonl
# shellcheck disable=SC2086
$py -m differences.claims findings "$out/evidence.jsonl" "$pairs" "$rows" \
  --reverse "$out/reverse-evidence.jsonl" --out "$out" $model 2>> "$out/judge.log"
