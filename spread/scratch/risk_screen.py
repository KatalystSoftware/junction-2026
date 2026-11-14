"""Scratch: an offline screen of driver fee schedules (riskfee.py and others) on the recorded weeks.

A recording cannot score a policy that acts otherwise, so this only says whether a schedule is worth playing. It fits
two models on every saved week, and replays each car of the default's weeks under each schedule:

1. When a waiting car gets its first driver: a logistic hazard for each hour from the posting to the deadline warning
   (3 hours before the last pickup), by the fee shown over the lane's usual fee, the hours on the board, the clock hour,
   the weekday, the hours left, the drivers notified and the car. A request's typical fee is its lane's usual fee times
   noise that drivers do not share, so every week varies the fee drivers see at the same multiple.
2. Whether the order ends late, by the hours left at that first booking and the car's late chance at the posting
   (slow.py); and what a car still without a driver at the warning pays and how often it ends late.

The difference between two schedules on the same cars is read from the models alone, so the models' bias in the level
cancels. The check is the paired weeks at openings 0.9 and 1.0 (`curve-fee-0.9-cost-1.2`, `curve-fee-1.0-cost-1.2`),
left out of the fit. What it cannot see: a car that waits longer counts in the waiting cars of later quotes and in the
gate, and drivers who wait for a raise.

    PYTHONPATH=. uv run --with scikit-learn python scratch/risk_screen.py extract     # data/screen/*.npz, once
    PYTHONPATH=. uv run --with scikit-learn python scratch/risk_screen.py check       # the models against the 0.9 and 1.0 weeks
    PYTHONPATH=. uv run --with scikit-learn python scratch/risk_screen.py screen      # each schedule on the default's weeks
"""
from __future__ import annotations

import collections
import json
import math
import sys
from multiprocessing import Pool

import numpy as np

from spreadlab import policy, slow
from spreadlab.play import load_run
from spreadlab.riskfee import PARAMS as RISK_PARAMS, RiskFeePolicy
from spreadlab.server import data_dir
from spreadlab.variants import VARIANTS

HOUR, DAY, WARN = 60, 1440, 180
OUT = data_dir() / "screen"
MAP = json.loads((data_dir() / "map.json").read_text())
DEFAULT = "slow-friday-late-150-kinds-limits"
CHECK = ("curve-fee-0.9-cost-1.2", "curve-fee-1.0-cost-1.2")
FEE16 = [0, 10 ** 6, 16, 10 ** 6, 0.9, 0.1, 1.2]  # the qualifying track's `fee16-*` rule
SCHEDULES = {  # name -> parameters on top of the default's
    "default": {},
    "risk-fees": {"risk_fees": True},
    "risk-fees-raise-0.06": {"risk_fees": True, "risk_raise_late": 0.06},
    "risk-fees-raise-0.03": {"risk_fees": True, "risk_raise_late": 0.03},
    "risk-hold": {"risk_fees": True, "risk_open": 1.0},
    "risk-open": {"risk_fees": True, "risk_raise_late": 0},
    "risk-fees-open-0.95": {"risk_fees": True, "risk_open": 0.95},
    "risk-fees-open-24h": {"risk_fees": True, "risk_open_hours": 24},
    "risk-fees-open-0.85": {"risk_fees": True, "risk_open": 0.85},
    "risk-fees-open-0.8": {"risk_fees": True, "risk_open": 0.8},
    "fee16 (qualifying track)": {"fee_rules": [FEE16]},
    "fee16-80 (qualifying track)": {"fee_rules": [[0, 10 ** 6, 16, 10 ** 6, 0.8, 0.1, 1.2]]},
}
AGE = (0, 1, 2, 3, 6, 12)
CLOCK = (0, 5, 6, 7, 8, 11, 14, 17, 20, 22)
LEFT = (0, 6, 8, 12, 24, 48)
NOTIFIED = (0, 5, 10, 40, 100)
KNEE = math.log(1.22)  # booking follows the fee over the lane's usual fee up to about 1.22, then hardly (scratch/research)


def bins(value, edges) -> int:
    return sum(value >= e for e in edges[1:])


