"""Shortcut policies that skip diagnosis, scored next to the reference on the same seeds.

Each sees only what an agent sees: `call(tool, **args) -> dict`. None reads a log or a diff.

python3 redteam/blind.py [--seeds 101,102,103] [--level 4]
"""

import argparse
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "sim"))

import incident  # noqa: E402
import policies  # noqa: E402


def _topo(call):
    topo = {s["name"]: s for s in call("get_topology")["services"]}
    deps = {n: [(d["service"], 1.0 if d["kind"] == "hard" else 0.3) for d in s["depends_on"]] for n, s in topo.items()}
    return topo, deps


def _under(deps, n):
    return {x for d, _ in deps[n] for x in {d} | _under(deps, d)}


def _protected(call, topo, service, tool):
    """Capacity first where callers retry (scale is never fined), the undo, capacity given back."""
    normal, retry = topo[service]["normal_replicas"], topo[service].get("callers_retry", 0)
    if retry:
        call("scale", service=service, replicas=min(4 * normal, math.ceil(normal * (1 + retry * 0.3 * 1.15))))
        call("wait", minutes=4)
    result = call(tool, service=service)
    if retry:
        if result.get("ok"):
            call("wait", minutes=max(1, result["completes_at_minute"] - result["minute"]))
        call("scale", service=service, replicas=normal)
    return result


def alert_undo(call):
    """Every app service whose error alert its dependencies do not explain gets a protected rollback,
    or a config revert if it has no live deploy; CPU alerts get double capacity. Never reads."""
    topo, deps = _topo(call)
    treated = set()
    while not call("get_status")["shift_over"]:
        alerts = []
        for tier in ("app", "data"):
            alerts += call("list_alerts", tier=tier).get("alerts", [])
        err = {a["service"]: a["value"] for a in alerts if a["signal"] == "error_rate"}
        for a in alerts:
            n = a["service"]
            if n in treated or topo[n]["tier"] == "external":
                continue
            up = 1.0
            for d, w in deps[n]:
                up *= 1 - w * err.get(d, 0)
            own = 1 - (1 - err.get(n, 0)) / up if up > 0.02 else 0
            if a["signal"] == "cpu" and n not in err:
                treated.add(n)
                call("scale", service=n, replicas=2 * topo[n]["normal_replicas"])
            elif a["signal"] == "error_rate" and own >= 0.06:
                treated.add(n)
                if not _protected(call, topo, n, "rollback").get("ok"):
                    call("revert_config", service=n)
        if call("get_status")["shift_over"]:
            return
        call("wait", minutes=3)


def rich_guess(call):
    """alert_undo, plus the quiet fault guessed by recency: every app service under the richest edge
    whose latest live change is under 90 minutes old gets a protected rollback, then a config revert."""
    topo, deps = _topo(call)
    rich = max((n for n in topo if topo[n]["tier"] == "edge"), key=lambda n: topo[n]["revenue_per_min"])
    for n in sorted(_under(deps, rich)):
        if topo[n]["tier"] != "app":
            continue
        live = [c for c in call("get_changes", service=n).get("changes", []) if c["status"] == "live"]
        if live and live[-1]["minute"] >= -90:
            if not _protected(call, topo, n, "rollback").get("ok"):
                call("revert_config", service=n)
    alert_undo(call)


def scale_all(call):
    """Capacity everywhere callers retry, held all shift (scale is never fined), then alert_undo."""
    topo, _ = _topo(call)
    for n in sorted(topo, key=lambda n: -topo[n].get("callers_retry", 0)):
        if topo[n].get("callers_retry") and topo[n]["tier"] != "external":
            call("scale", service=n, replicas=2 * topo[n]["normal_replicas"])
    alert_undo(call)


SHORTCUTS = {"alert-undo": alert_undo, "rich-guess": rich_guess, "scale-all": scale_all}


def play(seed, level, policy):
    estate = incident.Estate(seed, level)
    policy(lambda tool, **args: estate.call(tool, args))
    actions = [list(a) for a in estate.actions]
    return incident.replay(seed, level, actions).total_cost()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="101,102,103")
    ap.add_argument("--level", type=int, default=4)
    opts = ap.parse_args()
    for seed in map(int, opts.seeds.split(",")):
        null, ref = play(seed, opts.level, policies.nothing), play(seed, opts.level, policies.reference)
        scores = {name: incident.score(play(seed, opts.level, p), null, ref) for name, p in SHORTCUTS.items()}
        print(f"seed {seed}  reference 1.00  " + "  ".join(f"{k} {v:.2f}" for k, v in scores.items()), flush=True)
