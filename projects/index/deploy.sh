#!/usr/bin/env bash
# Publishes one GitHub Pages site on the public repository's gh-pages branch: site/ at the root (the
# index page, and the Spread pitch under spread/) and the on-call shift replay under incident/.
# Until the event ended these were served from our Verda machine on katalyst.fyi; that machine is gone.
#   ./deploy.sh [OWNER/NAME]      default KatalystSoftware/junction-2026
# The branch is one commit, replaced on every run. Pages was switched on for it once, with
#   gh api -X POST repos/OWNER/NAME/pages -f 'source[branch]=gh-pages' -f 'source[path]=/'
# Needs git and a GitHub login that may push there.
set -euo pipefail
cd "$(dirname "$0")"
repo=${1:-KatalystSoftware/junction-2026}
out=$(mktemp -d)
trap 'rm -rf "$out"' EXIT
cp -r site/. "$out"
../oncallbench/replay/deploy.sh --to "$out/incident"
touch "$out/.nojekyll" # serve the files as they are, with no Jekyll build
git -C "$out" init -q -b gh-pages
git -C "$out" add -A
git -C "$out" commit -q -m "site: built from $(git rev-parse --short HEAD)"
git -C "$out" push -q --force "https://github.com/$repo.git" gh-pages
echo "published the gh-pages branch of https://github.com/$repo"
