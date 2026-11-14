"""Scratch: the market signals in the desk's own answers (order_won, order_lost) that the policy does not use: the pickup
region of a win (the outage), the week's earlier days (the price war), and the dealer's earlier answers (the competitor's
reaction, the dealer's threshold).

    SPREAD_DATA=... python scratch/inputs/market.py [variant]

The outage, by RULES.md: on one working day the competitor is down in a town and the places within 80 km of it, and
dealers there pay about 30% more. For each day and each of the 30 towns as the centre, the script takes the log
likelihood ratio (LLR) of "quotes for cars collected in that region are accepted at prices 30% higher" against "as the
rest of the day", with the day's shift fitted on the quotes outside the region. A week's outage is the day and centre
with the highest LLR; it counts as identified at an LLR of 6 or more that is 3 above every other day's best.

The replay prices every serious quote again in expected values, as the best policy does (the multiple with the highest
chance x (price - 1.2 x fee - 150 euros x late chance)), with the day's shift learned from the answers so far, in steps
of 15 minutes. It has no drivers: for the curve's slope, play gave a third to a half of what such a replay gave.
"""
from __future__ import annotations

import json
import math
import multiprocessing
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from lib import load

SLOPE, SD, COST, LATE_EUR = 12.5405, 0.16, 1.2, 150
OUTAGE, WAR = math.log(1.3), -0.22
THRESHOLDS = (3, 5, 8)
MAP = json.loads((Path(os.environ.get("SPREAD_DATA", "data")) / "map.json").read_text())
PLACES = sorted(p["id"] for p in MAP["places"])
INDEX = {p: i for i, p in enumerate(PLACES)}
POS = {p["id"]: (math.radians(p["lat"]), math.radians(p["lon"])) for p in MAP["places"]}
MULTIPLES = np.arange(1.0, 2.4001, 0.02)


def km(a: str, b: str) -> float:
    (la, lo), (lb, lob) = POS[a], POS[b]
    return 2 * 6371 * math.asin(math.sqrt(math.sin((lb - la) / 2) ** 2 + math.cos(la) * math.cos(lb) * math.sin((lob - lo) / 2) ** 2))


REGION = np.array([[km(c, p) <= 80 for c in PLACES] for p in PLACES], dtype=float)  # [place, centre]


def sig(x):
    return 1 / (1 + np.exp(-x))


def newton(z, won, weights, mu=0.0, sd=SD):
    """The shift of the curve for each column of weights (answers x columns), with a prior at `mu`."""
    d = np.full(weights.shape[1], float(mu))
    if not len(z):
        return d
    for _ in range(8):
        c = sig(z[:, None] + SLOPE * d[None, :])
        rise = SLOPE * ((won[:, None] - c) * weights).sum(0) - (d - mu) / sd**2
        d = d + np.clip(rise / (SLOPE**2 * (c * (1 - c) * weights).sum(0) + 1 / sd**2), -0.3, 0.3)
    return d


def llr(z, won, d, inside):
    """For each centre: the log likelihood ratio of the outage in its region against none, on the answers inside."""
    if not len(z):
        return np.zeros(inside.shape[1])
    p0, p1 = sig(z[:, None] + SLOPE * d[None, :]), sig(z[:, None] + SLOPE * (d[None, :] + OUTAGE))
    return ((won[:, None] * np.log(p1 / p0) + (1 - won[:, None]) * np.log((1 - p1) / (1 - p0))) * inside).sum(0)


def value(at_list, list_, cost, used, truth):
    """The expected objective of pricing with the shift `used` when the shift is `truth`, and the orders won."""
    if not len(at_list):
        return 0.0, 0.0
    log_m = np.log(MULTIPLES)[None, :]
    revenue = MULTIPLES[None, :] * list_[:, None] - cost[:, None]
    best = np.argmax(sig(at_list[:, None] - SLOPE * (log_m - used[:, None])) * revenue, axis=1)
    rows = np.arange(len(at_list))
    win = sig(at_list - SLOPE * (np.log(MULTIPLES[best]) - truth))
    return float((win * revenue[rows, best]).sum()), float(win.sum())