def week_cars(path_variant_seed):
    """The one-car orders of a week: what was known at the first posting, its fee schedule then, its first booking before
    the warning, and how it ended."""
    variant, seed = path_variant_seed
    try:
        run = load_run(variant, seed)
    except Exception:
        return None
    params = {k: v for k, v in run["params"].items() if k in policy.DEFAULTS and k not in policy.RULES}
    desk = policy.Policy(None, 8, 0, params, run["roster"], MAP)
    requests = {r["request"]["id"]: r["request"] for r in run["reveal"]["requests"]}
    late = {e["line"]["orderId"] for e in run["events"] if e["kind"] == "ledger" and e["line"]["kind"] in ("late_refund", "undelivered_penalty")}
    paid = collections.Counter()
    for e in run["events"]:
        if e["kind"] == "ledger" and e["line"]["kind"] == "driver_fee" and e["line"]["orderId"]:
            paid[e["line"]["orderId"]] -= e["line"]["cents"]
    won = {e["order"]["id"]: e["order"] for e in run["events"] if e["kind"] == "order_won"}
    warned = {}
    for e in run["events"]:
        if e["kind"] == "deadline_close":
            warned.setdefault(e["orderId"], e["at"])
    gigs = {}
    for g in run["gigs"]:
        orders = {s["orderId"] for s in g["stops"]}
        if len(orders) == 1:
            o = orders.pop()
            if o not in gigs or g["postedAt"] < gigs[o]["postedAt"]:
                gigs[o] = g
    booked = {}
    for e in run["events"]:
        if e["kind"] == "gig_booked":
            booked.setdefault(e["gigId"], (e["at"], e["feeCents"]))
    cars = []
    for oid, order in won.items():
        request = requests.get(oid)
        if request is None or len(request["legs"]) != 1 or oid not in gigs or order.get("lastPickupAt") is None:
            continue
        g, leg = gigs[oid], request["legs"][0]
        posted, last = g["postedAt"], order["lastPickupAt"]
        warn = min(warned.get(oid, last - WARN), last - WARN)
        if warn <= posted:
            continue
        desk.requests[oid], desk.now = request, posted
        schedule = desk.fees_for(order, 1)
        if g["schedule"][0]["at"] <= posted and [(s["at"], s["feeCents"]) for s in g["schedule"]] != [(s["at"], s["feeCents"]) for s in schedule]:
            continue  # a schedule the parameters do not give again (snow fees, pushes): left out
        notified = desk.notified[leg["pickup"]["placeId"]]
        drive = desk.drive(request)
        chance = slow.chance(slow.known({**request, "respondBy": posted}, {"deadline": order["deadline"]}, notified, drive, len(run["roster"])), slow.MODELS["friday"])
        lane = policy.lane(request)
        usual = math.exp(policy.LANES[lane]) if lane in policy.LANES else request["referenceFeeCents"]
        at, fee = booked.get(g["id"], (None, None))
        cars.append({"posted": posted, "last": last, "warn": warn, "booked": at if at is not None and at < warn else None, "fee": fee,
                     "schedule": [(s["at"], s["feeCents"]) for s in schedule], "typ": request["referenceFeeCents"], "usual": usual,
                     "notified": notified, "same_day": order["option"] == "same_day", "premium": leg["car"]["premium"],
                     "private_pickup": leg["pickup"]["privateAddress"], "private_delivery": leg["delivery"]["privateAddress"],
                     "drive": drive, "chance": chance, "late": oid in late, "paid": paid[oid], "drivers": len(run["roster"]),
                     "request": request, "order": order})
    score = run["score"]
    return {"variant": variant, "seed": seed, "drivers": len(run["roster"]), "orders": score["wonOrders"], "on_time": score["onTimeShare"],
            "margin": score["marginCents"] / 100, "cars": cars}


def fee_at(schedule, minute) -> float:
    shown = schedule[0][1]
    for at, fee in schedule:
        if at <= minute:
            shown = fee
    return shown


def hours(car, schedule):
    """The car's hours on the board before the warning: (start, length in hours, fee shown over its start and end)."""
    out, start = [], car["posted"]
    while start < car["warn"]:
        end = min(start + HOUR, car["warn"])
        points = [start] + [at for at, _ in schedule if start < at < end]
        fee = sum(fee_at(schedule, p) * ((points[i + 1] if i + 1 < len(points) else end) - p) for i, p in enumerate(points)) / (end - start)
        out.append((start, (end - start) / HOUR, fee))
        start = end
    return out


