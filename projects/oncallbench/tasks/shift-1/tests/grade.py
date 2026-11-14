"""Verifier: check the receipt signature, replay the action log, settle, score.

Nothing the agent wrote is trusted. A missing or tampered receipt is graded as do-nothing.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import incident  # noqa: E402

CALIBRATION = json.loads(Path(__file__).with_name("calibration.json").read_text())


def grade(receipt_path):
    seed, level, valid = CALIBRATION["seed"], CALIBRATION["level"], 1.0
    try:
        receipt = json.loads(Path(receipt_path).read_text())
        if receipt["sig"] != incident.sign(receipt["actions"]):
            raise ValueError("bad signature")
        estate = incident.replay(seed, level, receipt["actions"])
    except Exception as e:
        print(f"receipt rejected, grading as do-nothing: {e!r}")
        valid, estate = 0.0, incident.replay(seed, level, [])
    cost = estate.total_cost()
    ledger = {
        "reward": incident.score(cost, CALIBRATION["cost_null"], CALIBRATION["cost_ref"]),
        "cost_total": cost,
        "beats_reference": float(cost < CALIBRATION["cost_ref"]),
        "valid_receipt": valid,
        "actions": len(estate.actions),
        "faults_left": sum(1 for f in estate.faults if f["end"] is None and f["kind"] != "overload"),
    }
    ledger.update({f"cost_{key}": value for key, value in estate._cost().items()})
    return ledger


if __name__ == "__main__":
    ledger = grade(sys.argv[1])
    print(json.dumps(ledger))
    Path(sys.argv[2]).write_text(json.dumps(ledger))