def week(w: dict) -> dict:
    q = sorted(w["quotes"], key=lambda r: r["at"])
    at = np.array([r["at"] for r in q])
    z, won = np.array([r["z"] for r in q]), np.array([float(r["won"]) for r in q])
    pk, dl = np.array([INDEX[r["pk"]] for r in q]), np.array([INDEX[r["dl"]] for r in q])
    list_, fee = np.array([r["list"] for r in q]) / 100, np.array([r["fee"] for r in q]) / 100
    cost = COST * fee + LATE_EUR * np.array([r["p_slow"] for r in q])
    at_list = z + SLOPE * np.log(np.array([r["m"] for r in q]))
    day, tod = at // 1440, at % 1440
    dealers = [r["dealer"] for r in q]

    hind = {}
    for d in range(5):
        i = np.where(day == d)[0]
        if len(i) < 20:
            continue
        inside, inside_dl = REGION[pk[i]], REGION[dl[i]]
        d_out = newton(z[i], won[i], 1 - inside, sd=0.3)
        hind[d] = {"i": i, "all": newton(z[i], won[i], np.ones((len(i), 1)), sd=0.3)[0], "out": d_out, "llr": llr(z[i], won[i], d_out, inside),
                   "llr_dl": llr(z[i], won[i], newton(z[i], won[i], 1 - inside_dl, sd=0.3), inside_dl).max(), "n": inside.sum(0), "wins": (inside * won[i][:, None]).sum(0)}
    best = {d: float(h["llr"].max()) for d, h in hind.items()}
    out_day = max(best, key=best.get)
    centre = int(hind[out_day]["llr"].argmax())
    top, other = best[out_day], max((v for d, v in best.items() if d != out_day), default=0.0)
    identified = top >= 6 and top - other >= 3
    h = hind[out_day]
    in_true = REGION[pk[h["i"]], centre] > 0
    delta = newton(z[h["i"]][in_true] + SLOPE * h["out"][centre], won[h["i"]][in_true], np.ones((int(in_true.sum()), 1)), sd=0.3)[0]
    truth = np.zeros(len(q))
    for d, hd in hind.items():
        truth[hd["i"]] = hd["all"]
    if identified:
        truth[h["i"]] = h["out"][centre] + delta * in_true
    levels = {d: hd["out"][centre] if d == out_day and identified else hd["all"] for d, hd in hind.items()}
    median = float(np.median(list(levels.values())))
    war_day = min(levels, key=levels.get)

    arms = ["base", "oracle", "friday", "carry"] + [f"det{t}" for t in THRESHOLDS]
    total = {a: {"out": [0.0, 0.0], "other": [0.0, 0.0]} for a in arms}
    flags = {t: [] for t in THRESHOLDS}  # (day, minute of the first flag, the centre's region overlaps the true one)
    finals: dict[int, float] = {}
    war_seen_at = None
    for d, hd in hind.items():
        i = hd["i"]
        inside = REGION[pk[i]]
        prev = [finals[k] for k in sorted(finals)]
        mu_friday = (float(np.median(prev)) + WAR) if d == 4 and len(prev) == 4 and min(prev) - float(np.median(prev)) > -0.12 else 0.0
        seen = len(prev) >= 2 and min(prev) - float(np.median(prev)) <= -0.12
        mu_carry = mu_friday if mu_friday else float(np.median(sorted(prev)[1:])) if seen else 0.0
        where = "out" if d == out_day and identified else "other"
        first = {t: None for t in THRESHOLDS}
        for t in range(480, 1110, 15):
            a, now = tod[i] + 15 <= t, (tod[i] >= t) & (tod[i] < t + 15)
            if not now.any():
                continue
            za, wa = z[i][a], won[i][a]
            ones = np.ones((int(a.sum()), 1))
            s_pol = newton(za, wa, ones)[0]
            if d == war_day and war_seen_at is None and a.sum() >= 5 and s_pol - (float(np.median(prev)) if prev else 0.0) <= -0.12:
                war_seen_at = t
            d_c = newton(za, wa, 1 - inside[a])
            live = llr(za, wa, d_c, inside[a])
            c_live = int(live.argmax())
            j = i[now]
            shifts = {"base": np.full(len(j), s_pol), "oracle": truth[j], "friday": np.full(len(j), newton(za, wa, ones, mu=mu_friday)[0]),
                      "carry": np.full(len(j), newton(za, wa, ones, mu=mu_carry)[0])}
            for thr in THRESHOLDS:
                if live[c_live] >= thr:
                    if first[thr] is None:
                        first[thr] = t
                        flags[thr].append((d, t, bool(d == out_day and identified and (REGION[:, c_live] * REGION[:, centre]).any())))
                    shifts[f"det{thr}"] = d_c[c_live] + OUTAGE * REGION[pk[j], c_live]
                else:
                    shifts[f"det{thr}"] = shifts["base"]
            for arm, used in shifts.items():
                v, n = value(at_list[j], list_[j], cost[j], used, truth[j])
                total[arm][where][0] += v
                total[arm][where][1] += n
        finals[d] = newton(z[i], won[i], np.ones((len(i), 1)))[0]

    # Each quote with the dealer's earlier answers, for the fit of the competitor's reaction.
    rows, seen_d = [], {}
    for k, r in enumerate(q):
        hist = seen_d.setdefault(dealers[k], [])
        before = [(dd, ww) for dd, ww in hist if dd < day[k]]
        yesterday = [ww for dd, ww in before if dd == day[k] - 1]
        today = [ww for dd, ww in hist if dd == day[k]]
        rows.append((z[k] + SLOPE * truth[k], won[k], len(before), sum(ww for _, ww in before), len(yesterday), sum(yesterday), len(today), sum(today), int(day[k]),
                     at_list[k], list_[k], cost[k], truth[k], r["trust"]))
        hist.append((int(day[k]), won[k]))
    return {"seed": w["week"]["seed"], "out_day": out_day, "centre": PLACES[centre], "top": top, "other": other, "identified": identified, "delta": float(delta),
            "n_in": float(h["n"][centre]), "wins_in": float(h["wins"][centre]), "n_day": len(h["i"]), "llr_dl": float(h["llr_dl"]), "war_day": war_day,
            "war_depth": float(levels[war_day] - median), "war_seen_at": war_seen_at, "levels": [levels.get(d, np.nan) for d in range(5)], "total": total, "flags": flags, "rows": rows}


