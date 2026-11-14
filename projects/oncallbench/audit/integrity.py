"""Exercise the captured verifier on valid, missing, tampered and signed-illegal receipts."""

import contextlib
import importlib.util
import io
import json

from check import HERE, load

ev = load(HERE / "runtime")
grade_path = HERE / "runtime/jobs/variants/aq-incident-ec900b74/tests/grade.py"
spec = importlib.util.spec_from_file_location("audited_grade", grade_path)
grade = importlib.util.module_from_spec(spec)
spec.loader.exec_module(grade)
directory = HERE / "runtime/integrity"
directory.mkdir(exist_ok=True)
reference = ev.run(101, 4, "reference").receipt()
tampered = json.loads(json.dumps(reference))
tampered["actions"].pop()
illegal = [["wait", {"minutes": -1}]]
cases = dict(valid=reference, tampered=tampered, unsigned=dict(actions=[]),
             signed_illegal=dict(actions=illegal, sig=ev.incident.sign(illegal)), missing=None)
rows = []
for name, receipt in cases.items():
    path = directory / (name + ".json")
    if receipt is not None:
        path.write_text(json.dumps(receipt))
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        ledger = grade.grade(str(path))
    assert ledger["reward"] == (1 if name == "valid" else 0), (name, ledger)
    assert ledger["valid_receipt"] == (1 if name == "valid" else 0), (name, ledger)
    rows.append(dict(case=name, result=ledger, verifier_output=output.getvalue()))
(HERE / "integrity.json").write_text(json.dumps(rows, indent=2) + "\n")
print("All five verifier receipt cases behaved as expected.")
