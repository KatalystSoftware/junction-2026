"""Regression checks for the red-team findings (redteam/REPORT.md). python3 redteam/test_redteam.py

1. The task's main container cannot resolve the public replay viewer, which serves the reference's
   every call for seed 101 (`tasks/shift-1`). The end-to-end check is the Harbor run in REPORT.md.
2. Where no files are loaded, `consumer-fixer` and `drain-only` play the reference's exact calls,
   so `eval.py` leaves them out there instead of printing them at 1.00 next to it.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "sim"))
sys.path.insert(0, str(ROOT))

import eval as ev  # noqa: E402
import incident  # noqa: E402
import policies  # noqa: E402

BLOCK = '"incident.katalyst.fyi:127.0.0.1"'


def test_replay_site_blocked():
    for compose in [ROOT / "task/environment/docker-compose.yaml",
                    *sorted(ROOT.glob("tasks/*/environment/docker-compose.yaml"))]:
        main = compose.read_text().split("\n  mcp-server:")[0]
        assert BLOCK in main, f"{compose}: main can reach the public replay viewer"


def test_file_policies_are_the_reference_without_files():
    for seed in (101, 102, 103):
        logs = {}
        for name in ("reference", *sorted(ev.FILE_ONLY)):
            estate = incident.Estate(seed, incident.SUBMITTED)
            policies.POLICIES[name](lambda tool, **args: estate.call(tool, args))
            logs[name] = estate.actions
        assert all(log == logs["reference"] for log in logs.values()), f"seed {seed}: a file-only policy differs"
    assert not ev.FILE_ONLY & set(ev.evaluate(101, incident.SUBMITTED)["score"])


if __name__ == "__main__":
    test_replay_site_blocked()
    test_file_policies_are_the_reference_without_files()
    print("ok")
