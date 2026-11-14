"""Scratch: what the per-dealer estimate is worth in euros, in a closed loop on the archived weeks.

    PYTHONPATH=. uv run --with numpy python scratch/dealer_sim.py [weeks]

The archive cannot price a change of quotes: its answers are to the prices it quoted. So each held-out week of the
reference is played again quote by quote with its own requests (the one-car dealer requests it quoted), and a dealer
answers by a known truth: the curve (curve-day.json) shifted by the day's level, which is the week's hindsight shift of
that day (its day factor and its price war), plus the dealer's own offset. Truth `archive` takes the dealer's Monday
offset from the week's hindsight fit; truth `synthetic` draws it from N(0, 0.035^2), the spread the archive shows. Each
morning a dealer's offset moves by -0.05 x (our win share there the day before - 0.3), the competitor's cut where we
win most (scratch/dealer_truth.py), and by N(0, 0.01^2). The dealer's count of orders on time follows the desk's own
wins: each win counts a day later, on time with chance 0.955, and a late one halves the count.

The desk prices with curve.best at a cost of 1.2 x the typical fee plus 6.75 euros (the default's cost and its
late_cost at a 4.5% late chance). The arms differ only in the shift they price with. Every arm of a week uses the same
random numbers, so differences are paired. Margins are in euros a week over these requests only (about 85% of quotes).
"""
from __future__ import annotations

import json, math, os, sys, zlib
from multiprocessing import Pool

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dealer_filter as f

SLOPE, TRUST = f.SLOPE, 13.7583
MULTS = np.round(np.arange(1.0, 2.4001, 0.02), 2)
LOGM = np.log(MULTS)
REACT, WALK, BASE_SHARE, TRUE_SD = -0.05, 0.01, 0.3, 0.035
ON_TIME, DELIVERY = 0.955, 1440


def best(z, shift, list_, cost):
    p = f.sig(z - SLOPE * (LOGM - shift))
    return int(np.argmax((MULTS * list_ - cost) * p))


def run(week, truth, arm, rng_seed):
    """One week under one arm. arm: dict(sd, drift, prior: dealer->mean, probe: Thompson draws while posterior sd > this)."""
    week = sorted(week, key=lambda r: r["at"])
    rng = np.random.default_rng(rng_seed)
    n = len(week)
    u_win, u_late, u_probe = rng.random(n), rng.random(n), rng.standard_normal(n)
    names = sorted({r["dealer"] for r in week}); idx = {d: i for i, d in enumerate(names)}; nd = len(names)
    dl = np.array([idx[r["dealer"]] for r in week]); day = np.array([r["day"] for r in week])
    at = np.array([r["at"] for r in week]); ans = np.array([r["answered"] for r in week])
    zb = np.array([r["z"] - TRUST * math.log(1 + 0.01 * r["trust"]) for r in week])
    lst = np.array([r["list"] for r in week], float); cost = np.array([1.2 * r["fee"] + 675 for r in week])
    # truth
    D_true, o0 = truth["D"], np.array([truth["o"].get(d, 0.0) for d in names])
    walk = np.random.default_rng(rng_seed + 1).normal(0, WALK, (7, nd))
    o_true = o0.copy()
    # desk
    sd, drift = arm["sd"], arm["drift"]
    m = np.array([arm.get("prior", {}).get(d, 0.0) for d in names]); v = np.full(nd, max(sd, 1e-6) ** 2)
    trust, pending = np.zeros(nd), []  # pending: (minute, dealer, on time)
    x = np.zeros(n); won = np.zeros(n); price = np.zeros(n); oh = np.zeros(n); ot = np.zeros(n)
    cur, cache, asked_today, won_today = -1, {}, np.zeros(nd), np.zeros(nd)
    for i in range(n):
        if day[i] != cur:
            if cur >= 0:
                if sd:
                    sel = day == cur
                    _, o, h = f.joint(zb[sel] + TRUST * np.log1p(0.01 * tz[sel]), x[sel], won[sel], dl[sel], m, v, f.LEARN)
                    m, v = o, 1 / (1 / v + h) + drift ** 2
                share = np.where(asked_today > 0, won_today / np.maximum(asked_today, 1), BASE_SHARE)
                o_true = o_true + REACT * (share - BASE_SHARE) + walk[day[i]]
            cur, cache, asked_today, won_today = day[i], {}, np.zeros(nd), np.zeros(nd)
            tz = np.zeros(n)
        while pending and pending[0][0] <= at[i]:
            _, d, ok = pending.pop(0)
            trust[d] = min(25, trust[d] + 1) if ok else trust[d] // 2
        tz[i] = trust[dl[i]]
        z = zb[i] + TRUST * math.log(1 + 0.01 * trust[dl[i]])
        sel = (day == cur) & (ans <= at[i]) & (np.arange(n) < i)
        key = int(sel.sum())
        if key not in cache:
            if key == 0:
                cache[key] = (0.0, m.copy())
            else:
                zs = zb[sel] + TRUST * np.log1p(0.01 * tz[sel])
                D, o, _ = f.joint(zs, x[sel], won[sel], dl[sel], m, v if sd else np.full(nd, 1e-12), f.LEARN)
                cache[key] = (D, o)
        D, o = cache[key]
        od = o[dl[i]]
        if arm.get("probe") and sd and math.sqrt(v[dl[i]]) > arm["probe"]:
            od += math.sqrt(v[dl[i]]) * u_probe[i]
        k = best(z, D + od, lst[i], cost[i])
        x[i], price[i] = LOGM[k], MULTS[k] * lst[i]
        oh[i], ot[i] = D + o[dl[i]], D_true[cur] + o_true[dl[i]]  # the dealer's whole threshold today, as estimated and true
        p_true = f.sig(z - SLOPE * (x[i] - D_true[cur] - o_true[dl[i]]))
        won[i] = float(u_win[i] < p_true)
        asked_today[dl[i]] += 1; won_today[dl[i]] += won[i]
        if won[i]:
            pending.append((ans[i] + DELIVERY, dl[i], u_late[i] < ON_TIME)); pending.sort()
    margin = won * (price - cost) / 100
    return dict(margin=margin, won=won, day=day, dealer=dl, oh=oh, ot=ot, trust=trust, names=names)


