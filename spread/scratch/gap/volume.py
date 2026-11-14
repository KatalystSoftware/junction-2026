"""What more orders cost in late orders: variants on the same seeds, from the score files. PYTHONPATH=. uv run --with numpy python scratch/gap/volume.py <data>"""
import sys, json, os
data = sys.argv[1]
S = {}
for v in os.listdir(f"{data}/runs"):
    for f in os.listdir(f"{data}/runs/{v}"):
        if f.endswith(".score.json"):
            s = json.load(open(f"{data}/runs/{v}/{f}"))
            sc = s.get("score", s)
            S[(v, f.split("-L8")[0])] = sc
variants = ["curve-live-surcharge", "curve-fee-1.0", "curve-fee-1.0-cost-1.3", "curve-fee-1.0-cost-1.2", "curve-fee-1.0-gate-25", "curve-fee-0.9-cost-1.2", "fee-cap-1.2-drop", "fee-cap-1.2-drop-cost-1.3", "notes", "notes-offers-8", "steep", "steep-cost-1.2",
            "steep-notes", "steep-notes-offers-8", "steep-notes-offers-8-cost-1.4", "steep-notes-offers-24", "slack-6", "slack-7", "steep-notes-offers-8-guard-92", "curve-no-gate", "curve-gate-10", "surcharge-8", "curve-live", "floor-1.7-all", "floor-1.5-gate-10"]
ref = "steep-notes-offers-8"
print(f"{'variant':34} seeds  orders  late/wk  on-time  lowest  margin | against the reference on the same seeds: d orders, d late, d margin")
for v in variants:
    seeds = sorted(s for (vv, s) in S if vv == v)
    if not seeds: continue
    common = [s for s in seeds if (ref, s) in S]
    o = [S[(v, s)]["wonOrders"] for s in seeds]; l = [S[(v, s)]["wonOrders"] * (1 - S[(v, s)]["onTimeShare"]) for s in seeds]
    line = f"{v:34} {len(seeds):4} {sum(o) / len(o):7.1f} {sum(l) / len(l):7.1f} {1 - sum(l) / sum(o):8.3f} {min(S[(v, s)]['onTimeShare'] for s in seeds):7.3f} {sum(S[(v, s)]['marginCents'] for s in seeds) / len(seeds) / 100:7.0f}"
    if common and v != ref:
        do = sum(S[(v, s)]["wonOrders"] - S[(ref, s)]["wonOrders"] for s in common) / len(common)
        dl = sum(S[(v, s)]["wonOrders"] * (1 - S[(v, s)]["onTimeShare"]) - S[(ref, s)]["wonOrders"] * (1 - S[(ref, s)]["onTimeShare"]) for s in common) / len(common)
        dm = sum(S[(v, s)]["marginCents"] - S[(ref, s)]["marginCents"] for s in common) / len(common) / 100
        line += f" | n={len(common)} {do:+6.1f} {dl:+5.1f} {dm:+7.0f}"
    print(line)
# within the reference: weeks by orders won
rows = sorted((S[(ref, s)]["wonOrders"], S[(ref, s)]["onTimeShare"], S[(ref, s)]["marginCents"] / 100, s) for (v, s) in S if v == ref)
print("\nreference weeks by orders won (quarters): orders, on time, margin, margin/order")
q = len(rows) // 4
for i in range(4):
    part = rows[i * q:(i + 1) * q] if i < 3 else rows[3 * q:]
    print("  %5.0f  %.3f  %6.0f  %5.1f  lowest on time %.3f" % (sum(r[0] for r in part) / len(part), sum(r[1] for r in part) / len(part), sum(r[2] for r in part) / len(part), sum(r[2] for r in part) / sum(r[0] for r in part), min(r[1] for r in part)))
