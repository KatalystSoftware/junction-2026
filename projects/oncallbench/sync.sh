#!/usr/bin/env bash
# The simulator and policies live once in sim/; the images need their own copies.
set -euo pipefail
cd "$(dirname "$0")"
cp sim/incident.py task/environment/mcp-server/incident.py
cp sim/incident.py task/tests/incident.py
cp sim/policies.py task/solution/policies.py
