"""Append one record per finished Harbor trial to metrics.json. Trials already recorded are kept
as they are, so a failure category written by hand survives.

python3 collect.py [commit]
"""

import fcntl
import json
import re
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent
METRICS = HERE / "metrics.json"
JOB = re.compile(r"r(\d+)-l(\d+)-s(\d+)-(.+)-\d{6}$")


def record(result_path, commit):
    job = JOB.match(result_path.parent.parent.name)
    if not job:
        return None
    d = json.loads(result_path.read_text())
    rewards = (d.get("verifier_result") or {}).get("rewards") or {}
    if "reward" not in rewards:
        return None
    agent = d.get("agent_result") or {}
    took = datetime.fromisoformat(d["finished_at"]) - datetime.fromisoformat(d["started_at"])
    return dict(
        round=int(job[1]), commit=commit, level=int(job[2]), seed=int(job[3]), run=job[4],
        score=round(rewards["reward"], 4), cost_usd=round(agent.get("cost_usd") or 0.0, 4),
        duration_s=round(took.total_seconds()), failure="",
        trial=f"{result_path.parent.parent.name}/{d['trial_name']}",
        sim_cost=rewards.get("cost_total"), faults_left=rewards.get("faults_left"),
        wasted=rewards.get("cost_wasted"), actions=rewards.get("actions"),
    )


if __name__ == "__main__":
    commit = sys.argv[1] if len(sys.argv) > 1 else ""
    with open(HERE / ".metrics.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        rows = json.loads(METRICS.read_text()) if METRICS.exists() else []
        seen = {r["trial"] for r in rows}
        for path in sorted(HERE.glob("jobs/r*/*/result.json")):
            row = record(path, commit)
            if row and row["trial"] not in seen:
                rows.append(row)
                print(json.dumps(row))
        rows.sort(key=lambda r: (r["round"], r["trial"]))
        METRICS.write_text("[\n" + ",\n".join(json.dumps(r) for r in rows) + "\n]\n")
    spent = sum(r["cost_usd"] for r in rows)
    print(f"{len(rows)} records, ${spent:.2f} of agent runs so far", file=sys.stderr)
