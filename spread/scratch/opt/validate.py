"""The offline stand-in (sim.py) against weeks that were played: for each variant that the archive holds on the reference's
seeds, the stand-in's difference to the reference next to the played difference, week by week.
PYTHONPATH=. uv run --with numpy python scratch/opt/validate.py <data> <cache> [draws]"""
import glob, json, sys
import numpy as np
from sim import Weeks, simulate, reference_rule, shadow_rule

data, cache = sys.argv[1:3]
DRAWS = int(sys.argv[3]) if len(sys.argv) > 3 else 2
weeks = Weeks(data, cache)
everything = list(range(len(weeks.W)))
weeks.fit(everything)
print("late model, log odds:", {"intercept": round(float(weeks.beta[0]), 2), **{n: round(float(b), 3) for n, b in zip(__import__("sim").FEATURES, weeks.beta[1:])}})
print("week intercepts: sd %.2f, lowest %.2f, highest %.2f" % (np.std(weeks.week), min(weeks.week), max(weeks.week)))
HOURS = [[6, 1.55], [8, 1.35], [12, 1.3], [30, 1.2]]
tight = lambda inner: (lambda row, parts, trust, desk: reference_rule(row, parts, trust, desk) if row["drivers"] < 750 else inner(row, parts, trust, desk))
RULES = {
    "steep-notes-offers-8-cost-1.4": shadow_rule(weeks, cost=1.4),
    "step-2": shadow_rule(weeks, step=0.02),
    "step-2-gate-25": shadow_rule(weeks, step=0.02, gate=25),
    "due-24": shadow_rule(weeks, step_hours=24),
    "due-24-gate-20": shadow_rule(weeks, step_hours=24, gate=20),
    "due-24-gate-25": shadow_rule(weeks, step_hours=24, gate=25),
    "due-24-gate-25-tight-750": tight(shadow_rule(weeks, step_hours=24, gate=25)),
    "hours": shadow_rule(weeks, cost=1.15, hours=HOURS),
    "hours-step-2-gate-25": shadow_rule(weeks, cost=1.15, hours=HOURS, step=0.02, gate=25),
    "hours-due-24-gate-25": shadow_rule(weeks, cost=1.15, hours=HOURS, step_hours=24, gate=25),
}
mean = lambda rows, k: np.mean([[r[k] for r in rows[d]] for d in range(DRAWS)], axis=0)
ref = [simulate(weeks, reference_rule, everything, d) for d in range(DRAWS)]
played = weeks.played
print("\nreference, %d weeks: stand-in orders %.1f late %.1f margin %.0f on time %.3f | played orders %.1f late %.1f margin %.0f on time %.3f" % (
    len(everything), mean(ref, "orders").mean(), mean(ref, "late").mean(), mean(ref, "margin").mean(), 1 - mean(ref, "late").sum() / mean(ref, "orders").sum(),
    np.mean([p["wonOrders"] for p in played]), np.mean([p["wonOrders"] * (1 - p["onTimeShare"]) for p in played]), np.mean([p["marginCents"] for p in played]) / 100,
    1 - sum(p["wonOrders"] * (1 - p["onTimeShare"]) for p in played) / sum(p["wonOrders"] for p in played)))
print("  week by week, stand-in against played: on-time share r = %.2f, orders r = %.2f, margin r = %.2f" % (
    np.corrcoef(1 - mean(ref, "late") / mean(ref, "orders"), [p["onTimeShare"] for p in played])[0, 1], np.corrcoef(mean(ref, "orders"), [p["wonOrders"] for p in played])[0, 1],
    np.corrcoef(mean(ref, "margin"), [p["marginCents"] for p in played])[0, 1]))
print("\nvariant, weeks | difference to the reference, stand-in / played: orders, late orders, margin | on-time share by week r | weeks under 91%: stand-in / played (same weeks) | lowest week stand-in / played")
for name, rule in RULES.items():
    scores = {}
    for f in glob.glob(f"{data}/runs/{name}/*.score.json"):
        d = json.load(open(f)); scores[d["seed"]] = d["score"]
    on = [wi for wi in everything if weeks.seeds[wi] in scores]
    if not on:
        continue
    sims = [simulate(weeks, rule, on, d) for d in range(DRAWS)]
    refs = [[ref[d][wi] for wi in on] for d in range(DRAWS)]
    pv, pr = [scores[weeks.seeds[wi]] for wi in on], [played[wi] for wi in on]
    late = lambda p: p["wonOrders"] * (1 - p["onTimeShare"])
    typ = mean(sims, "typ")
    d_orders, d_late = mean(sims, "orders") - mean(refs, "orders"), mean(sims, "late") - mean(refs, "late")
    d_margin = mean(sims, "margin") - 0.026 * np.maximum(0, d_orders) / 100 * typ / 100 - mean(refs, "margin")
    ot_sim = 1 - mean(sims, "late") / mean(sims, "orders")
    d_ot_sim, d_ot_played = ot_sim - (1 - mean(refs, "late") / mean(refs, "orders")), np.array([a["onTimeShare"] - b["onTimeShare"] for a, b in zip(pv, pr)])
    under_sim = np.mean([[r["on_time"] < 0.91 for r in sims[d]] for d in range(DRAWS)], axis=0)
    under_played = np.array([p["onTimeShare"] < 0.91 for p in pv])
    print(f"{name:30} {len(on):3} | orders {d_orders.mean():+6.1f} / {np.mean([a['wonOrders'] - b['wonOrders'] for a, b in zip(pv, pr)]):+6.1f}  late {d_late.mean():+5.1f} / {np.mean([late(a) - late(b) for a, b in zip(pv, pr)]):+5.1f}"
          f"  margin {d_margin.mean():+6.0f} / {np.mean([a['marginCents'] - b['marginCents'] for a, b in zip(pv, pr)]) / 100:+6.0f} | level r {np.corrcoef(ot_sim, [p['onTimeShare'] for p in pv])[0, 1]:.2f}, change r {np.corrcoef(d_ot_sim, d_ot_played)[0, 1]:.2f}"
          f" | under 91%: {under_sim.sum():.1f} / {under_played.sum()}, of the played ones the stand-in has {under_sim[under_played].sum():.1f} | lowest {min(min(r['on_time'] for r in s) for s in sims):.3f} / {min(p['onTimeShare'] for p in pv):.3f}")
