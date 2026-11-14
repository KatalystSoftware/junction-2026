"""Scratch: the share of a week's orders won after each hour of the week (Monday 00:00 is hour 0), on the books of book_rows.py
without `fresh-1301`-`1460`; spreadlab/exposure.json keeps it as `won_after`, which `Book.future` reads. Requests arrive Monday to
Friday, but few orders are won on Friday, so an even rate to Friday 18:00 counts about four times too many orders still to come on
Thursday evening, and with them too high a line for the week's late orders.

    SPREAD_DATA=$PWD/data PYTHONPATH=. uv run --with numpy python scratch/exposure/won_after.py [write]
"""
from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path

from spreadlab.server import data_dir

VARIANTS = ["slow-friday-late-150-kinds-limits", "steep-notes-offers-8", "thin-premium-0.4"]
HOURS = 5 * 24


def main() -> None:
    after, total = [0] * HOURS, 0
    for v in VARIANTS:
        for w in pickle.load(open(data_dir() / "exposure" / f"book-{v}.pkl", "rb")):
            if w["seed"].startswith("fresh-") and 1301 <= int(w["seed"][6:]) <= 1460:
                continue
            first: dict = {}
            for r in w["rows"]:
                first[r["order"]] = min(first.get(r["order"], 10 ** 9), r["at"])
            total += len(first)
            for at in first.values():
                for h in range(min(HOURS, at // 60 + (at % 60 > 0))):
                    after[h] += 1
    share = [round(a / total, 4) for a in after]
    for h in range(0, HOURS, 4):
        print(f"day {h // 24} {h % 24:02d}:00 {share[h]:.3f}")
    if sys.argv[1:] == ["write"]:
        path = Path(__file__).resolve().parents[2] / "spreadlab" / "exposure.json"
        fits = json.loads(path.read_text())
        fits["measured"]["won_after"] = share
        path.write_text(json.dumps(fits, indent=1) + "\n")


if __name__ == "__main__":
    main()
