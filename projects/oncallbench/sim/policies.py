"""Scripted policies. Each one only sees what an agent sees: `call(tool, **args) -> dict`.

Run against the live MCP server: python3 policies.py <policy> [url]
"""

import json
import math
import re
import sys
import urllib.request


def nothing(call):
    """Do-nothing baseline: never touches the estate."""


def stop_early(call):
    """Looks at the dashboards, then ends the shift without mitigating anything."""
    call("get_status")
    call("list_alerts")
    call("finish")


def leak_fix(call, service):
    """Memory that keeps climbing. The latest build is rolled back only on evidence: memory was
    low and flat in the window before it went out, so the climb began with it, and after reading
    what it changed. If memory was already climbing before the build, a restart is the stopgap."""
    changes = call("get_changes", service=service).get("changes", [])
    deploys = [c for c in changes if c["type"] == "deploy" and c["status"] == "live"]
    if not deploys or deploys[-1]["minute"] < -240:
        return ("restart", {})
    build = deploys[-1]
    before = call("get_metrics", service=service, until_minute=build["minute"])
    mem = [p["mem"] for p in before.get("series", [])]
    if before.get("ok") and mem and (max(mem) > 0.6 or max(mem) - min(mem) > 0.08):
        return ("restart", {})
    call("get_diff", service=service, change_id=build["id"])
    return ("rollback", {})


def scale_fix(call, service, since=None):
    """`since`: when the saturation began, if the default window no longer reaches a calm minute.
    Without it, a window that is saturated from its first minute holds no baseline: step back a
    window at a time until one starts calm, or the telemetry runs out."""
    back = {} if since is None else {"until_minute": since + 5}
    series = call("get_metrics", service=service, **back).get("series")
    if not series:
        return None
    def demand(p):  # retries are not new traffic
        return p["rps"] * (1 - p.get("retry_share", 0))

    last = series[-1]
    while since is None and series[0]["cpu"] >= 0.9:  # the trouble began before this window
        earlier = call("get_metrics", service=service, until_minute=series[0]["minute"]).get("series")
        if not earlier:
            break
        series = earlier
    calm = min(series, key=demand)  # size for the new load at 95% CPU
    if demand(last) < 1.3 * demand(calm):
        return None
    need = last["replicas"] * demand(last) / demand(calm) * calm["cpu"] * (1 - calm.get("retry_share", 0)) / 0.95
    return ("scale", {"replicas": max(last["replicas"] + 1, math.ceil(need))})


def words(text):
    return {w for w in re.split(r"[^a-z0-9]+", text.lower()) if len(w) >= 3}


def change_fix(call, service, symptom):
    """Undo the latest deploy or the latest config change: the one whose own diff touches what
    the symptom names. Newest first, and stop reading at the first match. Every change is judged by
    its own diff, also one that landed together with an ordinary one; None when no diff matches."""
    live = [c for c in call("get_changes", service=service).get("changes", []) if c["status"] == "live"]
    last = sorted({c["type"]: c for c in live}.values(), key=lambda c: -c["minute"])
    for c in last:
        if words(symptom) & words(call("get_diff", service=service, change_id=c["id"]).get("diff", "")):
            return ("rollback" if c["type"] == "deploy" else "revert_config", {})
    return None


DISRUPTS = {"rollback": (6, 0.3), "restart": (3, 0.5)}  # minutes a mitigation runs, share it fails meanwhile


