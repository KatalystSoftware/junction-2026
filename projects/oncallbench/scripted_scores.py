"""Cost and score of every scripted policy on a set of level-4 seeds, for the results table.

    python3 scripted_scores.py 200000-200023 > loop-evidence/common-scripted.json

Deterministic: the same seeds give the same file. Run it on the eval runner, not a shared workstation.
"""

import json
import sys

import eval as ev

first, last = map(int, sys.argv[1].split("-"))
rows = []
for seed in range(first, last + 1):
    r = ev.evaluate(seed, 4)
    rows.append(dict(seed=seed, cost_null=r["cost_null"], cost_ref=r["cost_ref"],
                     cost=r["cost"], score=r["score"]))
json.dump(rows, sys.stdout, indent=1)
print()
