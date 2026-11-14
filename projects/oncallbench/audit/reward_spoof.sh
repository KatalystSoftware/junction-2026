#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
cp -r runtime/jobs/variants/aq-incident-ec900b74 runtime/reward-spoof-task
rm -rf runtime/reward-spoof-task/solution
mkdir runtime/reward-spoof-task/solution
cp reward_spoof.py runtime/reward-spoof-task/solution/probe.py
cat >runtime/reward-spoof-task/solution/solve.sh <<'EOF'
#!/bin/bash
set -euo pipefail
python3 /solution/probe.py
EOF
UV_PYTHON_PREFERENCE=only-system uvx --from harbor==0.25.0 harbor run \
  -p runtime/reward-spoof-task -o runtime/spoof-jobs --job-name reward-spoof -a oracle --quiet