def guard_fix(call, service, tool, retries, normal, worth, left):
    """How to keep a disruptive mitigation from tipping a quiet service whose callers retry: the
    retries of what it fails must still fit its capacity. ("scale", replicas) or ("throttle",
    percent), whichever costs less; 0: it has the headroom; None: too late in the shift, the
    mitigation would fail more than the fault still can."""
    series = call("get_metrics", service=service).get("series")
    if not series or series[-1]["cpu"] >= 0.9:
        return 0
    back = [p["retry_share"] / (1 - p["retry_share"]) for p in series]
    capacity = max((1 + b) / p["cpu"] for b, p in zip(back, series))  # in units of normal load
    minutes, now = DISRUPTS[tool][0], back[-1] / retries
    failing = 1 - (1 - now) * (1 - DISRUPTS[tool][1])
    need = (1 + retries * failing) / capacity
    if need <= 1:
        return 0
    replicas, share = math.ceil(normal * need), min(90, math.ceil(100 * (1 - 1 / need)) + 1) / 100
    by_scale = 5 * now * worth + 3 * (replicas - normal) * (minutes + 8)  # the wait for it, and its replicas
    by_throttle = (minutes * share * (1 - failing) + share) * worth  # what it rejects, to the minute it lifts
    if left is not None and min(by_scale, by_throttle) + minutes * failing * worth >= now * (left - minutes) * worth:
        return None
    return ("scale", replicas) if by_scale <= by_throttle else ("throttle", round(100 * share))


def drain_fix(call, service, retries):
    """A storm that outlived its cause: reject the share it is shedding for a minute, so nothing
    is retried into the next one. None: no storm, or enough headroom to recover by itself."""
    series = call("get_metrics", service=service).get("series")
    if not series or series[-1]["retry_share"] <= 0.2 or series[-1]["cpu"] < 0.9:
        return None
    last = series[-1]
    capacity = (1 - last["error_rate"]) / (1 - last["retry_share"])
    if capacity > 1.45:
        return None
    return ("throttle", {"percent": min(90, math.ceil(100 * (1 - capacity / (1 + retries * last["error_rate"]))) + 3)})


UPSTREAM = re.compile(r"upstream call to (\S+) failed \((.*)\)")
FILE = re.compile(r"loading \w+ file: (\d+) entries, limit (\d+)")  # a consumer choking on a generated file


def trace(call, edge, busy, trusting=False, ready=None, since=None):
    """Descend from a failing edge along `upstream call to ... failed` log lines when no alert
    explains its errors: every upstream line of a service, the largest first, each service once.
    A service that logs its own failure is diagnosed, whether it alerts or not (`since`: when its
    CPU alert began, if it has one); one that only passes on failures from below, or whose
    diagnosis finds nothing to do, is descended through. One its caller blames by symptom while its
    own logs are clean is the suspect: its diffs settle it. A service with an operation in progress
    is left alone. `trusting` believes the clean logs and undoes the nearest caller's recent
    change instead."""
    visited = {edge}

    def descend(service, path, why):
        logs = call("get_logs", service=service).get("lines", [])
        text = " | ".join(line["message"] for line in logs)
        ups = sorted(((line["count"], m[1], m[2]) for line in logs if (m := UPSTREAM.match(line["message"]))),
                     reverse=True)
        own = [line for line in logs if line["level"] in ("ERROR", "FATAL") and not UPSTREAM.match(line["message"])]
        if path and (own or "request queue full" in text or "heap above" in text):
            action = diagnose(call, service, since=(since or {}).get(service), logs=logs)
            if action:
                return service, action
        elif path and not ups and words(why) - {"503", "timeout"}:
            if not trusting:
                if ready:  # the suspect is named: anything slow it needs can start while its diffs are read
                    ready(service)
                action = change_fix(call, service, why)
                if action:
                    return service, action
            for caller in path[::-1] if trusting else ():
                recent = [c for c in call("get_changes", service=caller).get("changes", [])
                          if c["status"] == "live" and c["minute"] >= -90]
                if recent:
                    return caller, ("rollback" if recent[-1]["type"] == "deploy" else "revert_config", {})
        for _, dep, reason in ups:
            if dep in visited or dep in busy:
                continue
            visited.add(dep)
            found = descend(dep, path + [service], reason)
            if found:
                return found
        return None

    return descend(edge, [], "") or (None, None)


