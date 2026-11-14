"""Scratch: does a per-dealer estimate of the price a dealer accepts this week predict its answers better than the
day's shift alone (curve.shift)? Rows from scratch/dealer_rows.py.

    PYTHONPATH=. uv run --with numpy python scratch/dealer_filter.py [prior sds] [drifts]   # e.g. 0.01,0.015,0.02 0.01,0.02

Each week is read in time order; an answer counts from the minute it came. Before each quote the curve is shifted by
- `day`: today's shift alone, as the policy does (prior sd `learn`, new each morning);
- `joint`: today's shift and an offset for each dealer, fitted together on today's answers (each answer is counted once,
  in one likelihood). Each dealer's offset has a normal prior: N(0, dealer_sd^2) on Monday, and each later morning the
  posterior of the day before with `drift`^2 added to its variance, so it never locks in. A dealer's update is a
  Kalman-like step: large while its variance is large, smaller as its answers build up. A dealer with few answers stays
  near 0, the market's level.
An answer is censored: a sale says only that the dealer's price is above the quote, a loss that it is below; with the
curve's logistic noise its likelihood is the curve's chance itself.
"""
from __future__ import annotations

import json, math, os, sys
from multiprocessing import Pool

import numpy as np

from spreadlab.server import data_dir

HERE = os.path.dirname(os.path.abspath(__file__))
SLOPE = 12.5405  # curve-day.json
LEARN = 0.16


def sig(v):
    return 1 / (1 + np.exp(-v))


def joint(z, x, won, dealer, prior_m, prior_v, learn, sweeps=4):
    """MAP of today's shift D and each dealer's offset o (dealer index array), with priors N(0, learn^2) and N(prior_m, prior_v).
    Returns D, o (all dealers) and the curvature of each dealer's likelihood today."""
    D, o = 0.0, prior_m.copy()
    n = len(prior_m)
    for _ in range(sweeps):
        for _ in range(2):
            p = sig(z - SLOPE * (x - D - o[dealer]))
            g = SLOPE * np.sum(won - p) - D / learn**2
            h = SLOPE**2 * np.sum(p * (1 - p)) + 1 / learn**2
            D += float(np.clip(g / h, -0.3, 0.3))
        p = sig(z - SLOPE * (x - D - o[dealer]))
        g = SLOPE * np.bincount(dealer, won - p, n) - (o - prior_m) / prior_v
        h = SLOPE**2 * np.bincount(dealer, p * (1 - p), n) + 1 / prior_v
        o += np.clip(g / h, -0.3, 0.3)
    p = sig(z - SLOPE * (x - D - o[dealer]))
    return D, o, SLOPE**2 * np.bincount(dealer, p * (1 - p), n)


def play(week, dealer_sd, drift, learn=LEARN, prior_mean=None):
    """The chance of each quote of one week in time order, and the dealer's offset the desk had at the quote.
    dealer_sd 0 is the day's shift alone. prior_mean: dealer -> a wrong starting offset, for the robustness check."""
    week = sorted(week, key=lambda r: r["at"])
    names = sorted({r["dealer"] for r in week})
    index = {d: i for i, d in enumerate(names)}
    z = np.array([r["z"] for r in week]); x = np.array([r["x"] for r in week]); won = np.array([float(r["won"]) for r in week])
    dl = np.array([index[r["dealer"]] for r in week]); at = np.array([r["at"] for r in week]); ans = np.array([r["answered"] for r in week])
    day = at // 1440
    m = np.zeros(len(names)) if prior_mean is None else np.array([prior_mean.get(d, 0.0) for d in names])
    v = np.full(len(names), max(dealer_sd, 1e-9) ** 2)
    out, est, shift = np.zeros(len(week)), np.zeros(len(week)), np.zeros(len(week))
    cur_day, cache = -1, {}
    for i in range(len(week)):
        if day[i] != cur_day:
            if cur_day >= 0 and dealer_sd:  # the day's answers become the dealers' prior for tomorrow, plus drift
                sel = (day == cur_day)
                D, o, h = joint(z[sel], x[sel], won[sel], dl[sel], m, v, learn)
                m, v = o, 1 / (1 / v + h) + drift**2
            cur_day, cache = day[i], {}
        sel = (day == cur_day) & (ans <= at[i])
        key = int(sel.sum())
        if key not in cache:
            if key == 0:
                cache[key] = (0.0, m.copy())
            elif dealer_sd:
                D, o, _ = joint(z[sel], x[sel], won[sel], dl[sel], m, v, learn)
                cache[key] = (D, o)
            else:
                D, o, _ = joint(z[sel], x[sel], won[sel], dl[sel], m, np.full(len(names), 1e-12), learn)
                cache[key] = (D, o)
        D, o = cache[key]
        shift[i], est[i] = D, o[dl[i]]
        out[i] = sig(z[i] - SLOPE * (x[i] - D - o[dl[i]]))
    return week, out, est, shift


