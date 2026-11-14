"""Check consistency of the audit evidence and its frozen source, without running simulations."""

import ast
import hashlib
import json
import re
import runpy
import tarfile

from check import HERE

for path in HERE.glob("*.py"):
    ast.parse(path.read_text(), filename=str(path))
for path in list(HERE.glob("*.json")) + list((HERE / "evidence").glob("*.json")):
    json.loads(path.read_text())
rows = [json.loads(line) for line in (HERE / "generality.jsonl").read_text().splitlines()]
assert [r["seed"] for r in rows] == list(range(1000, 1200))
assert all(r["level"] == 4 and r["cost_ref"] < r["cost_null"] for r in rows)
assert all(len(r["score"]) == 17 for r in rows)
summary = json.loads((HERE / "generality-summary.json").read_text())
bad = [r["seed"] for r in rows if r["reference_oracle"] < .75]
assert bad == summary["below_075"]
details = json.loads((HERE / "counterexamples.json").read_text())
assert [r["seed"] for r in details] == bad
assert all(r["components"]["wasted"] == 0 for r in details)
assert all(r["final_throttles"] == [] for r in details)
assert [r["seed"] for r in details if any(e["error_rate"] > .01 for e in r["edges_at_end"])] == [1016]
harbor = json.loads((HERE / "harbor-results.json").read_text())
assert harbor["trials"] == 27
assert not any(harbor[k] for k in ("cost_mismatches", "score_mismatches", "receipt_mismatches", "errors"))
assert len({(r["repeat"], r["seed"], r["policy"]) for r in harbor["rows"]}) == 27
provenance = json.loads((HERE / "provenance.json").read_text())
with tarfile.open(HERE / "source.tar.gz") as archive:
    for name, digest in provenance["sha256"].items():
        assert hashlib.sha256(archive.extractfile(name).read()).hexdigest() == digest, name
    original_simulator = archive.extractfile("sim/incident.py").read().decode()
old_tree = ast.parse(original_simulator)
new_tree = ast.parse((HERE.parent / "sim/incident.py").read_text())
for tree in (old_tree, new_tree):
    tree.body = [node for node in tree.body if not isinstance(node, ast.FunctionDef) or node.name != "briefing"]
same_logic = ast.dump(old_tree) == ast.dump(new_tree)
original_scope = {"__name__": "audited_incident"}
exec(compile(original_simulator, "<audited_incident>", "exec"), original_scope)
current_scope = runpy.run_path(str(HERE.parent / "sim/incident.py"))
same_level4_briefing = original_scope["briefing"](4) == current_scope["briefing"](4)
assert same_logic and same_level4_briefing
changed = [name for name, digest in provenance["sha256"].items()
           if hashlib.sha256((HERE.parent / name).read_bytes()).hexdigest() != digest]
report = (HERE / "REPORT.md").read_text()
for name in ("GENERALITY_FINDING", "GENERALITY_TABLES", "HARBOR_RESULTS", "BARE_TASK_RESULT"):
    assert f"<!-- END_{name} -->" in report
for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", report):
    assert (HERE / target).exists(), target
result = dict(fresh_seeds=len(rows), below_075=len(bad), harbor_trials=harbor["trials"],
              counterexamples=len(details), source_archive_matches=True,
              current_simulator_logic_matches_snapshot=same_logic,
              current_level4_briefing_matches_snapshot=same_level4_briefing,
              current_source_differs_from_snapshot=changed)
(HERE / "validation.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result))
