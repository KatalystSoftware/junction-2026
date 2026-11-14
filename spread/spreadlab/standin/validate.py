"""How far the stand-in can be trusted, measured the way it is used: on played paired checks it was not fitted on.

    python -m spreadlab.standin.validate --baselines steep-notes-offers-8,slow-friday-late-150-kinds-limits --seeds fresh- --out result.json

A paired check is an arm and a baseline that were both played on the same seeds. For each one the stand-in plays the baseline and
the arm on those seeds, with the baseline's played weeks as the base (the arm's own played weeks are never read), and its answer
is set beside play's:
- keep or reject: an arm is kept when its margin gain over the baseline has a 95% interval above zero and it has at most 1 week
  under 90% on time in 60 (a week under 90% counts as no margin);
- the gain itself: correlation, rank correlation, the slope of the played gain on the stand-in's, and the typical miss;
- weeks under 90% and under 92% on time, counts against counts;
- the similarity score. Ranking: of the policy pairs that play decides (the played difference's 95% interval excludes zero), the share
  the stand-in ranks the same way. Week by week, for the same policy and seed: the error of the margin, the orders and the on-time
  share, and the correlation of the margin. The base policy's own weeks are left out of the week-by-week numbers.
Natural and thin worlds (under 720 drivers listed) are reported apart. Fit the weights with `--hold-out` on the same seed prefix
(fit.py), or the check is not held out.
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import time
from multiprocessing import Pool
from pathlib import Path

from ..variants import VARIANTS
from . import pack, run

GROUPS = {"natural": lambda drivers: drivers >= run.THIN, "thin": lambda drivers: drivers < run.THIN}


def find_checks(baselines: list[str], prefixes: list[str], least: int, most: int, only: list[str]) -> list[dict]:
    """Every played arm with at least `least` seeds of the prefixes in common with a baseline; at most `most` seeds a check, evenly through the list."""
    weeks = pack.root() / "weeks"
    seeds_of = {p.name: {f.name[: -len(".json.gz")] for f in p.glob("*.json.gz")} for p in weeks.iterdir()}
    checks = []
    for baseline in baselines:
        for arm in sorted(seeds_of):
            if arm == baseline or (only and arm not in only):
                continue
            seeds = sorted(s for s in seeds_of[arm] & seeds_of.get(baseline, set()) if any(s.startswith(p) for p in prefixes))
            if len(seeds) >= least:
                step = max(1, math.ceil(len(seeds) / most)) if most else 1
                checks.append({"arm": arm, "baseline": baseline, "seeds": seeds[::step][:most] if most else seeds})
    return checks


def params_of(arm: str, seed: str) -> dict:
    """The arm's parameters: from variants.py, or those its played week saved when variants.py no longer names it."""
    if arm in VARIANTS:
        return VARIANTS[arm]
    from ..policy import DEFAULTS
    saved = pack.load_week(arm, seed)["params"] or {}
    return {k: v for k, v in saved.items() if k not in DEFAULTS or DEFAULTS[k] != v}


def verdict(gains: list[float], under: float) -> bool:
    """Kept: the gain's 95% interval is above zero, and at most 1 week in 60 is under 90%."""
    return bool(gains) and run.interval(gains)[0] > 0 and under <= len(gains) / 60 + 1e-9 + (0 if len(gains) >= 60 else 1 - len(gains) / 60)