def main() -> None:
    variant = sys.argv[1] if len(sys.argv) > 1 else "steep-notes-offers-8"
    weeks = load(variant)
    with multiprocessing.Pool(3) as pool:
        results = pool.map(week, weeks, chunksize=8)
    n = len(results)
    r = pd.DataFrame([{k: v for k, v in x.items() if k not in ("total", "flags", "rows", "levels")} for x in results])
    print(f"{variant}: {n} weeks\n\nTHE OUTAGE")
    print(f"best LLR of the week: quantiles {r.top.quantile([.05, .1, .25, .5, .75, .9]).round(1).to_dict()}; best LLR on any other day: {r.other.quantile([.5, .75, .9, .95, .99]).round(1).to_dict()}")
    print(f"identified (LLR 6 or more, 3 above every other day): {r.identified.mean():.0%} of weeks. By day: {r[r.identified].out_day.value_counts().sort_index().to_dict()}; same day as the price war: {(r[r.identified].out_day == r[r.identified].war_day).mean():.1%}")
    idn = r[r.identified]
    print(f"in the identified weeks: {idn.n_in.mean():.0f} quotes in the region that day of {idn.n_day.mean():.0f} ({idn.n_in.quantile([.1, .5, .9]).round(0).to_dict()}), won {idn.wins_in.sum() / idn.n_in.sum():.0%}; "
          f"fitted extra shift median {idn.delta.median():.3f} (the rules: {OUTAGE:.3f}); the same LLR by delivery place is higher in {(idn.llr_dl > idn.top).mean():.0%}")
    print(f"centres: {idn.centre.value_counts().head(8).to_dict()}")
    print(f"not identified: {len(r) - len(idn)} weeks, with {r[~r.identified].n_in.median():.0f} quotes in the best region (median)")

    def per_week(arm: str, where: str) -> tuple[float, float]:
        return (sum(x["total"][arm][where][0] - x["total"]["base"][where][0] for x in results) / n, sum(x["total"][arm][where][1] - x["total"]["base"][where][1] for x in results) / n)

    print(f"\nreplay, euros of objective a week against the policy's day shift (orders a week):")
    print(f"  knows the outage region and every day's shift from 08:00: outage days {per_week('oracle', 'out')[0]:+.0f} ({per_week('oracle', 'out')[1]:+.1f}), other days {per_week('oracle', 'other')[0]:+.0f} ({per_week('oracle', 'other')[1]:+.1f})")
    for thr in THRESHOLDS:
        flags = [(x["seed"], *f) for x in results for f in x["flags"][thr]]
        true = [f for f in flags if f[3]]
        times = sorted(f[2] for f in true)
        med = times[len(times) // 2] if times else 0
        gain, loss = per_week(f"det{thr}", "out"), per_week(f"det{thr}", "other")
        print(f"  detector at LLR {thr}: flags the outage in {len(true) / max(len(idn), 1):.0%} of the identified weeks, at {med // 60:02d}:{med % 60:02d} in the median "
              f"(quartiles {times[len(times) // 4] // 60:02d}:{times[len(times) // 4] % 60:02d} to {times[3 * len(times) // 4] // 60:02d}:{times[3 * len(times) // 4] % 60:02d}); "
              f"other flags {(len(flags) - len(true)) / n:.2f} a week; outage days {gain[0]:+.0f} ({gain[1]:+.1f}), other days {loss[0]:+.0f} ({loss[1]:+.1f}), net {gain[0] + loss[0]:+.0f}")

    print("\nTHE PRICE WAR")
    print(f"lowest day of the week against the week's median: depth median {r.war_depth.median():.3f}, under -0.12 in {(r.war_depth <= -0.12).mean():.0%} of weeks")
    war = r[r.war_depth <= -0.12]
    counts = war.war_day.value_counts().sort_index()
    left = len(war)
    for d in range(5):
        c = int(counts.get(d, 0))
        print(f"  {['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'][d]}: {c / len(war):.0%} of weeks; given none before, {c / max(left, 1):.0%}")
        left -= c
    seen = war.war_seen_at.dropna()
    print(f"the day's shift is 0.12 under the week so far, with 5 answers or more, by {int(seen.median()) // 60:02d}:{int(seen.median()) % 60:02d} in the median ({len(seen) / len(war):.0%} of war days)")
    for arm, name in (("friday", "Friday starts at the week's level less 0.22 when no day was low before"), ("carry", "the same, and each day after the war starts at the week's level")):
        g = per_week(arm, "out")[0] + per_week(arm, "other")[0]
        print(f"  {name}: {g:+.0f} euros a week")

    print("\nTHE DEALER'S EARLIER ANSWERS")
    rows = np.array([row for x in results for row in x["rows"]])
    off, won, nb, wb, ny, wy, nt, wt, day = (rows[:, k] for k in range(9))
    share = np.where(nb >= 5, wb / np.maximum(nb, 1), np.nan)
    resid = won - sig(off)
    t = pd.DataFrame({"share": share, "resid": resid, "won": won, "fitted": sig(off)})
    print("win share at the dealer on earlier days (5 answers or more), against today's answers:")
    print(t.groupby(pd.cut(t.share, [-0.01, 0.1, 0.2, 0.3, 0.4, 0.5, 0.7, 1.0])).agg(quotes_a_week=("won", lambda s: len(s) / n), fitted=("fitted", "mean"), won=("won", "mean")).round(3).to_string())
    x = np.c_[np.ones(len(off)), np.where(nb >= 5, share - 0.3, 0.0), nb >= 5, np.where(nt >= 3, wt / np.maximum(nt, 1) - 0.3, 0.0)].astype(float)
    beta = np.zeros(x.shape[1])
    for _ in range(20):
        p = sig(off + x @ beta)
        hess = (x * (p * (1 - p))[:, None]).T @ x
        beta = beta + np.linalg.solve(hess, x.T @ (won - p))
    se = np.sqrt(np.diag(np.linalg.inv(hess)))
    for name, b, s in zip(("intercept", "earlier win share, per unit", "has 5 earlier answers", "today's win share so far at the dealer (3 or more), per unit"), beta, se):
        print(f"  {name}: {b:+.3f} log odds (se {s:.3f}), {b / SLOPE:+.4f} in log price")
    at_list, list_, cost, truth = rows[:, 9], rows[:, 10], rows[:, 11], rows[:, 12]
    adj = (x[:, 1:3] @ beta[1:3]) / SLOPE
    base_v, _ = value(at_list, list_, cost, truth, truth + adj)
    know_v, know_n = value(at_list, list_, cost, truth + adj, truth + adj)
    print(f"  replay: pricing with the dealer's earlier win share, when the day's shift is known, is worth {(know_v - base_v) / n:+.0f} euros a week")
    full = (x[:, 1:] @ beta[1:]) / SLOPE
    base_v, _ = value(at_list, list_, cost, truth, truth + full)
    know_v, _ = value(at_list, list_, cost, truth + full, truth + full)
    print(f"  replay: the same with today's win share so far at the dealer too: {(know_v - base_v) / n:+.0f} euros a week")


if __name__ == "__main__":
    main()
