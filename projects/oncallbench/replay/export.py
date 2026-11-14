"""Export on-call shifts as per-minute data for the replay viewer (index.html).

A shift is fully determined by (seed, level, action log), so every run here is a replay in the
simulator: a scripted policy played in-process, or the signed action log of a Harbor trial. The
simulator is imported read-only from ../sim; nothing in it is changed.

Each episode (one level and seed) is one bundle, data/l<level>-s<seed>.js, and data/index.js lists
the bundles for the page. A bundle keeps the action logs of its trials, so it can be exported again
without the Harbor folders they came from.

python3 export.py                                   every bundle in data/ again, with this simulator
python3 export.py --level 4 --seeds 109 --jobs ../jobs   add or replace one episode, with its trials
python3 export.py --level 5 --seeds 109,110 --policies reference,unprotected,nothing
python3 export.py --level 4 --seeds 109 --out shift.json  plain JSON, no bundle

A bundle is an answer key: it holds the faults of its seed and every call of the reference. The
seeds of the shipped tasks (../tasks) are never exported, at any level, to a bundle or a file.
"""

import argparse
import hashlib
import importlib.util
import itertools
import json
import math
import re
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
PRE = 30  # minutes before the page that the viewer can scrub back to (not charged)
DEFAULT_SEED = 109  # a fresh seed no shipped task uses
# A bundle is an answer key: the faults, and the reference's calls that fix them. The judged tasks run
# on these seeds, and an agent in the task's container can reach a public site, so they are never
# exported. Levels share a seed's estate and most of its faults, so the rule holds at every level.
SHIPPED = {101, 102, 103}


def shipped_seeds():
    """The seeds no bundle may be made for: the fixed list, and whatever ../tasks ships today."""
    found = set(SHIPPED)
    for server in (HERE.parent / "tasks").glob("*/environment/mcp-server/server.py"):
        found |= {int(m) for m in re.findall(r"^SEED = (\d+)", server.read_text(), re.M)}
    return found
POLICIES = ["unprotected", "no-drain", "forgetful", "loudest-first", "alerts-only", "no-late", "nothing"]
POLICY_LABELS = {
    "reference": "Scripted reference", "nothing": "Do nothing", "stop-early": "Stop early",
    "loudest-first": "Loudest first", "alerts-only": "Alerts only", "no-late": "Leaves early",
    "trusting": "Trusts own telemetry", "shotgun": "Tries every mitigation", "thorough": "Reads everything",
    "one-fix": "One fix, then leaves", "exploiter": "Exploiter", "no-drain": "Never drains a storm",
    "unprotected": "Unprotected rollbacks", "forgetful": "Never lifts a throttle",
}
MODELS = {
    "claude-fable-5-2": "Claude Fable 5.2", "claude-opus-5-5": "Claude Opus 5.5", "claude-sonnet-5-5": "Claude Sonnet 5.5",
    "gemini-3.1-pro-preview": "Gemini 3.1 Pro",
    # served from Modal by ../rl/modal_serve.py; the adapter is ../rl/RESULTS.md's SFT adapter
    "gemma26-base": "Gemma 4 26B-A4B (untrained)", "gemma26-sft": "Gemma 4 26B-A4B + our SFT adapter",
}
FAULT_LABELS = {
    "bad_deploy": "bad deploy", "bad_config": "bad config", "leak": "memory leak",
    "overload": "traffic surge", "primary_down": "primary node down",
}
FAULT_FIX = {
    "bad_deploy": "rollback", "bad_config": "revert_config", "leak": "rollback", "overload": "scale",
    "primary_down": "failover",
}


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# --- playing a run ------------------------------------------------------------------


def play(incident, seed, level, drive):
    """Run `drive(call)` on a fresh estate and settle. Returns the estate and one record per
    accepted call: when it was made, what it returned, and what it did to the faults."""
    estate, log = incident.Estate(seed, level), []

    def call(tool, args=None):
        args = dict(args or {})
        before = dict(now=estate.now, wasted=estate.wasted, n=len(estate.actions),
                      ends=[f["end"] for f in estate.faults])
        result = estate.call(tool, args)
        if len(estate.actions) > before["n"]:
            log.append(dict(
                tool=tool, args=args, t0=before["now"], t1=estate.now, result=result,
                wasted=estate.wasted - before["wasted"],
                fixed=[i for i, f in enumerate(estate.faults) if before["ends"][i] is None and f["end"] is not None]))
        return result

    drive(call)
    estate.finish()
    return estate, log


def pressure(incident, estate, name, t):
    """Traffic over what the replicas serve at minute t: as it arrives (retries added, a throttle
    taken off the top), and from customers alone. Above 1 the service sheds load."""
    cap = estate.svc[name].get("cap", incident.HEADROOM)
    alone = estate._load(name, t) * estate.svc[name]["replicas"] / (estate._replicas(name, t) * cap)
    return (estate._state(t)[name][2] if getattr(estate, "storms", False) else alone), alone


def spans(flags, first):
    """[[from, to), ...] of the true runs in a per-minute list that starts at minute `first`."""
    out = []
    for i, on in enumerate(flags):
        if on and (not out or out[-1][1] != first + i):
            out.append([first + i, first + i + 1])
        elif on:
            out[-1][1] = first + i + 1
    return out


def trim(tool, result):
    """What the agent saw, minus the bulk the viewer has no room for."""
    if tool == "get_topology":
        tiers = {}
        for s in result["services"]:
            tiers[s["tier"]] = tiers.get(s["tier"], 0) + 1
        return dict(ok=True, minute=result.get("minute"), services=tiers)
    return result


