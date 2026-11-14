"""Scratch: the fit of `need` (spreadlab/exposure.py), the chance that a car which needs a driver now ends late, on the rows of book_rows.py.

One row per one-car order at its win and at each drop of its gig. A logistic with an intercept for each band of hours left to the last
pickup (from that minute), slow.py's other terms without the Friday ones, whether a driver dropped the car, and the live load:
ln(1 + waiting cars due the same day per 100 listed drivers) and the same for the waiting cars due on other days. Each week has its own
intercept (normal prior, sd 0.5) from its rows that are not due on its flu day, fitted in turn with the weights, so that the load
weight does not stand for a bad week and the intercept does not take up the flu day. Beside the wins and drops, the cars that wait for a
driver in the books at 20:00 and 01:00 (book_rows.py) are rows too, with how long each has waited. Fitted on the
seeds `cat-*` and `fresh-001` to `fresh-1201`; `fresh-1301` to `fresh-1460` are left out for the checks.

    PYTHONPATH=. uv run --with numpy python scratch/exposure/need_fit.py [all]     # `all` fits on every week, to show what moves

Prints the weights (as exposure.json wants them) and the measured tables beside the fit's mean on the rows left out.
"""
from __future__ import annotations

import json
import math
import pickle
import sys

import numpy as np

from spreadlab import exposure
from spreadlab.server import data_dir

VARIANTS = ["slow-friday-late-150-kinds-limits", "steep-notes-offers-8", "thin-premium-0.4"]


def held_out(seed: str) -> bool:
    return seed.startswith("fresh-") and 1301 <= int(seed.split("-")[1]) <= 1460


def waves(w: dict) -> set[int]:
    """The days whose night was the flu day's, by the night's likelihood ratio (exposure.ratio)."""
    nights = w["snaps"][-1]["nights"]
    return {d for d, (held, dropped) in nights.items() if exposure.ratio(held, dropped) > 1}


def flu(r: dict, wave: set[int]) -> bool:
    return r["due"] in wave and r["at"] >= r["due"] * 1440


def matrix(rows: list[tuple[dict, set]]) -> np.ndarray:
    return np.array([exposure.terms(r["hours"], r, r["dropped"], r["same"], r["other"], r["drivers"], flu(r, wave), exposure.night(r["at"]), r.get("waited", 0.0),
                                    exposure.daylight(r["at"], r["last"])) for r, wave in rows], float)


def waiting_rows(w: dict) -> list[dict]:
    """Rows for the cars that wait for a driver in the books at 20:00 and 01:00: how long each has waited since its win or its last drop."""
    by_order, feats, out = {}, {}, []
    for r in w["rows"]:
        by_order.setdefault(r["order"], []).append(r["at"])
        feats.setdefault(r["order"], r)
    for s in w["snaps"]:
        unheld = [(oid, due, hours) for oid, due, held, hours, picked in s["cars"] if not held and not picked and hours > 0 and oid in feats]
        for oid, due, hours in unheld:
            since = max(t for t in by_order[oid] if t <= s["at"])
            same = sum(1 for o, d, _ in unheld if d == due and o != oid)
            out.append({**feats[oid], "at": s["at"], "due": due, "hours": hours, "dropped": False, "same": same, "other": len(unheld) - 1 - same,
                        "waited": (s["at"] - since) / 60})
    return out


