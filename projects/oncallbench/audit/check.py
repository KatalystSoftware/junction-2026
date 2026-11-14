"""Read-only audit using the shipped eval.py; writes only beside this script.

Run with the project's Python: python3 audit/check.py [--root audit/runtime]
"""

import argparse
import hashlib
import importlib.util
import json
import random
import statistics
import subprocess
import tarfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent
FILES = ["README.md", "LOOP.md", "eval.py", "run.sh", "sync.sh"]


def snapshot():
    files = [SOURCE / name for name in FILES]
    files += sorted((SOURCE / "sim").glob("*.py"))
    files += sorted(p for p in (SOURCE / "task").rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    manifest = {str(p.relative_to(SOURCE)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    with tarfile.open(HERE / "source.tar.gz", "w:gz") as archive:
        for path in files:
            archive.add(path, arcname=path.relative_to(SOURCE), recursive=False)
    runtime = HERE / "runtime"
    runtime.mkdir(exist_ok=True)
    with tarfile.open(HERE / "source.tar.gz") as archive:
        archive.extractall(runtime, filter="data")
    provenance = dict(revision=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
                      captured_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), sha256=manifest)
    (HERE / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    return runtime


def load(root):
    spec = importlib.util.spec_from_file_location("audited_eval", root / "eval.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def quantiles(values):
    values = sorted(values)
    def q(p):
        pos = (len(values) - 1) * p
        lower = int(pos)
        return values[lower] + (values[min(lower + 1, len(values) - 1)] - values[lower]) * (pos - lower)
    return dict(min=values[0], p05=q(.05), p25=q(.25), median=q(.5), mean=statistics.mean(values),
                p75=q(.75), p95=q(.95), max=values[-1])


def generality(ev):
    rows = []
    with (HERE / "generality.jsonl").open("w") as output:
        for seed in range(1000, 1200):
            start = time.monotonic()
            row = ev.evaluate(seed, 4)
            row["cost_oracle"] = ev.oracle(seed, 4)
            row["reference_oracle"] = ((row["cost_null"] - row["cost_ref"]) /
                                       (row["cost_null"] - row["cost_oracle"]))
            row["faults"] = ev.incident.Estate(seed, 4).faults
            row["seconds"] = round(time.monotonic() - start, 3)
            output.write(json.dumps(row, sort_keys=True) + "\n")
            output.flush()
            rows.append(row)
            if (seed - 999) % 10 == 0 or row["reference_oracle"] < .75:
                print(f"seed={seed} ratio={row['reference_oracle']:.4f} seconds={row['seconds']}", flush=True)
    summary = dict(n=len(rows), reference_oracle=quantiles([r["reference_oracle"] for r in rows]),
                   below_075=[r["seed"] for r in rows if r["reference_oracle"] < .75],
                   worse_than_nothing=[r["seed"] for r in rows if r["cost_ref"] > r["cost_null"]],
                   policies={name: quantiles([r["score"][name] for r in rows]) for name in ev.policies.POLICIES})
    (HERE / "generality-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    held = [ev.evaluate(seed, 4) for seed in (101, 104, 105)]
    (HERE / "held-out.json").write_text(json.dumps(held, indent=2) + "\n")
    print(json.dumps(summary), flush=True)


def replay(ev, episodes=200):
    """Generate full call streams including rejects, then replay accepted logs and compare bytes."""
    counts = dict(episodes=0, attempted=0, accepted_actions=0, unlogged_successes=0, rejected=0,
                  response_comparisons=0)
    for ep in range(episodes):
        seed = 2000 + ep
        rng = random.Random(f"audit-replay:{seed}")
        estate = ev.incident.Estate(seed, 4)
        fresh = ev.incident.Estate(seed, 4)
        names = list(estate.svc)
        calls = list(estate.TOOLS) + ["unknown"]
        for _ in range(rng.randint(35, 100)):
            tool = rng.choice(calls)
            args = {}
            for key in estate.TOOLS.get(tool, ()):
                if key == "service":
                    args[key] = rng.choice(names + ["missing", None, ["x"], 1])
                elif key == "change_id":
                    args[key] = rng.choice(["v12", "missing", None, 3])
                elif key == "replicas":
                    args[key] = rng.choice([1, 4, 8, 12, 24, 99, True, "3", -1])
                elif key == "percent":
                    args[key] = rng.choice([0, 10, 35, 70, 90, 91, True, "3", -1])
                else:
                    args[key] = rng.choice([1, 2, 5, 12, 120, True, "3", -1])
            if tool in ("get_metrics", "get_logs") and rng.random() < .4:
                args["until_minute"] = rng.choice([-151, -150, -100, 0, estate.now, estate.now + 1, True])
            if tool == "list_alerts" and rng.random() < .4:
                args["tier"] = rng.choice(["app", "data", "edge", "invalid"])
            if rng.random() < .04:
                args["extra"] = 1
            before = len(estate.actions)
            answer = estate.call(tool, args)
            other = fresh.call(tool, json.loads(json.dumps(args)))
            assert json.dumps(answer, sort_keys=True) == json.dumps(other, sort_keys=True), (seed, tool, args)
            counts["response_comparisons"] += 1
            counts["attempted"] += 1
            key = ("accepted_actions" if len(estate.actions) > before else
                   "unlogged_successes" if answer.get("ok") else "rejected")
            counts[key] += 1
        receipt = json.loads(json.dumps(estate.receipt()))
        again = ev.incident.replay(seed, 4, receipt["actions"])
        estate.finish()
        assert again.total_cost() == estate.total_cost(), seed
        assert again._cost() == estate._cost(), seed
        assert again.receipt() == receipt, seed
        assert again.get_status() == estate.get_status(), seed
        counts["episodes"] += 1
    (HERE / "replay.json").write_text(json.dumps(counts, indent=2) + "\n")
    print(json.dumps(counts), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path)
    parser.add_argument("--only", choices=["generality", "replay"])
    args = parser.parse_args()
    root = args.root or snapshot()
    ev = load(root)
    if args.only != "generality":
        replay(ev)
    if args.only != "replay":
        generality(ev)