def record(incident, estate, log, index):
    """One run as the viewer reads it: per-minute error rates and costs, fault, storm and throttle
    spans, and the actions."""
    horizon, minutes = incident.HORIZON, range(-PRE, incident.HORIZON)
    surge = {f["service"]: f["start"] for f in estate.faults if f["kind"] == "overload"}

    def surging(n, t):  # more customer traffic than the replicas serve: the overload fault itself
        return n in surge and surge[n] <= t and pressure(incident, estate, n, t)[1] > 1 + 1e-9

    err, hot, storm, loss, extra = [], [], [], [], []
    for t in minutes:
        e = estate._err(t)
        err.append([[index[n], round(e[n] * 1e4), round(estate._own(n, t) * 1e4)]
                    for n in estate.order if e[n] >= 5e-4])
        hot.append([index[n] for n in estate.order if estate._metrics(n, t)["cpu"] >= incident.ALERT_SAT])
        # over capacity on retries alone: a storm, which no fault explains and no fix ends
        storm.append([index[n] for n in estate.order
                      if pressure(incident, estate, n, t)[0] > 1 + 1e-9 and not surging(n, t)])
        loss.append(round(sum(estate.svc[n]["revenue"] * e[n] for n in estate.edges), 2))
        extra.append(incident.REPLICA_COST * sum(
            max(0, estate._replicas(n, t) - estate.svc[n]["replicas"]) for n in estate.scales) if t >= 0 else 0)
    cost = estate._cost()
    assert abs(sum(loss[PRE:]) - cost["outage"]) < 1, "per-minute losses do not add up to the settled outage cost"
    assert sum(extra) == cost["replicas"] and sum(a["wasted"] for a in log) == cost["wasted"]

    faults = []
    for f in estate.faults:
        if f["kind"] == "overload":
            live = [surging(f["service"], t) for t in minutes]
        else:
            live = [estate._fault_sev(f, t) > 0 for t in minutes]
        faults.append(dict(live=spans(live, -PRE), cleared=None if live[-1] else max(
            [t + 1 for t, on in zip(minutes, live) if on] or [f["start"]])))

    throttles = []  # what the run rejected up front, and for how long
    for name, steps in getattr(estate, "throttles", {}).items():
        for (at, share), nxt in zip(steps, steps[1:] + [(horizon, 0)]):
            if share and nxt[0] > at:
                throttles.append(dict(service=index[name], percent=round(100 * share), span=[at, min(nxt[0], horizon)]))

    actions = []
    for a in log:
        tool = a["tool"]
        kind = ("mitigation" if tool in incident.MITIGATIONS else "query" if tool in estate.QUERIES | {"get_topology"}
                else tool if tool in ("wait", "finish", "throttle") else "other")
        act = dict(tool=tool, args=a["args"], kind=kind, t0=a["t0"], t1=a["t1"], result=trim(tool, a["result"]))
        if "service" in a["args"]:
            act["service"] = index[a["args"]["service"]]
        if kind == "mitigation":
            normal = estate.svc[a["args"]["service"]]["replicas"]
            act.update(lands=a["result"]["completes_at_minute"], wasted=a["wasted"], fixed=a["fixed"], effect=(
                "wasted" if a["wasted"] else "fix" if a["fixed"] else
                "undo" if tool == "scale" and a["args"]["replicas"] == normal else
                "fix" if tool == "scale" else "relief"))
        if kind == "throttle":  # in force from the next minute until the next throttle call on the service
            start = a["result"]["effective_at_minute"]
            later = [at for at, _ in estate.throttles[a["args"]["service"]] if at > start]
            act.update(percent=a["args"]["percent"], span=[start, min(later[0] if later else horizon, horizon)])
        actions.append(act)
    return dict(cost=dict(cost, total=estate.total_cost()), err=err, hot=hot, storm=storm, loss=loss, extra=extra,
                faults=faults, throttles=sorted(throttles, key=lambda s: (s["span"], s["service"])),
                actions=actions, horizon=horizon)


# --- the graph ----------------------------------------------------------------------


def layout(svc, edges):
    """Rows and x positions (0..1) for a layered drawing: edge services on top, app services by
    their longest call path from an edge, data services at the bottom. Services no edge reaches
    are `orphan`: they carry no customer traffic and the viewer sets them aside."""
    names = list(svc)
    callers = {n: [] for n in names}
    for n in names:
        for d, _ in svc[n]["deps"]:
            callers[d].append(n)
    depth = {e: 0 for e in edges}

    def reach(n):
        if n not in depth:
            above = [reach(c) for c in callers[n]]
            above = [d for d in above if d is not None]
            depth[n] = 1 + max(above) if above else None
        return depth[n]

    for n in names:
        reach(n)
    last = 1 + max(d for n, d in depth.items() if d is not None and svc[n]["tier"] == "app")
    row = {n: (None if depth[n] is None else last if svc[n]["tier"] == "data" else depth[n]) for n in names}
    on = [n for n in names if row[n] is not None]
    links = [(n, d) for n in on for d, _ in svc[n]["deps"]]  # caller above, dependency below
    near = {n: [] for n in on}
    for a, b in links:
        near[a].append(b)
        near[b].append(a)

    def order_rows(top):
        rows = [[] for _ in range(last + 1)]
        for n in on:
            rows[row[n]].append(n)
        rows[0] = list(top)
        pos = {}

        def place():
            for r in rows:
                for i, n in enumerate(r):
                    pos[n] = (i + 0.5) / len(r)

        place()
        for sweep in range(8):
            for i in (range(1, last + 1) if sweep % 2 == 0 else range(last - 1, 0, -1)):
                side = (lambda m: row[m] < i) if sweep % 2 == 0 else (lambda m: row[m] > i)

                def bary(n):
                    xs = [pos[m] for m in near[n] if side(m)] or [pos[m] for m in near[n]]
                    return sum(xs) / len(xs) if xs else pos[n]

                rows[i].sort(key=lambda n: (bary(n), n))
                place()
        return rows, pos

    def crossings(pos):
        segs = [(row[a], pos[a], row[b], pos[b]) for a, b in links]
        count = 0
        for (r1, x1, r2, x2), (r3, x3, r4, x4) in itertools.combinations(segs, 2):
            lo, hi = max(r1, r3), min(r2, r4)
            if lo >= hi:
                continue

            def at(r, ra, xa, rb, xb):
                return xa + (xb - xa) * (r - ra) / (rb - ra)

            if (at(lo, r1, x1, r2, x2) - at(lo, r3, x3, r4, x4)) * (at(hi, r1, x1, r2, x2) - at(hi, r3, x3, r4, x4)) < 0:
                count += 1
        return count

    best = None
    for top in itertools.islice(itertools.permutations(edges), 720):
        rows, pos = order_rows(top)
        score = crossings(pos)
        if best is None or score < best[0]:
            best = (score, rows)
    rows = best[1]

    # edge services are drawn as bars whose width grows with the revenue they earn
    size = {e: svc[e]["revenue"] ** 0.5 for e in rows[0]}
    share = {e: max(0.14, s / sum(size.values())) for e, s in size.items()}
    share = {e: s / sum(share.values()) for e, s in share.items()}
    x, at = {}, 0.0
    for e in rows[0]:
        x[e] = at + share[e] / 2
        at += share[e]
    widest = max(len(r) for r in rows[1:])
    gap, margin = 1 / (widest + 0.5), 0.5 / (widest + 0.5)
    for r in rows[1:]:
        for i, n in enumerate(r):
            x[n] = (i + 0.5) / len(r)
    for _ in range(60):  # pull each service under its callers and over its dependencies, keeping the order
        for r in rows[1:]:
            want = [sum(x[m] for m in near[n]) / len(near[n]) for n in r]
            left, right = list(want), list(want)
            for i in range(len(r)):
                left[i] = max(want[i], margin if i == 0 else left[i - 1] + gap)
            for i in reversed(range(len(r))):
                right[i] = min(want[i], 1 - margin if i == len(r) - 1 else right[i + 1] - gap)
            for i, n in enumerate(r):
                x[n] = min(max((left[i] + right[i]) / 2, margin + i * gap), 1 - margin - (len(r) - 1 - i) * gap)
    orphans = sorted((n for n in names if row[n] is None), key=lambda n: (svc[n]["tier"] != "app", n))
    return {n: dict(row=row[n], x=None if row[n] is None else round(x[n], 4),
                    **({"w": round(share[n], 4)} if n in share else {}),
                    **({"slot": orphans.index(n)} if row[n] is None else {})) for n in names}, last + 1