def truths(week, kind, seed):
    o, D = f.hindsight(week, dealer_sd=TRUE_SD)
    if kind == "archive":
        return dict(D=D, o={d: v[0] for d, v in o.items()})
    rng = np.random.default_rng(seed)
    return dict(D=D, o={d: rng.normal(0, TRUE_SD) for d in sorted(o)})


def one(args):
    seed, week, arms, kind = args
    truth = truths(week, kind, zlib.crc32(seed.encode()))
    top = f.top3(week)
    rs = zlib.crc32(f"{seed} {kind}".encode())
    out = {}
    for name, arm in arms.items():
        arm = dict(arm)
        if arm.get("prior") == "top3+":
            arm["prior"] = {d: 0.05 for d in top}
        elif arm.get("prior") == "top3-":
            arm["prior"] = {d: -0.05 for d in top}
        r = run(week, truth, arm, rs)
        t3 = np.array([r["names"][d] in top for d in r["dealer"]])
        early = t3 & (r["day"] <= 1)
        err = r["oh"] - r["ot"]
        war = int(np.argmin(truth["D"][:5])) if truth["D"][:5].min() < -0.12 else -1
        on_war, after = r["day"] == war, r["day"] == war + 1
        out[name] = dict(margin=float(r["margin"].sum()), orders=float(r["won"].sum()),
                         early_margin=float(r["margin"][early].sum()), early_orders=float(r["won"][early].sum()),
                         top3_orders=float(r["won"][t3].sum()), top3_margin=float(r["margin"][t3].sum()),
                         top3_trust=float(sum(r["trust"][r["names"].index(d)] for d in top)),
                         bias_top3_mt=float(err[early].mean()) if early.any() else 0.0, rmse_top3_mt=float(np.sqrt((err[early] ** 2).mean())) if early.any() else 0.0,
                         bias_all=float(err.mean()), rmse_all=float(np.sqrt((err ** 2).mean())),
                         war=war >= 0, bias_war=float(err[on_war].mean()) if on_war.any() else 0.0, bias_after=float(err[after].mean()) if after.any() else 0.0,
                         rmse_war=float(np.sqrt((err[on_war] ** 2).mean())) if on_war.any() else 0.0, rmse_after=float(np.sqrt((err[after] ** 2).mean())) if after.any() else 0.0)
    return seed, kind, out


ARMS = {
    "day": dict(sd=0, drift=0),
    "dealer": dict(sd=0.015, drift=0.02),
    "dealer-wide": dict(sd=0.035, drift=0.02),
    "dealer-probe": dict(sd=0.015, drift=0.02, probe=0.015),
    "dealer-wrong-high": dict(sd=0.015, drift=0.02, prior="top3+"),
    "dealer-wrong-low": dict(sd=0.015, drift=0.02, prior="top3-"),
}

if __name__ == "__main__":
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 10**6
    weeks = f.load("steep-notes-offers-8")
    seeds = [s for s in sorted(weeks) if f.split(s) == "holdout"][:count]
    jobs = [(s, weeks[s], ARMS, kind) for kind in ("archive", "synthetic") for s in seeds]
    with Pool(os.cpu_count()) as pool:
        res = pool.map(one, jobs, chunksize=2)
    json.dump(res, open(f.data_dir() / "dealer_sim-results.json", "w"))
    for kind in ("archive", "synthetic"):
        rows = [o for s, k, o in res if k == kind]
        print(f"\ntruth {kind}: {len(rows)} weeks. Euros a week against `day`, 95% interval; top3 Mon-Tue is the top three dealers' quotes on Monday and Tuesday")
        for name in ARMS:
            d = f.boot([r[name]["margin"] - r["day"]["margin"] for r in rows])
            e = f.boot([r[name]["early_margin"] - r["day"]["early_margin"] for r in rows])
            g = lambda key: np.mean([r[name][key] for r in rows])
            print(f"  {name:18s} margin {g('margin'):7.0f} {d[0]:+6.0f} ({d[1]:+.0f} to {d[2]:+.0f})  top3 Mon-Tue {g('early_margin'):6.0f} {e[0]:+5.0f} ({e[1]:+.0f} to {e[2]:+.0f})"
                  f"  orders {g('orders'):5.1f} top3 {g('top3_orders'):5.1f} Mon-Tue {g('early_orders'):5.1f}  top3 trust {g('top3_trust'):4.1f}"
                  f"  threshold error top3 Mon-Tue bias {g('bias_top3_mt'):+.4f} rmse {g('rmse_top3_mt'):.4f}, all {g('bias_all'):+.4f} {g('rmse_all'):.4f}")
        for name in ARMS:
            w = [r[name] for r in rows if r[name]["war"]]
            h = lambda key: np.mean([x[key] for x in w])
            print(f"  {name:18s} {len(w)} weeks with a price-war day: error on it bias {h('bias_war'):+.4f} rmse {h('rmse_war'):.4f}; day after bias {h('bias_after'):+.4f} rmse {h('rmse_after'):.4f}")
