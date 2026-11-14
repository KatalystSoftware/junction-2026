#!/bin/bash
# Replays the signed action log. The full ledger goes to /logs/verifier/reward.json (Harbor reads it
# first, so every cost component lands in result.json); the score alone goes to reward.txt.
python3 /tests/grade.py /ledger/receipt.json /logs/verifier/reward.json
python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["reward"])' \
  /logs/verifier/reward.json >/logs/verifier/reward.txt