def diagnose(call, service, signals=(), since=None, logs=None):
    """Pick the mitigation an on-call engineer would from the cheapest evidence. None: not a cause."""
    if "mem" in signals:  # memory only climbs on a leaking build
        return leak_fix(call, service)
    if "cpu" in signals:  # saturated and failing: traffic, if the request rate rose
        action = scale_fix(call, service, since)
        if action:
            return action
    if logs is None:
        logs = call("get_logs", service=service).get("lines", [])
    lines = " | ".join(line["message"] for line in logs)
    if "first seen in build" in lines:
        return ("rollback", {})
    if "setting loaded from" in lines:
        return ("revert_config", {})
    if "primary node unreachable" in lines:
        return ("failover", {})
    if "out of memory" in lines or "heap above" in lines:
        return leak_fix(call, service)
    if "request queue full" in lines:  # under retries a failing service sheds too: its own error comes first
        storm = "retry storm" in lines
        symptom = storm and any(line["level"] == "ERROR" and not UPSTREAM.match(line["message"]) for line in logs)
        action = None if symptom else scale_fix(call, service, since)  # from before its alert began, if it has one
        if action or not storm:
            return action
    for line in logs:  # a symptom that does not name its change: read the diffs
        if line["level"] == "ERROR" and not UPSTREAM.match(line["message"]):
            if FILE.search(line["message"]):  # the file it loaded is bad: the cause is where the file is made
                return ("file", {"symptom": line["message"]})
            return change_fix(call, service, line["message"])
    return None


def graph(call):
    """Topology, weighted dependencies, and the revenue per minute each service can take down."""
    topo = {s["name"]: s for s in call("get_topology")["services"]}
    deps = {n: [(d["service"], 1.0 if d["kind"] == "hard" else 0.3) for d in s["depends_on"]]
            for n, s in topo.items()}

    def worth(target):
        memo = {}

        def err(n):
            if n not in memo:
                ok = 0.0 if n == target else 1.0
                for d, w in deps[n]:
                    ok *= 1 - w * err(d)
                memo[n] = 1 - ok
            return memo[n]

        return sum(s["revenue_per_min"] * err(n) for n, s in topo.items() if s["tier"] == "edge")

    return topo, deps, {n: worth(n) for n in topo}


def blind(topo, service, n):
    """The n-th generic mitigation to try on a service without reading anything, cheapest first."""
    tools = (["failover"] if topo[service]["tier"] == "data" else []) + ["revert_config", "rollback", "scale", "restart"]
    if n >= len(tools):
        return None
    return (tools[n], {"replicas": 2 * topo[service]["normal_replicas"]} if tools[n] == "scale" else {})


