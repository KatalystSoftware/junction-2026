#!/usr/bin/env bash
# Bring the request cache down from the server into ./api-cache, so the pipeline reruns without keys and
# without paying for a request twice.
#
#   ./fetch-cache.sh
#
# The cache is not in git: it holds the raw text of third-party pages, which names people as news does.
# It lives in three places: this folder on a machine that has run the pipeline, /srv/talent-brief/api-cache
# on the server (the fullest copy, since live searches on the site add to it), and a dated backup outside
# the repository on the machine that built it. This only adds files; it never deletes a local one.
# Needs ssh access to the runner (the key in $VERDA_SSH_KEY, or ~/.ssh/id_ed25519_verda).
set -euo pipefail
cd "$(dirname "$0")"
rsync -az -e "ssh -i ${VERDA_SSH_KEY:-$HOME/.ssh/id_ed25519_verda} -o BatchMode=yes" \
  root@31.22.104.106:/srv/talent-brief/api-cache/ api-cache/
echo "api-cache: $(find api-cache -type f | wc -l) files"