# --- trials -------------------------------------------------------------------------


def variants(incident):
    """run.sh names each task copy by a hash of its level and seed; invert it."""
    return {hashlib.sha1(f"{level}-{seed}\n".encode()).hexdigest()[:8]: (level, seed)
            for level in incident.LEVELS for seed in range(2000)}


def episode_of(path, config):
    """The level and seed of a trial run from an exported task (../export-tasks.sh writes
    tasks-custom/seed-<seed>, with SEED and LEVEL in its MCP server): read from the task the trial
    ran, which sits next to the jobs folder, else from the job's name (r<round>-l<level>-s<seed>-...)."""
    seed = int(re.match(r"seed-(\d+)__", path.name)[1])
    task = path.parents[2] / config.get("task", {}).get("path", "-") / "environment/mcp-server/server.py"
    if task.exists():
        found = dict(re.findall(r"^(SEED|LEVEL) = (\d+)", task.read_text(), re.M))
        if int(found.get("SEED", -1)) == seed and "LEVEL" in found:
            return int(found["LEVEL"]), seed
    named = re.search(r"-l(\d+)-s(\d+)-", path.parent.name)
    if named and int(named[2]) == seed:
        return int(named[1]), seed
    return None


def read_trial(incident, path, known):
    """A Harbor trial folder -> its episode, action log and, where the agent kept a trajectory,
    what it said around each call. None when the folder is not a finished trial of this task."""
    path = Path(path)
    receipt, config = path / "artifacts/ledger/receipt.json", path / "config.json"
    variant = re.match(r"aq-incident-([0-9a-f]{8})__", path.name)
    if not (receipt.exists() and config.exists()):
        return None
    if variant and variant[1] in known:  # run.sh's task copies are named by a hash of level and seed
        level, seed = known[variant[1]]
    elif re.match(r"seed-\d+__", path.name) and episode_of(path, json.loads(config.read_text())):
        level, seed = episode_of(path, json.loads(config.read_text()))
    else:
        return None
    receipt, agent = json.loads(receipt.read_text()), json.loads(config.read_text())["agent"]
    if receipt.get("sig") != incident.sign(receipt["actions"]):
        print(f"skipped {path.parent.name}: the receipt's signature does not match", file=sys.stderr)
        return None
    model = (agent.get("model_name") or "").split("/")[-1]
    several = len([p for p in path.parent.iterdir() if p.is_dir() and "__" in p.name]) > 1  # several attempts
    name = f"{path.parent.name}-{path.name.split('__')[-1]}" if several else path.parent.name
    trial = dict(seed=seed, level=level, actions=receipt["actions"], id=name, scripted=not model,
                 label=MODELS.get(model, model) or POLICY_LABELS.get(agent.get("env", {}).get("POLICY"), agent["name"]),
                 words=[None] * len(receipt["actions"]), report=None, reward=None)
    reward = path / "verifier/reward.json"
    if reward.exists():
        trial["reward"] = json.loads(reward.read_text())
    trajectory = path / "agent/trajectory.json"
    if trajectory.exists():
        calls = []  # every tool call the agent made, in order, with what it wrote in that turn
        steps = [s for s in json.loads(trajectory.read_text())["steps"] if s.get("source") == "agent"]
        for s in steps:
            said = dict(say=(s.get("message") or "").strip(), think=(s.get("reasoning_content") or "").strip())
            for c in s.get("tool_calls") or []:
                calls.append((c["function_name"].split("_", 1)[-1] if c["function_name"].startswith("ops_")
                              else c["function_name"], c.get("arguments") or {}, said))
        at = 0
        for i, (tool, args) in enumerate(receipt["actions"]):  # the receipt holds the accepted calls only
            for j in range(at, len(calls)):
                if calls[j][0] == tool and calls[j][1] == args:
                    trial["words"][i], at = calls[j][2], j + 1
                    break
        if steps and not steps[-1].get("tool_calls"):
            trial["report"] = (steps[-1].get("message") or "").strip() or None
    return trial


# --- why the reference acts -----------------------------------------------------------

# The reference's runbook, as the page shows it; the numbers tag each of its calls.
RUNBOOK = [
    ("map", "revenue per edge, who calls whom, whose callers retry"),
    ("separate", "causes from failures passed up: a cause fails more than its dependencies explain"),
    ("chase", "quiet customer errors down every upstream log line, largest first"),
    ("prove", "the cause from its log and the change's own diff; undo nothing unread"),
    ("compare", "fresh traffic (requests minus retries) with the calm window before onset: a surge gets replicas, a storm gets drained"),
    ("protect", "a busy service whose callers retry before a disruptive fix: capacity first, or a throttle if cheaper"),
    ("give back", "lift throttles, return replicas, check customers, stay on shift to the last minute"),
]
ACTS = ("rollback", "revert_config", "restart", "scale", "failover", "throttle")
UNDO = {"rollback": "roll back", "revert_config": "revert"}
NOUN = {"rollback": "rollback", "revert_config": "config revert", "restart": "restart", "failover": "failover",
        "scale": "scale"}


