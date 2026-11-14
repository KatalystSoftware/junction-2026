"""Byte-identity of the levels that already exist. A new level may not move an old one.

For levels 0-5 it hashes the briefing, every tool reply a few scripted policies and a random
caller get (accepted or rejected), the cost of each shift, and the cost of every stored agent
receipt, and compares the hashes with `parity.json`. The baseline was written once, at 5039701,
before round 12 added a level; a builder never rewrites it.

python3 parity.py            check against parity.json
python3 parity.py --write    write the baseline (only when a level is meant to change)
"""

import argparse
import hashlib
import json
import multiprocessing
import random
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE / "sim"))

import incident  # noqa: E402
import policies  # noqa: E402

LEVELS = [0, 1, 2, 3, 4, 5]
SEEDS = list(range(1, 13)) + list(range(101, 107))
MORE = {4: list(range(3000, 3005))}  # the submitted level, on a few of the validation seeds too
POLICIES = ["reference", "exploiter", "loudest-first", "shotgun", "unprotected", "consumer-fixer"]
JOB = re.compile(r"r\d+-l(\d+)-s(\d+)-")
VALUES = [-1, 0, 1, 2, 5, 12, 40, 90, 500, True, "9", 2.5]


def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()[:16]


def settle(estate, calls):
    estate.finish()
    return digest([calls, estate.total_cost(), estate._cost(), estate.faults])


def play(seed, level, name):
    estate, calls = incident.Estate(seed, level), []

    def call(tool, **args):
        result = estate.call(tool, args)
        calls.append([tool, args, result])
        return result

    policies.POLICIES[name](call)
    return settle(estate, calls)


def noise(seed, level):
    """Random calls, legal and not, with the reply to each one recorded."""
    out = []
    for ep in range(12):
        r = random.Random(f"parity:{seed}:{level}:{ep}")
        estate, calls = incident.Estate(seed, level), []
        names = list(estate.svc) + ["nope", "", None, 3]
        tools = sorted(set(incident.Estate.TOOLS) | {"get_diff", "throttle", "drop_table"})
        for _ in range(r.randint(5, 60)):
            tool = r.choice(tools)
            args = {}
            for key in {"get_diff": ("service", "change_id"), "throttle": ("service", "percent")}.get(
                    tool, incident.Estate.TOOLS.get(tool, ())):
                args[key] = r.choice(names) if key == "service" else r.choice(VALUES)
            if tool == "get_diff" and isinstance(args["service"], str) and args["service"] in estate.svc and r.random() < 0.8:
                ids = [c["id"] for c in estate.svc[args["service"]]["changes"]]
                args["change_id"] = r.choice(ids) if ids else "v1"
            if tool in ("get_metrics", "get_logs") and r.random() < 0.4:
                args["until_minute"] = r.choice([-150, -60, -20, 0, estate.now, estate.now + 5, "x"])
            if tool == "list_alerts" and r.random() < 0.4:
                args["tier"] = r.choice(["edge", "app", "data", "infra", 3])
            if r.random() < 0.03:
                args["extra"] = 1
            calls.append([tool, args, estate.call(tool, args)])
        calls.append(["get_topology", {}, estate.call("get_topology", {})])
        out.append(settle(estate, calls))
    return digest(out)


def one(job):
    seed, level = job
    row = {name: play(seed, level, name) for name in POLICIES}
    row["random"] = noise(seed, level)
    return f"{level}:{seed}", row


def receipts():
    out = {}
    for path in sorted((HERE / "loop-evidence" / "receipts").glob("*.json")):
        job = JOB.match(path.name)
        if not job or int(job[1]) not in LEVELS:
            continue
        try:
            estate = incident.replay(int(job[2]), int(job[1]), json.loads(path.read_text())["actions"])
            out[path.name] = [estate.total_cost(), estate._cost()]
        except Exception as e:  # a receipt that never replayed stays one that does not replay
            out[path.name] = repr(e)
    return out


def snapshot():
    jobs = [(seed, level) for level in LEVELS for seed in SEEDS + MORE.get(level, [])]
    with multiprocessing.Pool(10) as pool:
        shifts = dict(pool.imap_unordered(one, jobs))
    return dict(
        briefing={str(level): digest(incident.briefing(level)) for level in LEVELS},
        submitted=incident.SUBMITTED,
        instruction=digest((HERE / "task" / "instruction.md").read_text()),
        server=digest((HERE / "task" / "environment" / "mcp-server" / "server.py").read_text()),
        shifts={key: shifts[key] for key in sorted(shifts)},
        receipts=receipts(),
    )


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    opts = ap.parse_args()
    now, path = snapshot(), HERE / "parity.json"
    if opts.write:
        path.write_text(json.dumps(now, indent=1, sort_keys=True) + "\n")
        print(f"baseline written: {len(now['shifts'])} shifts, {len(now['receipts'])} receipts")
        sys.exit(0)
    was, bad = json.loads(path.read_text()), []
    for part in ("briefing", "shifts", "receipts"):
        for key in sorted(set(was[part]) | set(now[part])):
            a, b = was[part].get(key), now[part].get(key)
            if a != b:
                moved = sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k)) if isinstance(a, dict) and isinstance(b, dict) else ""
                bad.append(f"{part} {key} {moved}")
    bad += [f"{part} changed" for part in ("submitted", "instruction", "server") if was[part] != now[part]]
    print(f"{len(now['shifts'])} shifts on levels {LEVELS}, {len(now['receipts'])} stored receipts: "
          + ("identical to the baseline" if not bad else f"{len(bad)} DIFFER"))
    for line in bad[:40]:
        print("  " + line)
    sys.exit(1 if bad else 0)