def hindsight(week, dealer_sd=0.3, learn=LEARN):
    """The whole week at once: a shift for each day and one offset for each dealer, from every answer of the week.
    The nearest the archive comes to a true threshold: the reveal does not show one."""
    names = sorted({r["dealer"] for r in week}); index = {d: i for i, d in enumerate(names)}
    z = np.array([r["z"] for r in week]); x = np.array([r["x"] for r in week]); won = np.array([float(r["won"]) for r in week])
    dl = np.array([index[r["dealer"]] for r in week]); day = np.array([r["at"] // 1440 for r in week])
    D, o = np.zeros(7), np.zeros(len(names))
    for _ in range(30):
        p = sig(z - SLOPE * (x - D[day] - o[dl]))
        D += np.clip((SLOPE * np.bincount(day, won - p, 7) - D / learn**2) / (SLOPE**2 * np.bincount(day, p * (1 - p), 7) + 1 / learn**2), -0.3, 0.3)
        p = sig(z - SLOPE * (x - D[day] - o[dl]))
        h = SLOPE**2 * np.bincount(dl, p * (1 - p), len(names))
        o += np.clip((SLOPE * np.bincount(dl, won - p, len(names)) - o / dealer_sd**2) / (h + 1 / dealer_sd**2), -0.3, 0.3)
    p = sig(z - SLOPE * (x - D[day] - o[dl]))
    h = SLOPE**2 * np.bincount(dl, p * (1 - p), len(names))
    return {d: (o[index[d]], 1 / (h[index[d]] + 1 / dealer_sd**2), int((dl == index[d]).sum())) for d in names}, D


def loss(p, y):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def load(variant):
    rows = json.load(open(data_dir() / f"dealer_rows-{variant}.json"))
    weeks = {}
    for r in rows:
        weeks.setdefault(r["seed"], []).append(r)
    return weeks


def split(seed):
    """tune: the catalogue's tune list and the random-price weeks; holdout: the holdout list and the fresh seeds."""
    tune = set(json.load(open(os.path.join(HERE, "..", "catalogue", "seeds.json")))["tune"])
    return "tune" if seed in tune or seed.startswith("explore") else "holdout"


def top3(week):
    count = {}
    for r in week:
        count[r["dealer"]] = count.get(r["dealer"], 0) + 1
    return set(sorted(count, key=count.get, reverse=True)[:3])


def boot(diffs, n=10000, seed=0):
    rng = np.random.default_rng(seed)
    d = np.array(diffs)
    means = rng.choice(d, (n, len(d))).mean(axis=1)
    return d.mean(), np.percentile(means, 2.5), np.percentile(means, 97.5)


def score(args):
    week, configs = args
    top = top3(week)
    res = {}
    for name, (sd, drift) in configs.items():
        w, p, est, _ = play(week, sd, drift)
        y = np.array([float(r["won"]) for r in w])
        l = loss(p, y)
        early = np.array([r["day"] in (0, 1) and r["dealer"] in top for r in w])
        res[name] = (l.sum(), len(l), l[early].sum(), int(early.sum()))
    return week[0]["seed"], res


if __name__ == "__main__":
    configs = {"day": (0, 0)}
    sds = [float(v) for v in sys.argv[1].split(",")] if len(sys.argv) > 1 else (0.02, 0.04, 0.06, 0.10)
    drifts = [float(v) for v in sys.argv[2].split(",")] if len(sys.argv) > 2 else (0, 0.02, 0.04)
    for sd in sds:
        for drift in drifts:
            configs[f"sd {sd} drift {drift}"] = (sd, drift)
    weeks = {**load("explore"), **load("steep-notes-offers-8")}
    with Pool(os.cpu_count()) as pool:
        results = dict(pool.map(score, [(w, configs) for w in weeks.values()]))
    json.dump(results, open(data_dir() / "dealer_filter-results.json", "w"))
    for part in ("tune", "holdout"):
        seeds = [s for s in results if split(s) == part]
        print(f"\n{part}: {len(seeds)} weeks. Log loss over all quotes, and over the top three dealers' quotes on Monday and Tuesday;")
        print("the difference to `day` a week (negative is better) with its 95% interval")
        for name in configs:
            all_ = sum(results[s][name][0] for s in seeds) / sum(results[s][name][1] for s in seeds)
            ear = sum(results[s][name][2] for s in seeds) / sum(results[s][name][3] for s in seeds)
            d = boot([results[s][name][0] / results[s][name][1] - results[s]["day"][0] / results[s]["day"][1] for s in seeds])
            e = boot([(results[s][name][2] - results[s]["day"][2]) / max(results[s][name][3], 1) for s in seeds])
            print(f"  {name:22s} {all_:.4f}  {ear:.4f}   all {d[0]*1000:+.2f} ({d[1]*1000:+.2f} to {d[2]*1000:+.2f}) e-3"
                  f"   top3 Mon-Tue {e[0]*1000:+.2f} ({e[1]*1000:+.2f} to {e[2]*1000:+.2f}) e-3")
