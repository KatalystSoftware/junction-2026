"""Fits the weights of late_wide.py over the won one-car dealer orders of cached weeks (cache.py), checks them on seeds
that the fit did not see, and prints the weights of the fit over every seed.

    uv run --no-project --with numpy python -I scratch/strategy/late_fit.py [--without <seed file>] <cache dir> <map.json> <variant> [...]

The check fits on half of the seeds and reads the other half: how well each chance ranks the late orders (AUC), and
the late share against the chance by band of the chance and by the won cars that waited for a driver at the quote. It
compares three chances: slow.py's `friday` weights as played, those 14 terms with the three for waiting cars, and all
of late_wide.py's terms.

`--without` names a file of seeds, separated by commas or lines. The script then also fits every term over the other seeds
only, prints those weights, and reads both fits on the orders of the named seeds: a variant that is screened on those seeds
with the first weights is judged on orders its late chance was fitted on.
"""
import collections
import glob
import hashlib
import json
import math
import os
import pickle
import sys
from multiprocessing import Pool

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # -I leaves the script's folder off the path
import late_wide  # noqa: E402

WITHOUT = ""
if "--without" in sys.argv:
    WITHOUT = sys.argv.pop(sys.argv.index("--without") + 1)
    sys.argv.remove("--without")
DAY, HOUR = 1440, 60
FRIDAY = [-4.601, 1.803, 1.239, 0.813, 0.392, 0.784, 0.681, 1.539, 0.454, -0.327, 0.437, 0.3, 0.22, 0.715]  # slow.MODELS["friday"]
MAP = json.load(open(sys.argv[2])) if len(sys.argv) > 2 else {"roads": [], "places": []}
MIN = {(r["from"], r["to"]): r["minutes"] for r in MAP["roads"]}
PLACES = {p["id"]: (p["lat"], p["lon"]) for p in MAP["places"]}