def reference(call, max_fixes=None, leave_when_clear=False, thorough=False, descend=True, trusting=False,
              guess=False, drain=True, protect=True, lift=True, files="fix"):
    """An expert on call. A service is a cause when it fails more than its dependencies explain
    (or its memory is filling up), however loud it is; a busy CPU or a recent change alone is not.
    Causes are worked in order of the revenue they cost, each from the cheapest evidence that
    settles it, and the edge is watched to the end of the shift for whatever starts later.
    Where the alert list is partial, edge errors that no alert explains are money too: they are
    ranked with the alerting causes and traced down through the callers' logs.
    Where callers retry, a disruptive mitigation on a quiet service gets capacity first (or a
    throttle, whichever is cheaper by its metrics), a service that retries hold down is throttled
    for the minute its fix lands so it comes back calm, and every throttle and borrowed replica
    is given back the minute it has done its work.
    Where services load a generated file, a service that chokes on its file, or whose failure comes
    and goes, is not the cause: its log at the minute its alert began names the file, the topology
    names the publisher, the publisher's diffs name the change, and after the revert the consumers
    that retries hold down are throttled together for the minute the next good file lands. A
    consumer is never mitigated. There the alert list is read by tier when it would be cut, a
    queued suspect is dropped when the free status shows its edges healthy again, and a quiet
    suspect gets unmeasured spare capacity while its diffs are read."""
    topo, deps, worth = graph(call)
    began, mended, treated, shed, seen, tiers = {}, {}, set(), {}, {}, None
    calm, hogs = set(), {}
    filed = any("file_from" in s for s in topo.values())  # what follows from it applies only where files are loaded
    fixes, looked, free, dropped, tried = 0, {}, None, set(), {}
    retries = {n: s.get("callers_retry", 0) for n, s in topo.items()}
    fixed, cleared, prepared, timers, clock, raw = set(), set(), {}, [], [0], call

    def call(tool, **args):
        """Timed steps go first: the throttle for the minute a fix lands, its lift, replicas to give
        back. A step that falls due before this call would return is made at its minute."""
        reach = args["minutes"] - 1 if tool == "wait" else 1 if tool.startswith(("get_", "list_")) else 0
        served = None
        while timers and tool not in ("get_status", "get_topology") and min(t[0] for t in timers) <= clock[0] + reach:
            minute, step, kw = timers.pop(min(range(len(timers)), key=lambda i: timers[i][0]))
            if minute > clock[0]:
                clock[0] = raw("wait", minutes=minute - clock[0]).get("minute", clock[0])
            served = raw(step, **kw)
            clock[0] = served.get("minute", clock[0])
        if served and tool == "wait":
            return served
        result = raw(tool, **args)
        clock[0] = result.get("minute", clock[0])
        return result

    def under(n):
        return {x for d, _ in deps[n] for x in {d} | under(d)}

    def prepare(service):
        """Capacity takes minutes to land: a quiet suspect whose callers retry gets it before its
        diffs are read, sized for a rollback, and gives it back if no rollback follows."""
        left = call("get_status")["minutes_left"] if filed else 0
        if protect and retries.get(service) and service not in err and left >= 60:
            # with most of the shift ahead, replicas for ten minutes cost less than the two minutes it
            # takes to measure the headroom: size it as if there were none
            normal = topo[service]["normal_replicas"]
            replicas = min(4 * normal, math.ceil(normal * (1 + retries[service] * DISRUPTS["rollback"][1] * 1.15)))
            prepared[service] = ("scale", replicas, call("scale", service=service, replicas=replicas).get("completes_at_minute", 0))
        elif protect and retries.get(service) and service not in err:
            plan = guard_fix(call, service, "rollback", retries[service], topo[service]["normal_replicas"],
                             worth[service], call("get_status")["minutes_left"])
            if plan and plan[0] == "scale":
                plan += (call("scale", service=service, replicas=plan[1]).get("completes_at_minute", 0),)
            prepared[service] = plan

    while True:
        status = call("get_status")
        if status["shift_over"]:
            return
        now = status["minute"]
        busy = {op["service"]: op["completes_at_minute"] for op in status["operations_in_progress"]}
        clear = all(e["error_rate"] <= 0.005 for e in status["edge"])
        if leave_when_clear and fixes and clear and not busy:
            call("finish")
            return
        if free or not clear or free is None:  # status is free; alerts may take clock time
            # the ten loudest hide the rest when the list was cut last time, or when the failing edges
            # alone fill a third of it: read it by tier at once, the edge tier is in the status
            failing = [dict(service=e["service"], signal="error_rate", value=e["error_rate"], firing_since_minute=now)
                       for e in status["edge"] if e["error_rate"] >= 0.05]
            by_tier = filed and (len(failing) >= 3 if tiers is None else tiers)
            result = call("list_alerts", **({"tier": "app"} if by_tier else {}))
            if not result["ok"]:
                return
            free = result["minute"] == now if free is None else free
            alerts, partial = result["alerts"], "total" in result
            cut = False
            seen = {a["service"]: now for a in alerts}  # the minute each alert was read at
            if by_tier:
                at, more = clock[0], call("list_alerts", tier="data")
                cut = result["total"] > len(alerts) or more.get("total", 0) > len(more.get("alerts", []))
                tiers = result["total"] + more.get("total", 0) + len(failing) + 1 > 10
                seen.update({a["service"]: at for a in more.get("alerts", [])})
                alerts = alerts + more.get("alerts", []) + failing
            elif partial and result["total"] > len(alerts):  # the list is cut off: read it tier by tier
                tiers = True
                for tier in ("app", "data"):
                    at, more = clock[0], call("list_alerts", tier=tier)
                    cut = cut or more.get("total", 0) > len(more.get("alerts", []))
                    seen.update({a["service"]: at for a in more.get("alerts", []) if a not in alerts})
                    alerts += [a for a in more.get("alerts", []) if a not in alerts]
            else:
                tiers = False
            err = {a["service"]: a["value"] for a in alerts if a["signal"] == "error_rate"}
            signals, since = {}, {}
            for a in alerts:
                signals.setdefault(a["service"], set()).add(a["signal"])
                if partial and a["signal"] == "cpu" and a["firing_since_minute"] + 5 <= now:
                    since[a["service"]] = a["firing_since_minute"]
            began = {a["service"]: a["firing_since_minute"] for a in alerts if a["signal"] == "error_rate"}
            hogs = {a["service"]: a["firing_since_minute"] for a in alerts if a["signal"] == "cpu"}
            if files == "surge":  # reads the waves as traffic: capacity where CPU alerts, load shed at the edge
                for n in sorted(signals):
                    if "cpu" in signals[n] and n not in treated and worth[n] > 0:
                        treated.add(n)
                        call("scale", service=n, replicas=2 * topo[n]["normal_replicas"])
                for e in status["edge"]:
                    want = 30 if 1 - (1 - e["error_rate"]) / (1 - shed.get(e["service"], 0) / 100) >= 0.05 else 0
                    if want != shed.get(e["service"], 0):
                        shed[e["service"]] = want
                        call("throttle", service=e["service"], percent=want)
            own = {}
            for n in signals:
                up = 1.0
                for d, w in deps[n]:
                    up *= 1 - w * err.get(d, 0)
                own[n] = 1 - (1 - err.get(n, 0)) / up if up > 0.02 else 0
                if cut and retries.get(n) and "cpu" in signals[n] and n not in err and n not in cleared:
                    # saturated under retries while a caller fails: the ten shown may hide its error alert
                    own[n] = max([err[c] for c in err if (n, 1.0) in deps[c]] or [0])
            suspects = [n for n in signals if n not in busy and worth[n] > 0 and looked.get(n, -99) + 5 <= now
                        and (own[n] >= 0.06 or "mem" in signals[n])]
            # with partial views the dearest per minute of looking goes first: a saturation or a
            # leak takes one query to settle, a symptom takes the diffs, a trace takes the path too
            work = [(-worth[n] * max(own[n], 0.05) / (1 if not partial else 3 if signals[n] & {"cpu", "mem"} else 8), n)
                    for n in suspects]
            hidden = set()
            for e in status["edge"] if partial and descend else ():
                up = 1.0
                for d, w in deps[e["service"]]:
                    up *= 1 - w * err.get(d, 0)
                gap = 1 - (1 - e["error_rate"]) / up if up > 0.02 else 0  # what customers see, unexplained
                if gap >= 0.01 and e["service"] not in dropped and looked.get(e["service"], -99) + 10 <= now:
                    work.append((-e["revenue_per_min"] * gap / 13, e["service"]))
                    hidden.add(e["service"])
            traced = set()
            for _, service in sorted(work):
                if looked.get(service, -99) > now:  # waiting for its publisher's next file
                    continue
                if service in traced and service not in hidden:  # a trace from the edge got to it first
                    continue
                if filed and not topo[service].get("file_from"):
                    # the list is minutes old by now and the status is free: what no longer fails at the
                    # edge needs no work. A file's consumer comes and goes, so its calm proves nothing.
                    fresh = {e["service"]: e["error_rate"] for e in call("get_status")["edge"]}
                    if all(fresh[e] <= 0.005 for e in fresh if e == service or service in under(e)):
                        continue
                looked[service], edge = now, None
                if service in hidden:
                    hidden.remove(service)
                    # a mitigation in progress below it explains errors; where files are loaded, not one
                    # that has landed since, nor a config revert on a service that was not failing
                    if under(service) & ({n for n, at in busy.items() if at > clock[0] and n not in calm} if filed else set(busy)):
                        continue
                    if trusting:
                        dropped.add(service)
                    edge = service
                    service, action = trace(call, service, busy, trusting, prepare, since)
                    if service in busy:
                        continue
                    traced.add(service)
                else:
                    if thorough:  # read everything on the suspect and its alerting neighbours first
                        near = [d for d, _ in deps[service]] + [n for n in topo if service in dict(deps[n])]
                        for n in [service] + sorted(n for n in near if n in signals):
                            for tool in ("get_metrics", "get_logs", "get_changes"):
                                call(tool, service=n)
                    if guess:
                        action = blind(topo, service, tried.get(service, 0))
                        tried[service] = tried.get(service, 0) + 1
                    elif drain and service in fixed and "cpu" in signals[service]:  # do not doubt the fix
                        action = drain_fix(call, service, retries[service])
                    else:
                        # where callers retry, a failing service is saturated whatever the cause: logs first
                        known = signals[service] - ({"cpu"} if retries.get(service) and service in err else set())
                        action, logs = None, None
                        if files and topo[service].get("file_from"):
                            # a bad file comes and goes, and a storm outlives it: the minute the error
                            # alert began firing shows the cause; with no error alert, the minute it was seen
                            when = began.get(service)
                            logs = call("get_logs", service=service, until_minute=max(
                                when, -150) if when is not None else seen.get(service, clock[0])).get("lines", [])
                            action = next((("file", {"symptom": line["message"]}) for line in logs
                                           if FILE.search(line["message"])), None)
                        action = action or diagnose(call, service, known, since.get(service), logs)
                        if not action and service not in err:
                            cleared.add(service)
                fed = ()
                if action and action[0] == "file":
                    symptom, pub, action = action[1]["symptom"], topo[service].get("file_from"), None
                    if files == "consumer":  # where it shows: undo the consumer's latest change, or restart it
                        if service not in treated:
                            treated.add(service)
                            live = [c for c in call("get_changes", service=service).get("changes", []) if c["status"] == "live"]
                            action = (("rollback" if live[-1]["type"] == "deploy" else "revert_config") if live else "restart", {})
                    elif files == "drain" or pub in mended:  # the storm the bad file left behind
                        if retries.get(service) and (drain or files == "drain") and clock[0] > mended.get(pub, -999):
                            action = drain_fix(call, service, retries[service])
                    elif files == "fix" and pub:
                        # the consumer's log names the file and its size over the limit, the topology names
                        # who makes it: the publisher's diffs settle which change to undo
                        fed, service = [n for n in topo if topo[n].get("file_from") == pub], pub
                        action = change_fix(call, pub, symptom)
                held = service in prepared
                plan = prepared.pop(service, 0)
                if plan and plan[0] == "scale" and not (action and action[0] in DISRUPTS):
                    # given back once it has landed, and after a fix that needs no protection has run
                    timers.append((max(plan[2], clock[0] + 3 if action else 0), "scale",
                                   dict(service=service, replicas=topo[service]["normal_replicas"])))
                if action and action[0] == "throttle":  # a measured drain: one minute, then lift
                    if call(action[0], service=service, **action[1])["ok"] and lift:
                        timers.append((0, "throttle", dict(service=service, percent=0)))
                elif action:
                    quiet = protect and action[0] in DISRUPTS and retries.get(service) and service not in err
                    if not held or action[0] not in DISRUPTS:
                        plan = guard_fix(call, service, action[0], retries[service], topo[service]["normal_replicas"],
                                         worth[service], call("get_status")["minutes_left"] if edge else None) if quiet else 0
                    if plan is None:
                        dropped.add(edge)
                        continue
                    if plan and plan[0] == "scale":  # capacity first: wait for it to land, then mitigate
                        landed = plan[2] if len(plan) > 2 else call(
                            "scale", service=service, replicas=plan[1]).get("completes_at_minute", 0)
                        while not (seen := call("get_status"))["shift_over"] and seen["minute"] < landed:
                            call("wait", minutes=landed - seen["minute"])
                    elif plan:
                        call("throttle", service=service, percent=plan[1])
                    result = call(action[0], service=service, **action[1])
                    at = result.get("completes_at_minute", 0)
                    if plan and plan[0] == "scale":  # give it back the minute the mitigation lands
                        timers.append((at, "scale", dict(service=service, replicas=topo[service]["normal_replicas"])))
                    elif plan and lift:
                        timers.append((at, "throttle", dict(service=service, percent=0)))
                    if result["ok"]:
                        busy[service] = at
                        if action[0] == "revert_config" and service not in err:
                            calm.add(service)
                        if drain and retries.get(service):
                            fixed.add(service)
                            failing = own.get(service, 0)
                            if action[0] in DISRUPTS:
                                failing = 1 - (1 - failing) * (1 - DISRUPTS[action[0]][1])
                            if not plan and failing >= 0.1:  # held down by retries: calm as the fix lands
                                timers.append((at - 1, "throttle", dict(service=service, percent=min(
                                    90, math.ceil(100 * (1 - 1 / (1 + retries[service] * failing)))))))
                                if lift:
                                    timers.append((at, "throttle", dict(service=service, percent=0)))
                        looked.pop(service, None)
                        fixes += 1
                        if fed:  # the file already loaded stays until the next generation
                            mended[service] = tick = 5 * math.ceil(at / 5)
                            for c in fed:
                                looked[c] = tick - 4
                            # retries hold these down: all are throttled by the minute the good file lands and
                            # lifted one a minute after it, the dearest first. One call a minute: those that
                            # cannot be throttled in time take their turn after.
                            # A consumer that was not saturated when the others were, or whose saturation began
                            # after theirs, came back between bad files by itself: it has the headroom.
                            first = min([hogs[c] for c in fed if c in hogs] or [0])
                            hot = [c for c in sorted(fed, key=lambda c: -worth[c]) if drain and retries.get(c) and worth[c] > 0
                                   and not (any(c in hogs for c in fed) and hogs.get(c, 999) > first + 2)]
                            lead = max(1, min(len(hot), tick - clock[0]))
                            for i, c in enumerate(hot):
                                fixed.add(c)
                                on = tick - lead + i if i < lead else tick + lead + 2 * (i - lead)
                                timers.append((on, "throttle", dict(service=c, percent=min(
                                    90, math.ceil(100 * (1 - 1 / (1 + retries[c])))))))
                                if lift:
                                    timers.append((tick + i if i < lead else on + 1, "throttle", dict(service=c, percent=0)))
                        if max_fixes and fixes >= max_fixes:
                            call("finish")
                            return
        now = call("get_status")["minute"]
        pending = [at - now for at in busy.values() if at > now]
        call("wait", minutes=max(1, min(pending)) if pending and not free else 1)


