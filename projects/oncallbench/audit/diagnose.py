"""Explain existing fresh-seed counterexamples, without modifying the reference or simulator."""

import json
from check import HERE, load

ev = load(HERE / "runtime")
rows = [json.loads(line) for line in (HERE / "generality.jsonl").read_text().splitlines()]
details = []
for row in rows:
    if row["reference_oracle"] >= .75 and row["cost_ref"] <= row["cost_null"]:
        continue
    seed = row["seed"]
    estate = ev.incident.Estate(seed, 4)
    events = []

    def call(tool, **args):
        before = estate.now
        result = estate.call(tool, args)
        events.append(dict(at=before, tool=tool, args=args, result=result))
        return result

    ev.policies.reference(call)
    estate.finish()
    mitigations = [e for e in events if e["tool"] in estate.TOOLS and
                   e["tool"] not in ("get_status", "get_topology", "list_alerts", "get_logs", "get_metrics",
                                     "get_changes", "get_diff", "wait", "finish")]
    traces = [dict(at=e["at"], tool=e["tool"], args=e["args"],
                   **({"lines": e["result"].get("lines")} if e["tool"] == "get_logs" else {}))
              for e in events if e["tool"] in ("get_logs", "get_metrics", "get_changes", "get_diff")]
    detail = dict(seed=seed, ratio=row["reference_oracle"], cost_null=row["cost_null"],
                  cost_ref=row["cost_ref"], cost_oracle=row["cost_oracle"], components=estate._cost(),
                  faults=estate.faults, mitigations=mitigations, queries=traces,
                  edges_at_end=estate.get_status()["edge"], accepted_calls=len(estate.actions),
                  alerts_at_end={tier or "all": estate.list_alerts(tier=tier) for tier in (None, "app", "data")},
                  residual_own=[dict(service=n, error=estate._own(n, 120),
                                     state=estate._state(120)[n], replicas=estate._replicas(n, 120),
                                     load=estate._load(n, 120), cap=estate.svc[n]["cap"])
                                for n in estate.order if estate._own(n, 120) >= .01],
                  final_throttles=estate.get_status()["throttles"])
    details.append(detail)
    print(json.dumps({k: detail[k] for k in ("seed", "ratio", "components", "faults", "mitigations")}), flush=True)
(HERE / "counterexamples.json").write_text("[\n" + ",\n".join(json.dumps(row, sort_keys=True) for row in details) + "\n]\n")
finish_checks = []
for row in rows:
    if row["score"]["no-late"] < 1:
        continue
    estate = ev.run(row["seed"], 4, "no-late")
    again = ev.incident.Estate(row["seed"], 4)
    finish_at = None
    for tool, args in estate.actions:
        if tool == "finish":
            finish_at = again.now
        again.call(tool, args)
    finish_checks.append(dict(seed=row["seed"], finish_at=finish_at,
                              late_start=next(f["start"] for f in estate.faults if f["start"] >= 0),
                              cost=estate.total_cost()))
(HERE / "no-late-full-score.json").write_text(json.dumps(finish_checks, indent=2) + "\n")
