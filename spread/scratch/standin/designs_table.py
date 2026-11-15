"""The designs of a CI round side by side, from the downloaded artifacts (`gh run download <run> -D <folder>`).

    python3 scratch/standin/designs_table.py <folder>

One line a design, baseline and group: the ranking agreement on the pairs play decides, on all pairs, keep-or-reject agreement, the
correlation and slope of the gain, its typical miss and bias, weeks under 90% and 92% per 60 (played / stand-in), and the arms' late
orders, stand-in over played.
"""
from __future__ import annotations

import glob
import json
import sys

print(f"{'design':20} {'baseline':10} {'group':8} {'pairs':>5} {'decided':>7} {'rank':>5} {'sign':>5} {'keep':>5} {'only sim':>8} {'only play':>9} {'corr':>5} {'slope':>5} {'miss':>5} {'bias':>6} "
      f"{'<90/60 p/s':>11} {'<92/60 p/s':>11} {'late':>5} {'d late r':>8} {'d ord r':>7}")
for path in sorted(glob.glob(f"{sys.argv[1]}/*/result-*.json")):
    d = json.load(open(path))
    name = path.split("result-")[1][: -len(".json")]
    for base in ("steep-notes-offers-8", "slow-friday-late-150-kinds-limits"):
        if name.endswith("-" + base):
            name, short = name[: -len(base) - 1], "reference" if base.startswith("steep") else "default"
    for group, s in d["summary"].items():
        rows = [r for r in d["rows"] if group == "all" or r["group"] == group]
        decided = [r for r in rows if r["played_interval"][0] > 0 or r["played_interval"][1] < 0]
        rank = sum((r["played_gain"] > 0) == (r["sim_gain"] > 0) for r in decided) / max(1, len(decided))
        print(f"{name:20} {short:10} {group:8} {s['checks']:5} {len(decided):7} {rank:5.2f} {s['sign_agree']:5.2f} {s['verdict_agree']:5.2f} {s['kept_by_sim_only']:8} {s['kept_by_play_only']:9} "
              f"{s['gain_corr']:5.2f} {s['slope']:5.2f} {s['gain_rmse']:5.0f} {s['gain_bias']:+6.0f} {s['played_under90_per60']:5.2f}/{s['sim_under90_per60']:<5.2f} "
              f"{s['played_under92_per60']:5.2f}/{s['sim_under92_per60']:<5.2f} {s['arm_late_ratio']:5.2f} {s['late_corr']:8.2f} {s['orders_corr']:7.2f}")