def one_fix(call):
    """Stop-early with one good move: mitigates the first cause it finds, then ends the shift."""
    reference(call, max_fixes=1)


def no_late(call):
    """The reference, but it ends the shift the first time the edge is healthy again."""
    reference(call, leave_when_clear=True)


def thorough(call):
    """The reference, but it reads metrics, logs and changes of the suspect and of every alerting
    neighbour before each mitigation."""
    reference(call, thorough=True)


def trusting(call):
    """The reference, but it believes a service's own telemetry: where a caller blames a service
    that reports healthy, it undoes the caller's recent change and moves on."""
    reference(call, trusting=True)


def alerts_only(call):
    """The reference without the descent from the edge: it works only what `list_alerts` shows."""
    reference(call, descend=False)


def shotgun(call):
    """The reference's eye for where the cause is, but no reading: it cycles the generic
    mitigations on each suspect until one sticks."""
    reference(call, descend=False, guess=True)


def no_drain(call):
    """The reference without retries in mind: it fixes causes and never throttles or scales for
    a storm."""
    reference(call, drain=False, protect=False)


def unprotected(call):
    """The reference, but it rolls back and restarts without protecting the service first; it
    drains the storm afterwards."""
    reference(call, protect=False)


def forgetful(call):
    """The reference, but it never lifts a throttle."""
    reference(call, lift=False)


