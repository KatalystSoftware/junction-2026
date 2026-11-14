"""How often each archived variant would clear a top-10 bar that sits a fixed share or a fixed sum above the reference
on the same seed, and still be ranked. From the saved scores only.

    python scratch/scenarios/bar.py <data folder> [reference variant]
"""
import json, sys
from pathlib import Path
import numpy as np

data = Path(sys.argv[1]); REF = sys.argv[2] if len(sys.argv) > 2 else "steep-notes-offers-8"
scores = {}
for folder in sorted((data / "runs").iterdir()):
    for f in folder.glob("*-L8.score.json"):
        s = json.load(open(f)); scores.setdefault(folder.name, {})[s["seed"]] = (s["score"]["marginCents"] / 100, s["score"]["onTimeShare"], s["score"]["wonOrders"], s["score"]["ranked"])
ref = scores[REF]
m = np.array([v[0] for v in ref.values()])
print(f"{REF}: {len(ref)} weeks, margin mean {m.mean():.0f} sd {m.std():.0f}; share of weeks over 13,700: {np.mean(m > 13700):.2f}, over 15,200: {np.mean(m > 15200):.2f}")
print("variant | weeks shared | mean difference | sd of the difference | orders | weeks unranked | under 91% | clears ref x 1.15 | x 1.33 | ref + 1,500 | ref + 3,400 (and ranked)")
out = []
for v, S in scores.items():
    shared = [s for s in S if s in ref]
    if v == REF or len(shared) < 20: continue
    d = np.array([S[s][0] - ref[s][0] for s in shared]); r = np.array([S[s][0] / max(1, ref[s][0]) for s in shared]); rk = np.array([S[s][3] for s in shared]); ot = np.array([S[s][1] for s in shared])
    out.append((d.mean(), f"  {v:32s} {len(shared):4d} {d.mean():+7.0f} {d.std():6.0f} {np.mean([S[s][2] for s in shared]):5.0f} {int((~rk).sum()):3d} {int((ot < .91).sum()):3d}   {np.mean((r >= 1.15) & rk):.2f}  {np.mean((r >= 1.33) & rk):.2f}  {np.mean((d >= 1500) & rk):.2f}  {np.mean((d >= 3400) & rk):.2f}"))
for _, line in sorted(out, reverse=True)[:14]: print(line)