def km(a: str, b: str) -> float:
    """The straight line between two places, as spreadlab.server.near_places counts it."""
    (la, lo), (lb, lob) = PLACES[a], PLACES[b]
    lat1, lat2 = math.radians(la), math.radians(lb)
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(math.radians(lob - lo) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


NEAR = {a: [b for b in PLACES if km(a, b) <= 30] for a in PLACES}  # a driver hears of a pickup within 30 km of home


def week(path: str) -> list[dict]:
    w = pickle.load(open(path, "rb"))
    at_home = collections.Counter(d["homePlaceId"] for d in w["roster"])
    notified = {a: sum(at_home[b] for b in NEAR[a]) for a in PLACES}
    requests = {r["request"]["id"]: r for r in w["requests"]}
    order_of = {g["id"]: g["stops"][0]["orderId"] for g in w["gigs"]}
    won, late = {}, set()
    waits = collections.defaultdict(list)  # order -> the spans in which no driver holds its car
    since: dict[str, int | None] = {}
    for e in w["events"]:
        kind = e["kind"]
        if kind == "order_won":
            won[e["order"]["id"]], since[e["order"]["id"]] = e["order"], e["at"]
        elif kind == "ledger":
            if e["line"]["kind"] in ("late_refund", "undelivered_penalty") and e["line"].get("orderId"):
                late.add(e["line"]["orderId"])
        elif kind in ("gig_booked", "gig_dropped", "no_show", "visit_failed", "order_cancelled"):
            order = e.get("orderId") or order_of.get(e.get("gigId"))
            if order not in since:
                continue
            if kind in ("gig_booked", "order_cancelled") and since[order] is not None:
                waits[order].append((since[order], e["at"]))
                since[order] = None
            elif kind in ("gig_dropped", "no_show", "visit_failed") and since[order] is None:
                since[order] = e["at"]
    for order, start in since.items():
        if start is not None:
            waits[order].append((start, 10 ** 9))
    spans = sorted((a, b, won[o].get("lastPickupAt", won[o]["deadline"])) for o, ss in waits.items() for a, b in ss)
    rows = []
    for id_, order in won.items():
        request = requests[id_]["request"]
        leg = request["legs"][0]
        if len(request["legs"]) != 1 or leg["pickup"]["privateAddress"] or leg["delivery"]["privateAddress"]:
            continue
        prices = (w["decisions"].get(id_) or {}).get("prices") or requests[id_].get("quote") or {}
        options = [o for o in request["options"] if o["kind"] in prices] or request["options"]
        drive, at = MIN[(leg["pickup"]["placeId"], leg["delivery"]["placeId"])], request["arrivedAt"]
        waiting_24 = sum(1 for a, b, last in spans if a <= at < b and last - at <= 24 * HOUR)
        waiting_later = sum(1 for a, b, last in spans if a <= at < b and last - at > 24 * HOUR)
        x = late_wide.known(request, options, notified, at_home, drive, len(w["roster"]), waiting_24, waiting_later)
        rows.append({"variant": w["variant"], "seed": w["seed"], "x": x, "late": id_ in late, "waiting": waiting_24 + waiting_later,
                     "exact": late_wide.last_pickup(leg, order["deadline"], drive) == order.get("lastPickupAt")})
    return rows


def fit(x: np.ndarray, y: np.ndarray, ridge: float = 1.0) -> np.ndarray:
    """Logistic regression by Newton's method, with a small penalty on every weight but the intercept."""
    w, penalty = np.zeros(x.shape[1]), ridge * np.eye(x.shape[1])
    penalty[0, 0] = 0
    for _ in range(50):
        p = 1 / (1 + np.exp(-x @ w))
        step = np.linalg.solve((x * (p * (1 - p))[:, None]).T @ x + penalty, x.T @ (y - p) - penalty @ w)
        w += step
        if np.abs(step).max() < 1e-8:
            break
    return w


def auc(p: np.ndarray, y: np.ndarray) -> float:
    order = np.argsort(p, kind="stable")
    ranks = np.empty(len(p))
    ranks[order] = np.arange(1, len(p) + 1)
    pos = y.sum()
    return float((ranks[y == 1].sum() - pos * (pos + 1) / 2) / (pos * (len(y) - pos)))


def family(variant: str) -> str:
    return ("reference" if variant == "steep-notes-offers-8" else "opt" if variant.startswith("opt-") else "search trials" if variant.startswith("s1-")
            else "slow-step, with a late cost" if "late-150" in variant else "slow-step" if variant.startswith("slow-step") else "cheaper backlog, wider gate")


def main() -> None:
    files = [f for v in sys.argv[3:] for f in sorted(glob.glob(f"{sys.argv[1]}/{v}/*.pkl"))]
    with Pool(4) as pool:
        rows = [r for rs in pool.map(week, files, chunksize=8) for r in rs]
    x = np.array([r["x"] for r in rows])
    y = np.array([float(r["late"]) for r in rows])
    waiting = np.array([r["waiting"] for r in rows])
    families = np.array([family(r["variant"]) for r in rows])
    held = np.array([int(hashlib.sha256(r["seed"].encode()).hexdigest(), 16) % 2 == 1 for r in rows])
    print(f"{len(files)} weeks of {len({r['variant'] for r in rows})} variants on {len({r['seed'] for r in rows})} seeds: {len(rows)} orders, {100 * y.mean():.1f}% late")
    print(f"the last pickup minute by the sites' hours is the world's lastPickupAt for {100 * np.mean([r['exact'] for r in rows]):.1f}% of orders")
    n = len(late_wide.NAMES)
    assert x.shape[1] == n
    chances = {"friday, as played": 1 / (1 + np.exp(-x[:, :14] @ np.array(FRIDAY)))}
    for name, terms in (("with waiting cars", 17), ("all terms", n)):
        chances[name] = 1 / (1 + np.exp(-x[:, :terms] @ fit(x[~held][:, :terms], y[~held])))
    print(f"\nFitted on {int((~held).sum())} orders, read on {int(held.sum())} orders of other seeds")
    for name, p in chances.items():
        p_, y_ = np.clip(p[held], 1e-9, 1 - 1e-9), y[held]
        print(f"  {name:20s} AUC {auc(p_, y_):.3f}, log loss {-np.mean(y_ * np.log(p_) + (1 - y_) * np.log(1 - p_)):.4f}, mean chance {100 * p_.mean():.1f}% against {100 * y_.mean():.1f}% late")
    print("\n  AUC by family of variants, on the other seeds: " + ", ".join(chances))
    for f in sorted(set(families)):
        m = held & (families == f)
        if y[m].sum() >= 20:
            print(f"   {f:30s} {int(m.sum()):7d} orders: " + ", ".join(f"{auc(p[m], y[m]):.3f}" for p in chances.values()))
    print("\n  Late share against each chance, by the won cars that waited at the quote, on the other seeds")
    for f in sorted(set(families)):
        for low, high in ((0, 5), (6, 15), (16, 99)):
            m = held & (families == f) & (waiting >= low) & (waiting <= high)
            if m.sum() >= 200:
                print(f"   {f:30s} {low:2d}-{high:2d} cars: {int(m.sum()):7d} orders, {100 * y[m].mean():5.1f}% late | " + ", ".join(f"{100 * p[m].mean():.1f}%" for p in chances.values()))
    print("\n  Late share by band of the chance with all terms, on the other seeds: orders, chance, late; and the friday chance of the same orders")
    p = chances["all terms"]
    for low, high in ((0, .02), (.02, .04), (.04, .07), (.07, .12), (.12, .2), (.2, .35), (.35, 1)):
        m = held & (p >= low) & (p < high)
        if m.sum():
            print(f"   {100 * low:4.0f}-{100 * high:3.0f}%: {int(m.sum()):7d}, {100 * p[m].mean():5.1f}%, {100 * y[m].mean():5.1f}% | friday {100 * chances['friday, as played'][m].mean():5.1f}%")
    moved = held & (np.abs(p - chances["friday, as played"]) >= 0.05)
    up, down = moved & (p > chances["friday, as played"]), moved & (p < chances["friday, as played"])
    weeks = len({(r["variant"], r["seed"]) for r, h in zip(rows, held) if h})
    for name, m in (("up", up), ("down", down)):
        print(f"   moved {name} by 5 points or more: {m.sum() / weeks:.1f} orders a week, {100 * y[m].mean():.1f}% late, friday {100 * chances['friday, as played'][m].mean():.1f}%, all terms {100 * p[m].mean():.1f}%")
    weights = fit(x, y)
    print("\nThe fit over every seed, for late_wide.WEIGHTS:")
    for name, weight in zip(late_wide.NAMES, weights):
        print(f"  {weight:+.3f}  {name}")
    print("WEIGHTS = [" + ", ".join(f"{weight:.3f}" for weight in weights) + "]")
    print("\nThe seeds of the fit:\n" + ",".join(sorted({r["seed"] for r in rows})))
    if WITHOUT:
        left_out = set(open(WITHOUT).read().replace(",", " ").split())
        seeds = np.array([r["seed"] for r in rows])
        out = np.isin(seeds, sorted(left_out))
        print(f"\n{WITHOUT}: {len(left_out & set(seeds))} of its {len(left_out)} seeds are in the fit, with {int(out.sum())} orders ({100 * out.mean():.1f}%), {100 * y[out].mean():.1f}% late")
        without = fit(x[~out], y[~out])
        print("  Read on those orders: AUC, log loss, mean chance")
        for name, w in (("friday, as played", np.array(FRIDAY)), ("all terms, fitted on every seed", weights), ("all terms, fitted without these seeds", without)):
            p_ = np.clip(1 / (1 + np.exp(-x[out][:, :len(w)] @ w)), 1e-9, 1 - 1e-9)
            print(f"   {name:40s} {auc(p_, y[out]):.3f}, {-np.mean(y[out] * np.log(p_) + (1 - y[out]) * np.log(1 - p_)):.4f}, {100 * p_.mean():.2f}%")
        apart = 100 * np.abs(1 / (1 + np.exp(-x[out] @ weights)) - 1 / (1 + np.exp(-x[out] @ without)))
        print(f"  The two fits differ on those orders by {apart.mean():.2f} points of chance on average, {np.percentile(apart, 99):.1f} at the 99th percentile")
        print("  The fit without these seeds:")
        print("WEIGHTS_WITHOUT = [" + ", ".join(f"{weight:.3f}" for weight in without) + "]")


if __name__ == "__main__":
    main()