def consumer_fixer(call):
    """The reference, but it treats a bad file where it shows: it undoes the failing consumer's
    latest change, or restarts it, and never looks at the publisher."""
    reference(call, files="consumer")


def surge_responder(call):
    """The reference, but it reads failures that come in waves as a traffic surge: it scales every
    service with a CPU alert and sheds 30% at each failing edge while it has errors."""
    reference(call, files="surge")


def drain_only(call):
    """The reference, but it drains the storm on a file's consumers each time and never touches
    the publisher."""
    reference(call, files="drain")


def loudest_first(call):
    """Works the loudest alert it has not treated yet, where it shows and one at a time, to the
    end of the shift. Symptoms are louder than causes, so it treats victims and bystanders."""
    topo = {s["name"]: s for s in call("get_topology")["services"]}
    treated = set()
    while True:
        status = call("get_status")
        if status["shift_over"]:
            return
        alert = None
        if any(e["error_rate"] > 0.005 for e in status["edge"]):
            alert = next((a for a in call("list_alerts").get("alerts", []) if a["service"] not in treated), None)
        if not alert:
            call("wait", minutes=1)
            continue
        service = alert["service"]
        treated.add(service)
        action = diagnose(call, service)
        if not action:
            recent = [c for c in call("get_changes", service=service).get("changes", [])
                      if c["status"] == "live" and c["minute"] >= alert["firing_since_minute"] - 15]
            if recent:
                action = ("rollback" if recent[-1]["type"] == "deploy" else "revert_config", {})
            elif alert["signal"] == "cpu":
                action = ("scale", {"replicas": 2 * topo[service]["normal_replicas"]})
            else:
                action = ("restart", {})
        result = call(action[0], service=service, **action[1])
        if result["ok"] and result["completes_at_minute"] > result["minute"]:
            call("wait", minutes=result["completes_at_minute"] - result["minute"])


