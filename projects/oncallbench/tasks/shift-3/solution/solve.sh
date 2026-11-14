#!/bin/bash
# Scripted policies, calling the MCP tools over plain HTTP. POLICY selects one:
#   reference (default)  triage down the dependency graph, mitigate every cause
#   one-fix              mitigates the first cause it finds, then ends the shift
#   stop-early           looks at the dashboards, then ends the shift
#   exploiter            every mitigation on everything that fires
#   no-late              the reference, but leaves once the edge is healthy
#   loudest-first        treats the loudest alert where it shows, one at a time
#   thorough             the reference, but reads everything before each mitigation
#   trusting             the reference, but believes a service's own telemetry over its callers
#   alerts-only          the reference without the descent from a failing edge
set -euo pipefail
python3 "$(dirname "$0")/policies.py" "${POLICY:-reference}" http://mcp-server:8000/mcp
