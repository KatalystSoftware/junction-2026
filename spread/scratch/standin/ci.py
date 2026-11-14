"""One design of the stand-in, fitted and checked on a CI runner: fits the drivers on the weeks outside the held-out seeds, then scores the
stand-in on the played paired checks of the held-out seeds (spreadlab/standin/validate.py). Offline: it reads packed weeks only.

    python3 scratch/standin/ci.py <design name> <out folder> [jobs]

A design is an entry of designs.json: the features to leave out of the fit (`drop`) and the world's options (`design`, world.DESIGN).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
name, out, jobs = sys.argv[1], Path(sys.argv[2]), sys.argv[3] if len(sys.argv) > 3 else str(os.cpu_count())
design = next(d for d in json.loads((HERE / "designs.json").read_text()) if d["name"] == name)
out.mkdir(parents=True, exist_ok=True)
weights = out / f"weights-{name}.json"
py = [sys.executable, "-m"]
hold = design.get("hold_out", "fresh-")
subprocess.run(py + ["spreadlab.standin.fit", "--out", str(weights), "--hold-out", hold, "--drop", ",".join(design.get("drop", [])), "--jobs", jobs,
                     "--limit", str(design.get("limit", 0)), "--variants", design.get("variants", "")], check=True, cwd=HERE.parents[1])
for baseline in design.get("baselines", ["steep-notes-offers-8", "slow-friday-late-150-kinds-limits"]):
    with open(out / f"report-{name}-{baseline}.txt", "w") as report:
        done = subprocess.run(py + ["spreadlab.standin.validate", "--baselines", baseline, "--seeds", hold, "--weights", str(weights), "--design", json.dumps(design.get("design", {})),
                                    "--jobs", jobs, "--draws", str(design.get("draws", 1)), "--most", str(design.get("most", 40)), "--arms", ",".join(design.get("arms", [])), "--out", str(out / f"result-{name}-{baseline}.json")],
                              cwd=HERE.parents[1], stdout=subprocess.PIPE, text=True, check=True)
        report.write(done.stdout)
        print(done.stdout[-3500:], flush=True)