def explain(policies, estate, log):
    """Why the reference made each call: the runbook rule, and for a mitigation the numbers behind
    it. Worked out here from its own calls and what they returned, with the same arithmetic as
    sim/policies.py; the reference itself is not touched. A reason is kept only when it reproduces
    the call that was made (the replica count, the throttle share, a word the diff and the symptom
    share). Otherwise the entry has a rule at most, and the page shows the plain action."""
    svc, upstream = estate.svc, getattr(policies, "UPSTREAM", re.compile(r"upstream call to (\S+) failed \((.*)\)"))
    disrupts = getattr(policies, "DISRUPTS", {})
    out = [None] * len(log)

    def on(a, service):
        return a["args"].get("service") == service

    def acted_before(i, service):  # index of the reference's last mitigation or throttle on the service
        return next((j for j in range(i - 1, -1, -1) if log[j]["tool"] in ACTS and on(log[j], service)), -1)

    def acted_after(i, service):
        return next((a for a in log[i + 1:] if a["tool"] in ACTS and on(a, service)), None)

    def metrics(i, service):
        """The get_metrics calls on the service that led straight to call i, oldest first. Timed
        steps on other services (a throttle lifted, replicas returned, a wait) may sit between."""
        found = []
        for j in range(i - 1, acted_before(i, service), -1):
            a = log[j]
            if a["tool"] == "get_metrics" and on(a, service):
                found.append(a)
            elif a["tool"] not in ("wait", "throttle", "scale", "get_metrics") or on(a, service):
                if a["tool"] not in ("get_changes", "get_diff", "get_logs") or not found:
                    break
        return found[::-1]

    def demand(p):
        return p["rps"] * (1 - p.get("retry_share", 0))

    def guard(series, service, tool):  # guard_fix: what the retried failures of a disruptive fix need
        retries, normal = svc[service].get("retry", 0), svc[service]["replicas"]
        if not series or not retries or tool not in disrupts or any("retry_share" not in p for p in series):
            return None
        back = [p["retry_share"] / (1 - p["retry_share"]) for p in series]
        capacity = max((1 + b) / p["cpu"] for b, p in zip(back, series))
        failing = 1 - (1 - back[-1] / retries) * (1 - disrupts[tool][1])
        need = (1 + retries * failing) / capacity
        return dict(need=need, replicas=math.ceil(normal * need), share=min(90, math.ceil(100 * (1 - 1 / need)) + 1),
                    fails=disrupts[tool][1], retries=retries, normal=normal)

    def symptoms(i, service):  # what the logs said about the service before call i: its own errors, then its callers'
        own, blamed = [], []
        for j in range(i - 1, max(-1, i - 60), -1):
            a = log[j]
            if a["tool"] != "get_logs":
                continue
            for line in a["result"].get("lines", []):
                m = upstream.match(line["message"])
                if on(a, service) and not m and line["level"] in ("ERROR", "FATAL"):
                    own.append((line["message"], None))
                elif m and m[1] == service and m[2] not in ("503 or timeout",):
                    blamed.append((m[2], a["args"]["service"]))
        return own + blamed

    for i, a in enumerate(log):
        tool, s = a["tool"], a["args"].get("service")
        rule, why = None, None
        if tool == "get_topology":
            rule, why = 1, "Read who earns what, who calls whom and whose callers retry."
        elif tool == "list_alerts":
            total = a["result"].get("total", len(a["result"].get("alerts", [])))
            rule, why = 2, f"{total} alerts are firing. Keep the services that fail more than their dependencies explain."
        elif tool == "get_logs":
            caller = next(((log[j]["args"]["service"], m[2]) for j in range(i - 1, max(-1, i - 12), -1)
                           if log[j]["tool"] == "get_logs" for line in log[j]["result"].get("lines", [])
                           if (m := upstream.match(line["message"])) and m[1] == s), None)
            if svc[s]["tier"] == "edge":
                share = estate._err(a["t0"])[s]
                rule, why = 3, f"Customers of {s} see {share:.1%} errors that no alert explains. Start from its log."
            elif caller:
                rule, why = 3, f"The log of {caller[0]} blames {s} ({caller[1]}). Read what {s} itself reports."
            else:
                rule, why = 4, f"Look for an error of its own in the log of {s}."
        elif tool == "get_changes":
            rule, why = 4, f"List what changed on {s} before blaming a change."
        elif tool == "get_diff":
            rule, why = 4, f"Read what {a['args'].get('change_id')} did. A change is undone only if its own diff touches the symptom."
        elif tool == "get_metrics":
            nxt = acted_after(i, s)
            if nxt and nxt["tool"] == "scale" and nxt["args"]["replicas"] != svc[s]["replicas"]:
                follow = acted_after(log.index(nxt), s)
                if follow and follow["tool"] in disrupts:
                    rule, why = 6, f"Measure the headroom of {s} before a fix that will fail some of its requests."
                else:
                    rule, why = 5, f"Real traffic or retries? Compare the requests of {s} with a calm window."
            elif nxt and nxt["tool"] == "throttle" and nxt["args"].get("percent"):
                rule, why = 7, f"The fix is in. Check whether retries still hold {s} down."
        elif tool == "wait":
            rule = 7
        elif tool == "scale":
            normal, replicas = svc[s]["replicas"], a["args"]["replicas"]
            nxt = acted_after(i, s)
            if replicas == normal:
                fix = next((b for b in log[:i][::-1] if on(b, s) and b["tool"] in disrupts), None)
                up = next((b for b in log[:i][::-1] if on(b, s) and b["tool"] == "scale" and b["args"]["replicas"] > normal), None)
                rule = 7
                if up and fix and fix["result"].get("completes_at_minute", 999) <= a["t0"] + 1:
                    why = (f"The {NOUN[fix['tool']]} has landed. Give back the {up['args']['replicas'] - normal} "
                           f"borrowed replicas: {up['args']['replicas']} to {normal}.")
                elif up:
                    why = f"No disruptive fix followed. Give back the borrowed replicas: {up['args']['replicas']} to {normal}."
            elif nxt and nxt["tool"] in disrupts:
                rule = 6
                g = guard((metrics(i, s) or [{}])[-1].get("result", {}).get("series"), s, nxt["tool"])
                if g and g["replicas"] == replicas:
                    why = (f"Protect first. The {NOUN[nxt['tool']]} fails {g['fails']:.0%} of requests, callers retry "
                           f"{g['retries']} times: {g['need']:.0%} of what {normal} replicas serve. "
                           f"Scale {normal} to {replicas} first.")
                elif svc[s].get("retry") and replicas == min(4 * normal, math.ceil(normal * (1 + svc[s]["retry"] * disrupts[nxt["tool"]][1] * 1.15))):
                    why = (f"Protect first. Callers retry {svc[s]['retry']} times and the {NOUN[nxt['tool']]} fails "
                           f"{disrupts[nxt['tool']][1]:.0%} of requests: scale {normal} to {replicas} without waiting to measure.")
            else:
                rule = 5
                group = metrics(i, s)
                if group:
                    last, series = group[0]["result"]["series"][-1], group[-1]["result"]["series"]
                    calm = min(series, key=demand)
                    need = last["replicas"] * demand(last) / demand(calm) * calm["cpu"] * (1 - calm.get("retry_share", 0)) / 0.95
                    if demand(last) >= 1.3 * demand(calm) and max(last["replicas"] + 1, math.ceil(need)) == replicas:
                        why = (f"Real traffic, not retries. With retries taken out, {s} gets {demand(last):,.0f} requests a second "
                               f"against {demand(calm):,.0f} in the calm window at minute {calm['minute']}, "
                               f"{demand(last) / demand(calm):.1f} times as many. Scale {last['replicas']} to {replicas}.")
        elif tool in UNDO:
            rule, change = 4, a["result"].get("reverted")
            diffs = {b["args"]["change_id"]: b["result"].get("diff", "") for b in log[acted_before(i, s) + 1:i]
                     if b["tool"] == "get_diff" and on(b, s)}
            for symptom, caller in symptoms(i, s) if change in diffs else ():
                shared = policies.words(symptom) & policies.words(diffs[change])
                if shared:
                    word = max(sorted(shared), key=len)
                    other = [c for c, d in diffs.items() if c != change and not policies.words(symptom) & policies.words(d)]
                    said = f"The log of {caller} says of {s}" if caller else f"The log of {s} says"
                    why = (f"{said}: {symptom}. The diff of {change} touches `{word}`"
                           + (f"; {other[0]}, the other change that minute, does not" if other else "")
                           + f". {UNDO[tool].capitalize()} {change}.")
                    break
            if not why and change:
                lines = " | ".join(m for m, _ in symptoms(i, s))
                if "first seen in build" in lines or "setting loaded from" in lines:
                    why = f"The log of {s} names the change itself. {UNDO[tool].capitalize()} {change}."
        elif tool == "failover":
            rule = 4
            if any("primary node unreachable" in m for m, _ in symptoms(i, s)):
                why = f"The log of {s} says its primary node is unreachable. Fail over."
        elif tool == "throttle" and a["args"]["percent"]:
            percent, start, retries = a["args"]["percent"], a["result"]["effective_at_minute"], svc[s].get("retry", 0)
            nxt, group = acted_after(i, s), metrics(i, s)
            fix = next((b for b in log[:i][::-1] if on(b, s) and b["tool"] in NOUN
                        and b["result"].get("completes_at_minute") == start), None)
            if nxt and nxt["tool"] in disrupts and nxt["t0"] <= a["t1"]:
                rule = 6
                g = guard((group or [{}])[-1].get("result", {}).get("series"), s, nxt["tool"])
                if g and g["share"] == percent:
                    why = (f"Protect first. The {NOUN[nxt['tool']]} will fail {g['fails']:.0%} of the requests of {s} and its callers "
                           f"retry {g['retries']} times: {g['need']:.0%} of its capacity. Here a {percent}% throttle costs less than replicas.")
            elif fix and retries:
                rule = 7
                lands = "new replicas land" if fix["tool"] == "scale" else f"{NOUN[fix['tool']]} lands"
                why = (f"Callers of {s} retry {retries} times, and those retries would hold it down after the fix. "
                       f"Reject {percent}% for the minute the {lands}, minute {start}, so it comes back calm.")
            elif group and retries:
                rule, last = 7, group[-1]["result"]["series"][-1]
                if last.get("retry_share", 0) > 0.2 and last["cpu"] >= 0.9:
                    capacity = (1 - last["error_rate"]) / (1 - last["retry_share"])
                    if percent == min(90, math.ceil(100 * (1 - capacity / (1 + retries * last["error_rate"]))) + 3):
                        why = (f"The cause is gone, but {last['retry_share']:.0%} of the requests of {s} are retries and it sheds "
                               f"{last['error_rate']:.0%}: a storm that outlived its cause. Reject {percent}% for one minute so "
                               f"nothing is retried into the next.")
        elif tool == "throttle":
            rule = 7
            was = next((b for b in log[:i][::-1] if on(b, s) and b["tool"] == "throttle" and b["args"]["percent"]), None)
            if was:
                held = a["result"]["effective_at_minute"] - was["result"]["effective_at_minute"]
                why = f"Lift it after {held} minute{'' if held == 1 else 's'}. A throttle left on keeps turning customers away."
        if rule:
            out[i] = dict(rule=rule, **({"why": why} if why else {}))
    return out


