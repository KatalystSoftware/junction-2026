#!/usr/bin/env bash
# Invoke with nix develop -c bash audit/probe.sh after the captured run.sh made seed 101's variant.
set -euo pipefail
cd "$(dirname "$0")"
cp -r runtime/jobs/variants/aq-incident-ec900b74 runtime/probe-task
rm -rf runtime/probe-task/solution
mkdir runtime/probe-task/solution
cp probe.py runtime/probe-task/solution/probe.py
cat >runtime/probe-task/solution/solve.sh <<'EOF'
#!/bin/bash
set -euo pipefail
python3 /solution/probe.py
EOF
UV_PYTHON_PREFERENCE=only-system uvx --from harbor==0.25.0 harbor run \
  -p runtime/probe-task -o runtime/probe-jobs --job-name boundary-probe -a oracle --quiet
