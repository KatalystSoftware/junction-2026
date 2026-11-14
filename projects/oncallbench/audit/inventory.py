"""Record reference decisions that select an unread twin change; observes the unmodified policy."""

import json

from check import HERE, load

ev = load(HERE / "runtime")
rows = []
for seed in list(range(1, 13)) + list(range(101, 107)):
    estate = ev.incident.Estate(seed, 4)
    changes, read = {}, {}
    decisions = []

    def call(tool, **args):
        before = estate.now
        result = estate.call(tool, args)
        service = args.get("service")
        if result.get("ok") and tool == "get_changes":
            changes[service] = [c for c in result["changes"] if c["status"] == "live"]
            read[service] = []
        if result.get("ok") and tool == "get_diff":
            read.setdefault(service, []).append(args["change_id"])
        if result.get("ok") and tool in ("rollback", "revert_config") and service in changes:
            by_id = {c["id"]: c for c in changes[service]}
            selected = by_id.get(result["reverted"])
            if selected and selected["id"] not in read[service] and read[service]:
                decisions.append(dict(minute=before, service=service, tool=tool, selected=selected,
                                      read_diff_ids=read[service][:], changes=changes[service]))
        return result

    ev.policies.reference(call)
    rows.append(dict(seed=seed, decisions=decisions))
(HERE / "unread-twins.json").write_text(json.dumps(rows, indent=2) + "\n")
print(json.dumps(dict(seeds=len(rows), selections=sum(len(r["decisions"]) for r in rows),
                      seeds_with_selections=[r["seed"] for r in rows if r["decisions"]])))
