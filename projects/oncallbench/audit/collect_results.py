"""Collect compact Harbor evidence and compare each verifier ledger to shipped eval.run."""

import json
import shutil
from check import HERE, load

ev = load(HERE / "runtime")
output = HERE / "evidence"
output.mkdir(exist_ok=True)
expected = {}
rows = []
for job in sorted((HERE / "runtime/jobs").glob("audit-r*-l4-s*")):
    bits = job.name.split("-")
    repeat, seed = int(bits[1][1:]), int(bits[3][1:])
    policy = "-".join(bits[4:-1])
    key = (seed, policy)
    if key not in expected:
        estate = ev.run(seed, 4, "nothing" if policy == "nop" else policy)
        null = ev.run(seed, 4, "nothing").total_cost()
        ref = ev.run(seed, 4, "reference").total_cost()
        expected[key] = dict(cost=estate.total_cost(), score=ev.incident.score(estate.total_cost(), null, ref),
                             components=estate._cost(), actions=len(estate.actions))
    trials = [p for p in job.iterdir() if p.is_dir() and (p / "config.json").exists()]
    if len(trials) != 1:
        raise RuntimeError(f"Unexpected trial count in {job}: {len(trials)}")
    trial = trials[0]
    result = json.loads((trial / "result.json").read_text())
    ledger_path = trial / "verifier/reward.json"
    ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() else None
    reference = expected[key]
    row = dict(job=job.name, repeat=repeat, seed=seed, policy=policy, expected=reference, actual=ledger,
               exception_info=result.get("exception_info"),
               cost_matches=bool(ledger and ledger["cost_total"] == reference["cost"]),
               score_matches=bool(ledger and ledger["reward"] == reference["score"]),
               receipt_matches=False)
    receipt = json.loads((trial / "artifacts/ledger/receipt.json").read_text())
    direct = ev.run(seed, 4, "nothing" if policy == "nop" else policy)
    row["receipt_matches"] = direct.receipt() == receipt
    row["timing"] = {name: result.get(name) for name in ("started_at", "finished_at", "environment_setup", "agent_execution", "verifier")}
    rows.append(row)
    (output / (job.name + ".json")).write_text(json.dumps(row, indent=2) + "\n")
    if row["exception_info"]:
        shutil.copyfile(trial / "trial.log", output / (job.name + ".log"))

probe_job = HERE / "runtime/probe-jobs/boundary-probe"
probe_trial = next(p for p in probe_job.iterdir() if p.is_dir() and (p / "config.json").exists())
shutil.copyfile(probe_trial / "agent/oracle.txt", HERE / "probe-results.jsonl")
shutil.copyfile(probe_trial / "verifier/reward.json", HERE / "probe-reward.json")
bare_job = HERE / "runtime/bare-jobs/bare-task-nop"
bare_trial = next(p for p in bare_job.iterdir() if p.is_dir() and (p / "config.json").exists())
for source, dest in (("verifier/test-stdout.txt", "bare-verifier.txt"),
                     ("result.json", "bare-result.json")):
    shutil.copyfile(bare_trial / source, output / dest)
spoof_job = HERE / "runtime/spoof-jobs/reward-spoof"
spoof_trial = next(p for p in spoof_job.iterdir() if p.is_dir() and (p / "config.json").exists())
shutil.copyfile(spoof_trial / "verifier/reward.json", HERE / "spoof-reward.json")
shutil.copyfile(spoof_trial / "agent/oracle.txt", HERE / "spoof-agent.txt")
summary = dict(trials=len(rows), cost_mismatches=[r["job"] for r in rows if not r["cost_matches"]],
               score_mismatches=[r["job"] for r in rows if not r["score_matches"]],
               receipt_mismatches=[r["job"] for r in rows if not r["receipt_matches"]],
               errors=[r for r in rows if r["exception_info"]], rows=rows)
(HERE / "harbor-results.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps({k: v for k, v in summary.items() if k != "rows"}))