# --- bundles ------------------------------------------------------------------------


def read_bundle(path):
    """The episode a bundle file holds, or None when the file is not one."""
    text = Path(path).read_text()
    try:
        return json.loads(text[text.index("push(") + 5:text.rindex(")")])["sessions"][0]
    except (ValueError, KeyError, IndexError):
        return None


def stored_trials(old):
    """The trials of an exported episode, as inputs: a bundle carries their action logs and words."""
    return [dict(seed=old["seed"], level=old["level"], id=run["id"], label=run["label"], scripted=False,
                 actions=[[a["tool"], a["args"]] for a in run["actions"]], reward=None, report=run.get("report"),
                 words=[{k: a[k] for k in ("say", "think") if k in a} for a in run["actions"]])
            for run in old["runs"] if run["kind"] == "trial"]


def results(incident, level, cfg):
    """The level's result over every measured run, from the loop's committed evidence: the regraded
    scores, and for each run of the headline model how it handled the quiet fault's service, read
    off its signed action log by replaying it."""
    if not cfg or not (HERE / cfg["file"]).exists():
        return None
    rows = [r for r in json.loads((HERE / cfg["file"]).read_text()) if r["round"] == cfg["round"]]
    runs = []
    for r in sorted((r for r in rows if r["run"] == cfg["run"]), key=lambda r: (r["seed"], r["new"])):
        how, receipt = None, HERE / cfg["receipts"] / (r["trial"].replace("/", "__") + ".json")
        if receipt.exists():
            estate = incident.replay(r["seed"], level, json.loads(receipt.read_text())["actions"])
            quiet = next((f["service"] for f in estate.faults if f.get("gray")), None)
            fix = next((i for i, (tool, args) in enumerate(estate.actions)
                        if tool in ("rollback", "revert_config") and args.get("service") == quiet), None)
            if quiet and fix is not None:  # did capacity go on the service before the fix that disturbs it?
                normal = estate.svc[quiet]["replicas"]
                first = any(tool == "scale" and args.get("service") == quiet and args["replicas"] > normal
                            for tool, args in estate.actions[:fix])
                how = "unprotected" if not first else "wasted" if estate.wasted else "protected"
            elif quiet:
                how = "never fixed"
        runs.append(dict(seed=r["seed"], score=round(r["new"], 2), trial=r["trial"].split("/")[0] + "-" + r["trial"].split("__")[-1],
                         **({"how": how} if how else {})))
    if not runs:
        return None
    scores = sorted(r["new"] for r in rows if r["run"] == cfg["run"])
    others = [dict(label=cfg["others"].get(r["run"], r["run"]), score=round(r["new"], 2), seed=r["seed"])
              for r in rows if r["run"] != cfg["run"]]
    fresh = cfg.get("fresh")  # the same model on seeds no task ships: one score a seed, from the loop's metrics
    if fresh and (HERE / fresh["file"]).exists():
        got = sorted((r for r in json.loads((HERE / fresh["file"]).read_text())
                      if (r["round"], r["run"], r["level"]) == (fresh["round"], cfg["run"], level)), key=lambda r: r["seed"])
        fresh = got and dict(mean=round(sum(r["score"] for r in got) / len(got), 2), source=fresh.get("source", ""),
                             runs=[dict(seed=r["seed"], score=round(r["score"], 2)) for r in got])
    return dict(label=cfg["label"], mean=round(sum(scores) / len(scores), 2), median=round(scores[len(scores) // 2], 2),
                low=round(scores[0], 2), high=round(scores[-1], 2), count=len(scores), runs=runs, others=others,
                source=cfg.get("source", ""), **({"fresh": fresh} if fresh else {}))


def session(incident, policies, seed, level, names, trials, notes):
    """Everything the viewer needs for one episode: the estate, its faults, and the runs on it."""
    probe = incident.Estate(seed, level)
    order = list(reversed(probe.order))  # edge services first, as get_topology lists them
    index = {n: i for i, n in enumerate(order)}
    place, rows = layout(probe.svc, probe.edges)
    services = [dict(name=n, tier=probe.svc[n]["tier"], revenue=probe.svc[n]["revenue"],
                     replicas=probe.svc[n]["replicas"], deps=[[index[d], w] for d, w in probe.svc[n]["deps"]],
                     **({"retries": probe.svc[n]["retry"], "tight": probe.svc[n]["cap"] < incident.HEADROOM}
                        if "retry" in probe.svc[n] else {}),
                     **place[n]) for n in order]
    faults = [dict(service=index[f["service"]], kind=f["kind"], label=FAULT_LABELS.get(f["kind"], f["kind"]),
                   fix=FAULT_FIX.get(f["kind"]), start=f["start"], quiet=bool(f.get("gray")), late=f["start"] > 0,
                   share=round(1 - incident.HEADROOM / f["load"], 4) if f["kind"] == "overload" else f["sev"],
                   **({"onset": f["start"] + f["grow"]} if f["kind"] == "leak" else {}))
              for f in probe.faults]
    decoy = probe.batch and dict(service=index[probe.batch["service"]], start=probe.batch["start"],
                                 end=probe.batch["end"])
    sid = f"l{level}-s{seed}"
    about = notes.get(sid, {})
    # the task instruction as the agent got it, one entry per bullet
    brief = (HERE.parent / "task/instruction.md").read_text().replace("<!-- BRIEFING -->\n", incident.briefing(level))
    told = [" ".join(b.split()) for b in re.split(r"\n(?=- )", brief) if b.startswith("- ")]
    told = [b[2:].split(" ## ")[0].split(" | ")[0].strip() for b in told]

    runs, scripted, cost = [], [], {}
    for name in dict.fromkeys(["reference", "nothing"] + names):
        estate, log = play(incident, seed, level, lambda call: policies.POLICIES[name](
            lambda tool, **args: call(tool, args)))
        run = record(incident, estate, log, index)
        if name == "reference":  # why it made each call, next to what the agent says of its own
            for action, reason in zip(run["actions"], explain(policies, estate, log)):
                action.update(reason or {})
        cost[name] = run["cost"]["total"]
        if name in names or name == "reference":
            what = (policies.POLICIES[name].__doc__ or "").strip().split(". ")[0].replace("\n", " ")
            (runs if name == "reference" else scripted).append(dict(
                id=name, label=POLICY_LABELS.get(name, name), kind="policy", source=f"policy {name}",
                **({"note": dict(what=" ".join(what.split()).rstrip(".") + ".")} if what and name != "reference" else {}),
                **run))
    for trial in trials:
        def drive(call, trial=trial):
            for tool, args in trial["actions"]:
                if not call(tool, args)["ok"]:
                    raise ValueError(f"{trial['id']}: action rejected on replay: {tool} {args}")
        try:
            estate, log = play(incident, seed, level, drive)
        except ValueError as e:  # a log recorded under different rules than this simulator's
            print(f"skipped {e}", file=sys.stderr)
            continue
        run = record(incident, estate, log, index)
        for action, words in zip(run["actions"], trial["words"]):
            action.update({k: v for k, v in (words or {}).items() if v})
        graded = (trial["reward"] or {}).get("cost_total")
        if graded is not None and abs(graded - run["cost"]["total"]) > 0.01:
            print(f"note: {trial['id']} was graded at ${graded:,.2f}; this simulator replays it to "
                  f"${run['cost']['total']:,.2f}", file=sys.stderr)
        runs.append(dict(id=trial["id"], label=trial["label"], kind="trial", source=f"trial {trial['id']}",
                         **({"report": trial["report"]} if trial["report"] else {}), **run))
    order_of = about.get("order", [])  # the runs to lead with, by id; the rest keep their order
    runs[1:] = sorted(runs[1:], key=lambda r: order_of.index(r["id"]) if r["id"] in order_of else len(order_of))
    runs += sorted(scripted, key=lambda r: names.index(r["id"]))  # the reference, the trials, then the scripts
    for run in runs:
        run["score"] = round(incident.score(run["cost"]["total"], cost["nothing"], cost["reference"]), 4)
        if run["id"] in about.get("runs", {}):  # what went wrong in this run, from the loop's notes
            note = dict(about["runs"][run["id"]])
            # moments: a quote from the agent's own report, or a label, pinned to the call it is about
            for moment in note.pop("moments", []):
                hit = next((a for a in run["actions"] if a["tool"] == moment["tool"]
                            and a["args"].get("service") == moment["service"] and "label" not in a
                            and all(a["args"].get(k) == moment[k] for k in ("replicas", "percent") if k in moment)), None)
                if hit is None:
                    print(f"note: no {moment['tool']} on {moment['service']} in {run['id']} for its moment", file=sys.stderr)
                    continue
                hit.update({k: moment[k] for k in ("quote", "label") if k in moment})
                if "told" in moment:  # the sentence of the task instruction that covers this call, as shipped
                    said = next((b for b in told if b.startswith(moment["told"])), None)
                    if said is None:
                        print(f"note: the instruction has no sentence starting {moment['told']!r}", file=sys.stderr)
                    else:
                        hit["told"] = said
            run["note"] = note
    headline = results(incident, level, about.get("headline"))
    cfg = incident.LEVELS[level]
    return dict(
        id=sid, seed=seed, level=level, title=about.get("title", f"Level {level}, seed {seed}"),
        horizon=incident.HORIZON, pre=PRE, rows=rows, cost_null=cost["nothing"], cost_ref=cost["reference"],
        rules=dict(query_min=cfg["query_min"], act_min=cfg["act_min"], wasted=cfg["wasted"],
                   replica_cost=incident.REPLICA_COST, storms=bool(cfg.get("storms"))),
        runbook=[list(line) for line in RUNBOOK], **({"headline": headline} if headline else {}),
        services=services, faults=faults, decoy=decoy or None, runs=runs)


# two-sided 95% quantiles of Student's t, by degrees of freedom (beyond 30, the normal's 1.96)
T975 = [None, 12.706, 4.303, 3.182, 2.776, 2.571, 2.447, 2.365, 2.306, 2.262, 2.228, 2.201, 2.179, 2.160, 2.145,
        2.131, 2.120, 2.110, 2.101, 2.093, 2.086, 2.080, 2.074, 2.069, 2.064, 2.060, 2.056, 2.052, 2.048, 2.045, 2.042]


def spread(cfg, metrics, placeholder=False):
    """Every scored run of each model on the pre-registered seeds, for the band above the replay: scores only,
    no actions, so it is safe for any seed. The mean weighs each seed once, and its 95% interval comes from the
    seed means (Student's t, seeds - 1 degrees of freedom): runs on one seed share its estate, so they are not
    independent samples of the model."""
    rows = [r for r in json.loads(Path(metrics).read_text())
            if r.get("round") == cfg["round"] and r.get("level") == cfg["level"] and r.get("score") is not None]
    # Harbor trials only (<job>/<trial>__<id>): scores from another harness, such as rl/'s own runner, stay out
    harbor = [r for r in rows if re.fullmatch(r"[^/\s]+/[^/\s]+__[A-Za-z0-9]+", r.get("trial") or "")]
    if len(harbor) < len(rows):
        print(f"note: spread leaves out {len(rows) - len(harbor)} round-{cfg['round']} rows that are not Harbor trials",
              file=sys.stderr)
    rows = harbor
    models = []
    for run, label in cfg["models"]:
        mine = sorted((r for r in rows if r["run"] == run), key=lambda r: (r["seed"], r.get("trial", "")))
        off = sorted({r["seed"] for r in mine} - set(cfg["seeds"]))
        if off:
            print(f"note: spread leaves out {run}'s runs on seeds {off}, which were not pre-registered", file=sys.stderr)
        mine = [r for r in mine if r["seed"] in cfg["seeds"]]
        if not mine:
            continue
        by = {}
        for r in mine:
            by.setdefault(r["seed"], []).append(round(r["score"], 4))
        means = [statistics.mean(v) for v in by.values()]
        k = len(means)
        half = T975[min(k - 1, 30)] * statistics.stdev(means) / math.sqrt(k) if 1 < k <= 31 else \
            1.96 * statistics.stdev(means) / math.sqrt(k) if k > 31 else None
        models.append(dict(run=run, label=label, mean=round(statistics.mean(means), 4), n=len(mine), seeds=k,
                           **({"half": round(half, 4)} if half is not None else {}),
                           runs=[dict(seed=s, score=v, k=i) for s, vs in by.items() for i, v in enumerate(vs)]))
    seeds = sorted(cfg["seeds"])
    named = f"{seeds[0]} to {seeds[-1]}" if seeds == list(range(seeds[0], seeds[-1] + 1)) else ", ".join(map(str, seeds))
    return dict(caption=cfg["caption"], level=cfg["level"], round=cfg["round"], seeds=named, models=models,
                source=f"{Path(metrics).name}, round {cfg['round']}", **({"placeholder": True} if placeholder else {}))


def write_spread(notes, metrics=None):
    """data/spread.js from the notes' "spread" entry; the page draws nothing while no model has a run."""
    cfg = notes.get("spread")
    if not cfg:
        return
    data = spread(cfg, metrics or HERE / cfg["file"], placeholder=metrics is not None)
    DATA.mkdir(exist_ok=True)
    (DATA / "spread.js").write_text(f"window.REPLAY_SPREAD = {json.dumps(data, separators=(',', ':'), sort_keys=True)};\n")
    got = ", ".join(f"{m['run']} {m['n']} runs on {m['seeds']} seeds" for m in data["models"]) or "no runs yet"
    print(f"wrote data/spread.js ({got}){' from PLACEHOLDER data' if metrics else ''}")


def write_index(first=None):
    """data/index.js: the bundles the page loads. The first one opens: the episode the notes name under
    "open", then the newest level."""
    found = sorted((p for p in DATA.glob("l*-s*.js") if re.fullmatch(r"l\d+-s\d+\.js", p.name)),
                   key=lambda p: [p.stem != first] + [-int(n) if i == 0 else int(n) for i, n in enumerate(re.findall(r"\d+", p.name))])
    (DATA / "index.js").write_text(f"window.REPLAY_FILES = {json.dumps([p.name for p in found])};\n")
    return found


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--level", type=int, help="default: the simulator's newest level")
    ap.add_argument("--seeds", help=f"comma-separated seeds (default {DEFAULT_SEED}); never a shipped task's seed")
    ap.add_argument("--policies", help="scripted policies to play next to the reference")
    ap.add_argument("--jobs", action="append", default=[], help="a Harbor jobs folder; adds its agent trials")
    ap.add_argument("--trial", action="append", default=[], help="one Harbor trial folder (repeatable)")
    ap.add_argument("--only", help="keep only trials whose job name contains one of these comma-separated strings")
    ap.add_argument("--fresh", action="store_true", help="drop the trials already stored in the bundle")
    ap.add_argument("--notes", default=HERE / "notes.json", help="titles and per-run captions, by episode")
    ap.add_argument("--sim", default=HERE.parent / "sim", help="folder with incident.py")
    ap.add_argument("--policy-file", default=HERE.parent / "task/solution/policies.py")
    ap.add_argument("--out", help="write plain JSON for the chosen episodes here instead of bundles")
    ap.add_argument("--spread", action="store_true", help="write only data/spread.js, the scores band, and stop")
    ap.add_argument("--metrics", help="read the band's runs from this file instead of ../metrics.json; marks it a "
                                      "placeholder, which deploy.sh refuses to ship")
    opts = ap.parse_args()
    notes = json.loads(Path(opts.notes).read_text()) if Path(opts.notes).exists() else {}
    if opts.spread:
        return write_spread(notes, opts.metrics)

    incident = load(Path(opts.sim) / "incident.py", "incident")
    policies = load(opts.policy_file, "policies")
    stamp = hashlib.sha256((Path(opts.sim) / "incident.py").read_bytes()).hexdigest()[:12]
    picked = [p for p in (opts.policies or ",".join(POLICIES)).split(",") if p in policies.POLICIES and p != "reference"]

    for stale in DATA.glob("l*-s*.js"):  # a bundle of a shipped seed must not sit in data/, whoever put it there
        if int(re.fullmatch(r"l\d+-s(\d+)\.js", stale.name)[1]) in shipped_seeds():
            sys.exit(f"refused: {stale.relative_to(HERE)} is the bundle of a shipped task's seed. Delete it before exporting.")
    existing = {p.stem: read_bundle(p) for p in DATA.glob("l*-s*.js")}
    existing = {k: v for k, v in existing.items() if v}
    again = not (opts.level is not None or opts.seeds or opts.jobs or opts.trial or opts.out or opts.policies) and existing
    if again:  # no episode named: every bundle again, from its own runs
        todo = [(old["level"], old["seed"]) for old in existing.values()]
    else:
        level = max(incident.LEVELS) if opts.level is None else opts.level
        todo = [(level, int(s)) for s in (opts.seeds or str(DEFAULT_SEED)).split(",")]
    barred = sorted({seed for _, seed in todo} & shipped_seeds())
    if barred:
        sys.exit(f"refused: seed {', '.join(map(str, barred))} is a shipped task's seed. Its bundle would be that "
                 f"task's answer key (faults and the reference's calls). Use a fresh seed, for example {DEFAULT_SEED}.")

    known = variants(incident)
    asked = [Path(t) for t in opts.trial]
    folders = list(asked)
    for jobs in opts.jobs:
        folders += sorted(p.parent for p in Path(jobs).glob("*/*__*/config.json"))
    found = [t for t in (read_trial(incident, f, known) for f in folders) if t]
    found = [t for t in found if (not t["scripted"] or any(t["id"].startswith(f.parent.name) for f in asked))
             and (not opts.only or any(s in t["id"] for s in opts.only.split(",")))]

    sessions = []
    for level, seed in todo:
        sid, old = f"l{level}-s{seed}", existing.get(f"l{level}-s{seed}")
        if level not in incident.LEVELS:
            print(f"skipped {sid}: this simulator has no level {level}", file=sys.stderr)
            continue
        trials = [t for t in found if (t["level"], t["seed"]) == (level, seed)]
        if old and not opts.fresh:  # keep what the bundle already holds, unless a folder brings it again
            trials += [t for t in stored_trials(old) if t["id"] not in [x["id"] for x in trials]]
        names = [r["id"] for r in old["runs"] if r["kind"] == "policy" and r["id"] in policies.POLICIES
                 and r["id"] != "reference"] if again else picked
        sessions.append(session(incident, policies, seed, level, names, trials, notes))

    for s in sessions:
        print(f"{s['id']}: do-nothing ${s['cost_null']:,.0f}, reference ${s['cost_ref']:,.0f}")
        for run in s["runs"]:
            print(f"  {run['id']:<28} ${run['cost']['total']:>10,.0f}  score {run['score']:.2f}  "
                  f"{len(run['actions'])} actions")
    if opts.out:
        Path(opts.out).write_text(json.dumps(dict(version=2, simulator=stamp, sessions=sessions),
                                             separators=(",", ":"), sort_keys=True) + "\n")
        print(f"wrote {opts.out}")
        return
    DATA.mkdir(exist_ok=True)
    for s in sessions:
        body = json.dumps(dict(version=2, name=s["id"], simulator=stamp, sessions=[s]), separators=(",", ":"), sort_keys=True)
        out = DATA / f"{s['id']}.js"
        out.write_text(f"(window.REPLAY_BUNDLES = window.REPLAY_BUNDLES || []).push({body});\n")
        print(f"wrote {out.relative_to(HERE)} ({out.stat().st_size / 1024:.0f} KB)")
    print("data/index.js lists " + ", ".join(p.name for p in write_index(notes.get("open"))))
    write_spread(notes, opts.metrics)


if __name__ == "__main__":
    main()