def exploiter(call):
    """Tries to score without diagnosing: every mitigation on everything that fires."""
    topo = {s["name"]: s for s in call("get_topology")["services"]}
    for probe in (dict(service="nope"), dict(service=None), dict(service=["x"])):
        call("rollback", **probe)
    call("wait", minutes=-5)
    call("wait", minutes=True)
    call("scale", service=next(iter(topo)), replicas=10**6)
    for service in sorted({a["service"] for a in call("list_alerts")["alerts"]}):
        for tool in ("rollback", "revert_config", "restart", "failover"):
            call(tool, service=service)
            call("wait", minutes=6)
        call("scale", service=service, replicas=4 * topo[service]["normal_replicas"])
    call("finish")


POLICIES = {
    "nothing": nothing, "stop-early": stop_early, "one-fix": one_fix,
    "reference": reference, "exploiter": exploiter,
    "shotgun": shotgun, "no-late": no_late, "loudest-first": loudest_first, "thorough": thorough,
    "trusting": trusting, "alerts-only": alerts_only,
    "no-drain": no_drain, "unprotected": unprotected, "forgetful": forgetful,
    "consumer-fixer": consumer_fixer, "surge-responder": surge_responder, "drain-only": drain_only,
}


def http_caller(url):
    def call(tool, **args):
        body = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": tool, "arguments": args}}
        req = urllib.request.Request(url, json.dumps(body).encode(), {
            "Content-Type": "application/json", "Accept": "application/json, text/event-stream"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            reply = json.load(resp)
        if "error" in reply or reply["result"].get("isError"):
            return {"ok": False, "error": "rejected by the server"}
        return json.loads(reply["result"]["content"][0]["text"])

    return call


if __name__ == "__main__":
    POLICIES[sys.argv[1]](http_caller(sys.argv[2] if len(sys.argv) > 2 else "http://mcp-server:8000/mcp"))
