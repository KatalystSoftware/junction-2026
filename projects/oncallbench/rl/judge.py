"""Tabulate Harbor trials of the judge-style runs (judge.sh): score, wasted mitigations, faults left,
whether each rollback or restart on a service whose callers retry was protected first, how the shift
ended, and harness errors. Each trial's signed action log is replayed in its variant's simulator.

    python3 judge.py <job dir>... [--md]
"""

import json
import math
import sys
from pathlib import Path

DISRUPTIVE = ("rollback", "restart")


def variant_sim(trial):
    """The simulator, seed and level of the variant a trial ran."""
    cfg = json.loads((trial / "config.json").read_text())
    task = Path(cfg["task"]["path"]) if "task" in cfg and "path" in cfg["task"] else None
    if task is None or not task.exists():
        raise FileNotFoundError(f"{trial}: task path not found in config.json")
    server = (task / "environment" / "mcp-server" / "server.py").read_text()
    seed = int(next(line for line in server.splitlines() if line.startswith("SEED")).split("=")[1])
    level = int(next(line for line in server.splitlines() if line.startswith("LEVEL")).split("=")[1])
    return task / "environment" / "mcp-server", seed, level


def analyse(trial):
    trial = Path(trial)
    result = json.loads((trial / "result.json").read_text())
    rewards = (result.get("verifier_result") or {}).get("rewards") or {}
    exc = (result.get("exception_info") or {}).get("exception_type")
    receipt = trial / "artifacts" / "ledger" / "receipt.json"
    actions = json.loads(receipt.read_text())["actions"] if receipt.exists() else []
    simdir, seed, level = variant_sim(trial)
    sys.path.insert(0, str(simdir))
    import incident  # noqa: E402  (the variant's own copy)

    estate = incident.Estate(seed, level)
    protected, unprotected = [], []
    guard = {}  # service -> minute a scale above normal or a throttle was started
    for tool, args in actions:
        svc = args.get("service")
        if tool == "scale" and svc in estate.svc and args.get("replicas", 0) > estate.svc[svc]["replicas"]:
            guard[svc] = estate.now
        elif tool == "throttle" and args.get("percent", 0) > 0:
            guard[svc] = estate.now
        elif tool in ("scale", "throttle"):
            guard.pop(svc, None)
        if tool in DISRUPTIVE and svc in estate.svc and estate.svc[svc].get("retry"):
            (protected if svc in guard else unprotected).append(f"{tool} {svc}@{estate.now}")
        estate.call(tool, args)
    clock = estate.now
    if actions and actions[-1][0] == "finish":
        ended = "finish"
    elif clock >= incident.HORIZON:
        ended = "shift end"
    elif exc and "Timeout" in exc:
        ended = f"timeout at minute {clock}"
    else:
        ended = f"agent stopped at minute {clock}"
    sys.path.remove(str(simdir))
    del sys.modules["incident"]
    return dict(task=simdir.parent.parent.name, trial=trial.name, seed=seed, level=level, score=rewards.get("reward"),
                wasted=round((rewards.get("cost_wasted") or 0) / incident.LEVELS[level]["wasted"]),
                faults_left=rewards.get("faults_left"), actions=len(actions), protected=protected,
                unprotected=unprotected, ended=ended, harness_error=exc)


def main(paths, md=False):
    rows = []
    for job in map(Path, paths):
        for trial in sorted(p for p in job.iterdir() if p.is_dir() and (p / "result.json").exists()):
            rows.append(dict(job=job.name, **analyse(trial)))
    for r in rows:
        prot = (f"{len(r['protected'])} of {len(r['protected']) + len(r['unprotected'])}"
                if r["protected"] or r["unprotected"] else "none needed")
        if md:
            print(f"| {r['job']} | {r['seed']} | {r['score']} | {r['wasted']} | {r['faults_left']} | {prot} | "
                  f"{r['ended']} | {r['actions']} | {r['harness_error'] or ''} |")
        else:
            print(json.dumps(r))
    by = {}
    for r in rows:
        by.setdefault(r["job"].removesuffix("-" + r["task"]), []).append(r)  # judge.sh: <prefix>-<base|sft>
    for name, rs in by.items():
        s = [r["score"] or 0.0 for r in rs]
        mean = sum(s) / len(s)
        se = math.sqrt(sum((x - mean) ** 2 for x in s) / max(1, len(s) - 1) / len(s))
        print(f"{name}: n={len(s)} mean={mean:.3f} se={se:.3f} scores={[round(x, 3) for x in s]}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--md"]
    main(args, "--md" in sys.argv)