def rank(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    out = [0.0] * len(values)
    for place, i in enumerate(order):
        out[i] = place
    return out


def corr(a: list[float], b: list[float]) -> float:
    n = len(a)
    if n < 3:
        return float("nan")
    ma, mb = sum(a) / n, sum(b) / n
    va, vb = sum((x - ma) ** 2 for x in a), sum((y - mb) ** 2 for y in b)
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / math.sqrt(va * vb) if va and vb else float("nan")


def score(checks: list[dict], sim: dict, draws: int) -> dict:
    """`sim`: (arm, seed, base) -> [week of each draw]."""
    rows, weeks = [], {}
    for check in checks:
        arm, baseline = check["arm"], check["baseline"]
        played = {s: (run.played_week(arm, s), run.played_week(baseline, s)) for s in check["seeds"]}
        for n, name in enumerate((arm, baseline)):  # each played week beside the stand-in's week of the same policy and seed
            for s in check["seeds"]:
                ws = sim.get((name, s, baseline), [])
                if len(ws) == draws and not (name == baseline and (name, s, baseline) in weeks):
                    p = played[s][n]
                    weeks[(name, s, baseline)] = {"policy": name, "seed": s, "base": baseline, "drivers": p["drivers"], "own_base": name == baseline,
                                                  **{f"played_{k}": p[k] for k in ("margin", "orders", "late", "on_time")},
                                                  **{f"sim_{k}": sum(w[k] for w in ws) / draws for k in ("margin", "orders", "late", "on_time")}}
        for group, keep in GROUPS.items():
            seeds = [s for s in check["seeds"] if keep(played[s][0]["drivers"]) and len(sim.get((arm, s, baseline), [])) == draws and len(sim.get((baseline, s, baseline), [])) == draws]
            if len(seeds) < 10:
                continue
            p_gain = [run.ranked(played[s][0]) - run.ranked(played[s][1]) for s in seeds]
            s_gain = [sum(run.ranked(a) - run.ranked(b) for a, b in zip(sim[(arm, s, baseline)], sim[(baseline, s, baseline)])) / draws for s in seeds]
            under = lambda weeks, line: sum(w["on_time"] < line for w in weeks)
            p_arm, s_arm = [played[s][0] for s in seeds], [w for s in seeds for w in sim[(arm, s, baseline)]]
            p_base, s_base = [played[s][1] for s in seeds], [w for s in seeds for w in sim[(baseline, s, baseline)]]
            mean = lambda xs: sum(xs) / len(xs)
            rows.append({
                "arm": arm, "baseline": baseline, "group": group, "seeds": len(seeds),
                "played_gain": mean(p_gain), "played_interval": run.interval(p_gain), "sim_gain": mean(s_gain), "sim_interval": run.interval(s_gain),
                "played_keep": verdict(p_gain, under(p_arm, 0.90)), "sim_keep": verdict(s_gain, under(s_arm, 0.90) / draws),
                "played_under90": under(p_arm, 0.90), "sim_under90": under(s_arm, 0.90) / draws, "played_under92": under(p_arm, 0.92), "sim_under92": under(s_arm, 0.92) / draws,
                "played_base_under90": under(p_base, 0.90), "sim_base_under90": under(s_base, 0.90) / draws,
                "played_orders": mean([w["orders"] for w in p_arm]) - mean([w["orders"] for w in p_base]), "sim_orders": mean([w["orders"] for w in s_arm]) - mean([w["orders"] for w in s_base]),
                "played_late": mean([w["late"] for w in p_arm]) - mean([w["late"] for w in p_base]), "sim_late": mean([w["late"] for w in s_arm]) - mean([w["late"] for w in s_base]),
                "played_arm_late": mean([w["late"] for w in p_arm]), "sim_arm_late": mean([w["late"] for w in s_arm]),
                "seed_corr": corr(p_gain, s_gain)})
    summary = {}
    for group in list(GROUPS) + ["all"]:
        sel = [r for r in rows if group == "all" or r["group"] == group]
        if not sel:
            continue
        # Week by week, the policies that are not the base: the base's own played week is what the stand-in measured its market from.
        wk = [w for w in weeks.values() if not w["own_base"] and (group == "all" or GROUPS[group](w["drivers"]))]
        err = lambda k: [w[f"sim_{k}"] - w[f"played_{k}"] for w in wk]
        mae = lambda k: sum(map(abs, err(k))) / max(1, len(wk))
        bias = lambda k: sum(err(k)) / max(1, len(wk))
        decided = [r for r in sel if r["played_interval"][0] > 0 or r["played_interval"][1] < 0]
        p, s = [r["played_gain"] for r in sel], [r["sim_gain"] for r in sel]
        var_s = sum((x - sum(s) / len(s)) ** 2 for x in s)
        weeks = sum(r["seeds"] for r in sel)
        summary[group] = {
            "checks": len(sel), "weeks": weeks,
            "verdict_agree": sum(r["played_keep"] == r["sim_keep"] for r in sel) / len(sel),
            "kept_by_play": sum(r["played_keep"] for r in sel), "kept_by_both": sum(r["played_keep"] and r["sim_keep"] for r in sel),
            "kept_by_sim_only": sum(r["sim_keep"] and not r["played_keep"] for r in sel), "kept_by_play_only": sum(r["played_keep"] and not r["sim_keep"] for r in sel),
            "sign_agree": sum((a > 0) == (b > 0) for a, b in zip(p, s)) / len(sel),
            # The headline: of the policy pairs that play decided (the played difference's 95% interval excludes zero), the share the stand-in ranks the same way.
            "decided": len(decided), "ranking_agree": sum((r["played_gain"] > 0) == (r["sim_gain"] > 0) for r in decided) / len(decided) if decided else float("nan"),
            "week_n": len(wk), "week_margin_mae": mae("margin"), "week_margin_bias": bias("margin"), "week_margin_corr": corr([w["played_margin"] for w in wk], [w["sim_margin"] for w in wk]),
            "week_margin_mean": sum(w["played_margin"] for w in wk) / max(1, len(wk)),
            "week_orders_mae": mae("orders"), "week_orders_bias": bias("orders"), "week_orders_corr": corr([w["played_orders"] for w in wk], [w["sim_orders"] for w in wk]),
            "week_on_time_mae": mae("on_time"), "week_on_time_bias": bias("on_time"), "week_on_time_corr": corr([w["played_on_time"] for w in wk], [w["sim_on_time"] for w in wk]),
            "gain_corr": corr(p, s), "gain_rank_corr": corr(rank(p), rank(s)),
            "slope": sum((x - sum(s) / len(s)) * (y - sum(p) / len(p)) for x, y in zip(s, p)) / var_s if var_s else float("nan"),
            "gain_rmse": math.sqrt(sum((a - b) ** 2 for a, b in zip(p, s)) / len(sel)), "gain_bias": sum(b - a for a, b in zip(p, s)) / len(sel),
            "played_under90_per60": 60 * sum(r["played_under90"] for r in sel) / weeks, "sim_under90_per60": 60 * sum(r["sim_under90"] for r in sel) / weeks,
            "played_under92_per60": 60 * sum(r["played_under92"] for r in sel) / weeks, "sim_under92_per60": 60 * sum(r["sim_under92"] for r in sel) / weeks,
            "under92_corr": corr([r["played_under92"] / r["seeds"] for r in sel], [r["sim_under92"] / r["seeds"] for r in sel]),
            "late_corr": corr([r["played_late"] for r in sel], [r["sim_late"] for r in sel]), "orders_corr": corr([r["played_orders"] for r in sel], [r["sim_orders"] for r in sel]),
            "arm_late_ratio": sum(r["sim_arm_late"] * r["seeds"] for r in sel) / max(1e-9, sum(r["played_arm_late"] * r["seeds"] for r in sel)),
        }
    return {"rows": rows, "summary": summary, "weeks": list(weeks.values())}


def report(scored: dict) -> list[str]:
    lines = [f"{'arm':44} {'baseline':34} {'group':8} {'n':>3} {'played gain':>24} {'stand-in gain':>24} {'keep p/s':>8} {'<90 p/s':>9} {'<92 p/s':>9} {'late p/s':>11}"]
    for r in sorted(scored["rows"], key=lambda r: (r["group"], r["baseline"], -r["played_gain"])):
        gain = lambda g, i: f"{g:+6.0f} ({i[0]:+.0f} to {i[1]:+.0f})"
        lines.append(f"{r['arm'][:44]:44} {r['baseline'][:34]:34} {r['group']:8} {r['seeds']:3} {gain(r['played_gain'], r['played_interval']):>24} {gain(r['sim_gain'], r['sim_interval']):>24} "
                     f"{'keep' if r['played_keep'] else 'drop'}/{'keep' if r['sim_keep'] else 'drop'} {r['played_under90']:3}/{r['sim_under90']:<4.1f} {r['played_under92']:3}/{r['sim_under92']:<4.1f} "
                     f"{r['played_arm_late']:5.1f}/{r['sim_arm_late']:<5.1f}")
    for group, s in scored["summary"].items():
        lines.append(f"\n{group}: {s['checks']} checks, {s['weeks']} played weeks of the arms")
        lines.append(f"  SIMILARITY, ranking: of {s['decided']} policy pairs that play decides, the stand-in ranks {s['ranking_agree']:.0%} the same way (all {s['checks']} pairs: {s['sign_agree']:.0%})")
        lines.append(f"  SIMILARITY, week by week ({s['week_n']} weeks, same policy and seed): margin off by {s['week_margin_mae']:.0f} on average ({s['week_margin_mae'] / max(1, s['week_margin_mean']):.0%} of {s['week_margin_mean']:.0f}), "
                     f"bias {s['week_margin_bias']:+.0f}, correlation {s['week_margin_corr']:.2f}; orders off by {s['week_orders_mae']:.1f}, bias {s['week_orders_bias']:+.1f}, correlation {s['week_orders_corr']:.2f}; "
                     f"on-time share off by {100 * s['week_on_time_mae']:.1f} points, bias {100 * s['week_on_time_bias']:+.1f}, correlation {s['week_on_time_corr']:.2f}")
        lines.append(f"  keep or reject agrees in {s['verdict_agree']:.0%}; play keeps {s['kept_by_play']}, both keep {s['kept_by_both']}, only the stand-in keeps {s['kept_by_sim_only']}, only play keeps {s['kept_by_play_only']}")
        lines.append(f"  the gain's sign agrees in {s['sign_agree']:.0%}; correlation {s['gain_corr']:.2f}, rank correlation {s['gain_rank_corr']:.2f}, played gain per unit of stand-in gain {s['slope']:.2f}, "
                     f"typical miss {s['gain_rmse']:.0f}, stand-in minus played {s['gain_bias']:+.0f}")
        lines.append(f"  weeks under 90% per 60: played {s['played_under90_per60']:.2f}, stand-in {s['sim_under90_per60']:.2f}; under 92%: played {s['played_under92_per60']:.2f}, stand-in {s['sim_under92_per60']:.2f} "
                     f"(by arm, correlation {s['under92_corr']:.2f}); late orders of the arms, stand-in over played {s['arm_late_ratio']:.2f}; change in late orders, correlation {s['late_corr']:.2f}; in orders {s['orders_corr']:.2f}")
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--baselines", default="steep-notes-offers-8,slow-friday-late-150-kinds-limits")
    parser.add_argument("--seeds", default="fresh-", help="comma-separated seed prefixes: the held-out seeds")
    parser.add_argument("--arms", default="", help="comma-separated: only these arms")
    parser.add_argument("--least", type=int, default=20)
    parser.add_argument("--most", type=int, default=40)
    parser.add_argument("--draws", type=int, default=1)
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--weights", default=str(run.WEIGHTS))
    parser.add_argument("--design", default="{}")
    parser.add_argument("--out", default="")
    args = parser.parse_args()
    split = lambda text: [x for x in text.split(",") if x]
    checks = find_checks(split(args.baselines), split(args.seeds), args.least, args.most, split(args.arms))
    arms = {}
    for check in checks:
        for name in (check["arm"], check["baseline"]):
            if name not in arms:
                arms[name] = params_of(name, check["seeds"][0])
    tasks = sorted({(name, seed, draw, check["baseline"]) for check in checks for name in (check["arm"], check["baseline"]) for seed in check["seeds"] for draw in range(args.draws)})
    run.SETUP.update(arms=arms, weights=json.loads(Path(args.weights).read_text()), design=json.loads(args.design))
    started, sim, errors = time.time(), collections.defaultdict(list), []
    with Pool(args.jobs) as pool:
        for (arm, seed, draw, base), (_, _, _, week) in zip(tasks, pool.imap(run.job, tasks, chunksize=2)):
            if "error" in week:
                errors.append(f"{arm} {seed}: {week['error']}")
            else:
                sim[(arm, seed, base)].append(week)
    scored = score(checks, sim, args.draws)
    print(f"{len(checks)} checks, {len(tasks)} stand-in weeks, {time.time() - started:.0f} s, {len(errors)} errors")
    print("\n".join(report(scored)))
    for error in errors[:3]:
        print("ERROR", error)
    if args.out:
        Path(args.out).write_text(json.dumps({"design": json.loads(args.design), "weights": args.weights, "errors": errors[:20], **scored}) + "\n")


if __name__ == "__main__":
    main()