def features(car, start, fee) -> list[float]:
    k = (start - car["posted"]) // HOUR
    x = math.log(fee / car["usual"])
    first = float(k == 0)
    row = [first * min(x, KNEE), first * max(x - KNEE, 0), (1 - first) * min(x, KNEE), (1 - first) * max(x - KNEE, 0)]
    row += [float(bins(k, AGE) == i) for i in range(1, len(AGE))]
    row += [float(bins(start % DAY / 60, CLOCK) == i) for i in range(1, len(CLOCK))]
    row += [float(start // DAY % 7 == d) for d in range(1, 7)]
    row += [float(bins((car["last"] - start) / 60, LEFT) == i) for i in range(1, len(LEFT))]
    row += [float(bins(car["notified"], NOTIFIED) == i) for i in range(1, len(NOTIFIED))]
    row += [float(car["same_day"]), float(car["premium"]), float(car["private_pickup"]), float(car["private_delivery"]),
            max(0, car["drive"] - 240) / 60, (car["drivers"] - 760) / 100]
    return row


def late_features(car, booked_at) -> list[float]:
    """Hours left at the first booking in bins, the car's own late chance, and no booking before the warning."""
    z = math.log(car["chance"] / (1 - car["chance"]))
    if booked_at is None:
        return [0.0] * 5 + [1.0, z]
    left = (car["last"] - booked_at) / 60
    return [float(bins(left, (3, 4, 6, 8, 12, 24)) == i) for i in range(1, 6)] + [0.0, z]


def rows(week):
    """Hazard rows (features, booked in this hour, length) and late rows (features, late) of a week."""
    X, y, w, L, z, unpaid = [], [], [], [], [], []
    for car in week["cars"]:
        for start, length, fee in hours(car, car["schedule"]):
            if length < 0.5:
                break
            booked = car["booked"] is not None and car["booked"] < start + HOUR
            X.append(features(car, start, fee)), y.append(booked), w.append(length)
            if booked or car["booked"] is not None and car["booked"] < start + HOUR:
                break
        L.append(late_features(car, car["booked"])), z.append(car["late"])
        if car["booked"] is None:
            unpaid.append(car["paid"] / car["typ"])
    return np.array(X, np.float32), np.array(y, bool), np.array(L, np.float32), np.array(z, bool), unpaid


def all_weeks():
    runs = data_dir() / "runs"
    return [(d.name, p.name.split("-L")[0]) for d in sorted(runs.iterdir()) if d.is_dir() for p in sorted(d.glob("*-L8.json.gz"))]


def week_rows(variant_seed):
    """In a worker: the week's hazard and late rows, and the week itself only when it is checked or screened."""
    week = week_cars(variant_seed)
    if week is None or not week["cars"]:
        return None
    keep = week if week["variant"] in CHECK or week["variant"] == DEFAULT else None
    return (None if week["variant"] in CHECK else rows(week)), keep


def extract() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    weeks, X, y, L, z, unpaid, check, default, n = all_weeks(), [], [], [], [], [], [], [], 0
    with Pool(4, maxtasksperchild=200) as pool:
        for got in pool.imap_unordered(week_rows, weeks, chunksize=2):
            n += 1
            if n % 500 == 0:
                print(n, "weeks", flush=True)
            if got is None:
                continue
            arrays, week = got
            if week is not None:
                (check if week["variant"] in CHECK else default).append(week)
            if arrays is not None:
                a, b, c, d, e = arrays
                X.append(a), y.append(b), L.append(c), z.append(d), unpaid.extend(e)
    np.savez(OUT / "rows.npz", X=np.concatenate(X), y=np.concatenate(y), L=np.concatenate(L), z=np.concatenate(z), unpaid=np.array(unpaid))
    for name, data in (("check", check), ("default", default)):
        (OUT / f"{name}.json").write_text(json.dumps(data))
    print(sum(len(a) for a in X), "car-hours,", sum(len(a) for a in L), "cars,", len(check), "check weeks,", len(default), "default weeks")


def fit():
    import pickle
    if (OUT / "models.pkl").exists():
        return pickle.loads((OUT / "models.pkl").read_bytes())
    from sklearn.linear_model import LogisticRegression
    d = np.load(OUT / "rows.npz")
    hazard = LogisticRegression(C=10, max_iter=500).fit(d["X"], d["y"])
    lateness = LogisticRegression(C=10, max_iter=500).fit(d["L"], d["z"])
    models = hazard, lateness, float(np.mean(d["unpaid"]))
    (OUT / "models.pkl").write_bytes(pickle.dumps(models))
    print("price terms (first hour under and over 1.22 x the lane's fee, later hours):", np.round(hazard.coef_[0][:4], 2), flush=True)
    return models


def expect(car, schedule, hazard, lateness, unpaid):
    """The expected fees over the typical fee, booked within the hour, and the chance of ending late, under a schedule."""
    hs = hours(car, schedule)
    p = hazard.predict_proba(np.array([features(car, s, f) for s, _, f in hs], np.float32))[:, 1]
    alive, fees, late, first = 1.0, 0.0, 0.0, 0.0
    lates = lateness.predict_proba(np.array([late_features(car, s + length * 30) for s, length, _ in hs] + [late_features(car, None)], np.float32))[:, 1]
    for i, (start, length, fee) in enumerate(hs):
        q = 1 - (1 - p[i]) ** length
        fees += alive * q * fee / car["typ"]
        late += alive * q * lates[i]
        if i == 0:
            first = q
        alive *= 1 - q
    return fees + alive * unpaid, first, late + alive * lates[-1]


def check() -> None:
    hazard, lateness, unpaid = fit()
    weeks = json.loads((OUT / "check.json").read_text())
    for variant in CHECK:
        got = collections.Counter()
        for week in (w for w in weeks if w["variant"] == variant):
            for car in week["cars"]:
                fees, first, late = expect(car, car["schedule"], hazard, lateness, unpaid)
                got["cars"] += 1
                got["model fees"] += fees
                got["model first"] += first
                got["model late"] += late
                got["fees"] += car["paid"] / car["typ"]
                got["first"] += car["booked"] is not None and car["booked"] - car["posted"] <= HOUR
                got["late"] += car["late"]
            got["weeks"] += 1
        n = got["cars"]
        print(f"{variant}: {got['weeks']} weeks, {n / got['weeks']:.0f} cars a week")
        print(f"  fees over typical: recorded {got['fees'] / n:.3f}, model {got['model fees'] / n:.3f}")
        print(f"  booked within the hour: recorded {got['first'] / n:.1%}, model {got['model first'] / n:.1%}")
        print(f"  late a week: recorded {got['late'] / got['weeks']:.1f}, model {got['model late'] / got['weeks']:.1f}")


def interval(values, draws=10000):
    rng = np.random.default_rng(1)
    values = np.asarray(values)
    means = values[rng.integers(0, len(values), (draws, len(values)))].mean(axis=1)
    return values.mean(), np.quantile(means, 0.025), np.quantile(means, 0.975)


def screen_week(week):
    """In a worker: the expected fees, first-hour bookings and late orders of a week's cars under each schedule."""
    hazard, lateness, unpaid = fit()
    totals = {}
    for name, extra in SCHEDULES.items():
        params = {**VARIANTS[DEFAULT], **extra}
        desk = (RiskFeePolicy if params.get("risk_fees") else policy.Policy)(None, 8, 0, params, [], MAP)
        desk.roster, desk.notified = [None] * week["drivers"], collections.defaultdict(int)
        t = collections.Counter()
        for car in week["cars"]:
            desk.requests[car["order"]["id"]], desk.now = car["request"], car["posted"]
            desk.notified[car["request"]["legs"][0]["pickup"]["placeId"]] = car["notified"]
            schedule = [(s["at"], s["feeCents"]) for s in desk.fees_for(car["order"], 1)]
            if name == "default":
                t["same as played"] += schedule == [tuple(s) for s in car["schedule"]]
            fees, first, late = expect(car, schedule, hazard, lateness, unpaid)
            t["fees"] += fees * car["typ"] / 100
            t["typ"] += car["typ"] / 100
            t["first"] += first
            t["late"] += late
            t["cars"] += 1
        totals[name] = t
    return {"drivers": week["drivers"], "orders": week["orders"], "on_time": week["on_time"], "totals": totals}


def screen() -> None:
    fit()
    weeks = json.loads((OUT / "default.json").read_text())
    with Pool(4) as pool:
        done = pool.map(screen_week, weeks, chunksize=4)
    same = sum(w["totals"]["default"]["same as played"] for w in done) / sum(w["totals"]["default"]["cars"] for w in done)
    print(f"{len(done)} weeks of {DEFAULT}, {sum(w['drivers'] < 720 for w in done)} with under 720 drivers; the default's schedule is the "
          f"played one for {same:.1%} of cars. Euros a week against the default's schedule, 95% intervals over weeks; a late order at 150.")
    print(f"{'schedule':28s} {'fees saved':>21s} {'late orders':>21s} {'net':>21s} {'paid/typ':>8s} {'booked<1h':>9s} {'thin net':>8s} {'<90%':>4s} {'lowest':>6s}")
    for name in SCHEDULES:
        d = [{k: w["totals"][name][k] - w["totals"]["default"][k] for k in ("fees", "late")} for w in done]
        fees = interval([-r["fees"] for r in d])
        late = interval([r["late"] for r in d])
        net = interval([-r["fees"] - 150 * r["late"] for r in d])
        thin = [-r["fees"] - 150 * r["late"] for r, w in zip(d, done) if w["drivers"] < 720]
        on_time = [1 - ((1 - w["on_time"]) * w["orders"] + r["late"]) / w["orders"] for r, w in zip(d, done)]
        paid = sum(w["totals"][name]["fees"] for w in done) / sum(w["totals"][name]["typ"] for w in done)
        first = sum(w["totals"][name]["first"] for w in done) / sum(w["totals"][name]["cars"] for w in done)
        print(f"{name:28s} {fees[0]:+6.0f} ({fees[1]:+5.0f} to {fees[2]:+5.0f}) {late[0]:+6.2f} ({late[1]:+.2f} to {late[2]:+.2f}) "
              f"{net[0]:+6.0f} ({net[1]:+5.0f} to {net[2]:+5.0f}) {paid:8.3f} {first:9.1%} {np.mean(thin):+8.0f} {sum(o < 0.9 for o in on_time):4d} {min(on_time):6.1%}")

if __name__ == "__main__":
    {"extract": extract, "check": check, "screen": screen}[sys.argv[1]]()