def fit(X: np.ndarray, y: np.ndarray, week: np.ndarray, weeks: int, own: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """The weights, and each week's intercept from its rows `own` only (not the flu day's), so that the intercept does not take up the flu day."""
    beta, eff = np.zeros(X.shape[1]), np.zeros(weeks)
    beta[:6] = [-1.0, -2.0, -3.0, -3.0, -4.0, -4.8]
    for _ in range(12):
        off = eff[week]
        for _ in range(6):
            p = 1 / (1 + np.exp(-(X @ beta + off)))
            beta += np.clip(np.linalg.solve(X.T @ (X * (p * (1 - p))[:, None]) + 1e-2 * np.eye(len(beta)), X.T @ (y - p) - 1e-2 * beta), -1, 1)
        z = X @ beta
        for _ in range(4):
            p = 1 / (1 + np.exp(-(z + eff[week])))
            g = np.bincount(week, (y - p) * own, weeks) - eff / 0.25
            h = np.bincount(week, p * (1 - p) * own, weeks) + 1 / 0.25
            eff += g / h
    z, c = X @ beta, 0.0  # the level of a week the desk knows nothing about: the bands give the training rows' late share without intercepts
    for _ in range(20):
        p = 1 / (1 + np.exp(-(z + c)))
        c += (y - p).sum() / (p * (1 - p)).sum()
    beta[:6] += c
    return beta, eff


def main() -> None:
    every = len(sys.argv) > 1 and sys.argv[1] == "all"
    train, test = [], []
    for v in VARIANTS:
        for w in pickle.load(open(data_dir() / "exposure" / f"book-{v}.pkl", "rb")):
            (test if held_out(w["seed"]) and not every else train).append(w)
            if every and held_out(w["seed"]):
                test.append(w)
    rows = [(i, r, waves(w)) for i, w in enumerate(train) for r in w["rows"] + waiting_rows(w) if r["hours"] >= 0]
    X, y, week = matrix([(r, wv) for _, r, wv in rows]), np.array([r["late"] for _, r, _ in rows], float), np.array([i for i, _, _ in rows])
    beta, eff = fit(X, y, week, len(train), np.array([r["due"] not in wv for _, r, wv in rows], float))
    # the chance that a car without a driver has one when the night of its due day begins, by hours to that night (exposure.by_night)
    held = []
    for w in train:
        snaps = {s["at"]: s for s in w["snaps"]}
        drops = {(r["order"], r["at"] // 1440) for r in w["rows"] if r["dropped"] and r["at"] % 1440 < 60}
        for s in w["snaps"]:
            for oid, due, h, hours, picked in s["cars"]:
                night = snaps.get(due * 1440 + 60)
                if h or picked or night is None or due * 1440 <= s["at"]:
                    continue
                later = {o: hh for o, _, hh, _, _ in night["cars"]}
                if oid in later:
                    held.append(((due * 1440 - s["at"]) / 60, later[oid] or (oid, due) in drops))
    H = np.array(held, float)
    print("held by the night of the due day, by hours to it: " + "  ".join(
        f"<{b}h {H[(H[:, 0] >= a) & (H[:, 0] < b), 1].mean():.2f} ({int(((H[:, 0] >= a) & (H[:, 0] < b)).sum())})" for a, b in ((0, 6), (6, 18), (18, 30), (30, 54), (54, 999))))
    print(f"fit on {len(train)} weeks, {len(rows)} rows ({'every week' if every else 'without fresh-1301 to 1460'}); week intercepts sd {eff.std():.2f}")
    print(json.dumps({"names": exposure.TERMS, "weights": [round(float(b), 3) for b in beta]}))
    for name, b in zip(exposure.TERMS, beta):
        print(f"  {name:48} {b:+.3f}")
    trw = [(r, waves(w)) for w in test for r in w["rows"] + waiting_rows(w) if r["hours"] >= 0]
    tr = [r for r, _ in trw]
    Xt, yt = matrix(trw), np.array([r["late"] for r in tr], float)
    pt = 1 / (1 + np.exp(-(Xt @ beta)))
    order = np.argsort(pt); auc = (np.argsort(order)[yt == 1].mean() - (yt.sum() - 1) / 2) / (len(yt) - yt.sum()) if 0 < yt.sum() < len(yt) else float("nan")
    loss = -np.mean(yt * np.log(np.clip(pt, 1e-9, 1)) + (1 - yt) * np.log(np.clip(1 - pt, 1e-9, 1)))
    print(f"\nrows left out: {len(tr)} of {len(test)} weeks; late {yt.mean():.3f}, fit {pt.mean():.3f}; AUC {auc:.3f}; log loss {loss:.5f}")
    hours = np.array([r["hours"] for r in tr]); drop = np.array([r["dropped"] for r in tr]); same = np.array([r["same"] for r in tr])
    bands = [(0, 2), (2, 4), (4, 8), (8, 16), (16, 30), (30, 999)]
    for label, keep in (("after a drop", drop == 1), ("at the win", drop == 0)):
        print(f"  {label}, by hours left (late / fit / rows): " + "  ".join(
            f"{a}-{b}h {yt[keep & (hours >= a) & (hours < b)].mean():.2f}/{pt[keep & (hours >= a) & (hours < b)].mean():.2f}/{int((keep & (hours >= a) & (hours < b)).sum())}"
            for a, b in bands if (keep & (hours >= a) & (hours < b)).sum()))
    fl = np.array([flu(r, wv) for r, wv in trw])
    wt = np.array(["waited" in r for r in tr])
    print("  waiting in the books at 20:00 and 01:00, by hours left: " + "  ".join(
        f"{a}-{b}h {yt[wt & (hours >= a) & (hours < b)].mean():.2f}/{pt[wt & (hours >= a) & (hours < b)].mean():.2f}/{int((wt & (hours >= a) & (hours < b)).sum())}"
        for a, b in bands if (wt & (hours >= a) & (hours < b)).sum()))
    print("  on the flu day after its night, by hours left: " + "  ".join(
        f"{a}-{b}h {yt[fl & (hours >= a) & (hours < b)].mean():.2f}/{pt[fl & (hours >= a) & (hours < b)].mean():.2f}/{int((fl & (hours >= a) & (hours < b)).sum())}"
        for a, b in bands if (fl & (hours >= a) & (hours < b)).sum()))
    at = np.array([r["at"] for r in tr]); wavenight = fl & (drop == 1) & (at % 1440 < 60)
    for label, keep in (("all drops", drop == 1), ("drops in a wave night's first hour", wavenight), ("other drops", (drop == 1) & ~wavenight)):
        mid = keep & (hours >= 8) & (hours < 16)
        print(f"  {label}, 8-16 h left, by cars waiting due the same day: " + "  ".join(
            f"{a}-{b}: {yt[mid & (same >= a) & (same < b)].mean():.2f}/{pt[mid & (same >= a) & (same < b)].mean():.2f}/{int((mid & (same >= a) & (same < b)).sum())}"
            for a, b in ((0, 5), (5, 15), (15, 30), (30, 999)) if (mid & (same >= a) & (same < b)).sum()))
        print(f"  {label}, by hours left: " + "  ".join(
            f"{a}-{b}h {yt[keep & (hours >= a) & (hours < b)].mean():.2f}/{pt[keep & (hours >= a) & (hours < b)].mean():.2f}/{int((keep & (hours >= a) & (hours < b)).sum())}"
            for a, b in bands if (keep & (hours >= a) & (hours < b)).sum()))


if __name__ == "__main__":
    main()
