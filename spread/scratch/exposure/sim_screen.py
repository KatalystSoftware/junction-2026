"""Scratch: the drop-exposure quote rule against the default and `day-cap-70`, in the closed-loop stand-in of scratch/opt/sim.py on the default's
recorded weeks (scratch/target/screen.py extracts them; scratch/exposure/measure.py gives each week's drops in each night's first hour).

Rules, as policy.py's quote cost of a one-car dealer request in cents, with p the late chance at the quote (slow.py):
- default: fee x (1.2 + 0.8 x waiting cars x p) + 150 x p euros; no quote while 25 cars wait.
- cap-70: the default, and no quote whose fastest option's last pickup falls on a day with 70 orders in flight, until a night has had 10 drops in its first hour.
- default-24h: the default's surcharge on the waiting cars due within 24 hours only (the target thread's failed neighbour).
- k<kappa>-l<load>: fee x 1.2 + exposure.cost(...) (spreadlab/exposure.py): €82 for each expected late order that one more car due that day adds to
  the book, its own included, and kappa x the week's value x its change to the chance of a week under 90%; the load weights of `need` x load; no
  waiting-car surcharge, no late cost of its own, no day cap; no quote while 40 cars wait. `no-tail` and `no-wave` are k1-l1 without the tail term
  and without the flu-day scenarios.
The sim prices the fastest option's due day alone; the desk can drop one option and keep a slower one, so the cap's lost volume here is an upper bound.

    PYTHONPATH=. uv run --with numpy python scratch/exposure/sim_screen.py <draws> [crowd|nocrowd] [rule names...]

Weeks: `cat-` seeds of the catalogue's tune list are tune; the `fresh-` weeks judge. Thin is under 720 drivers listed.
"""
from __future__ import annotations

import collections
import json
import pickle
import sys
from multiprocessing import Pool
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.argv[1:1] = ["screen", "x"]  # screen.py reads its options from argv[4:]
sys.path[:0] = [str(HERE.parent / "target"), str(HERE.parent / "gap"), str(HERE.parent / "opt")]
import screen as target  # noqa: E402
import sim  # noqa: E402

from spreadlab import exposure  # noqa: E402
from spreadlab.server import data_dir  # noqa: E402

del sys.argv[1:3]
DAY = 1440
BASE = "slow-friday-late-150-kinds-limits"
CROWD = (0.052, 0.136)  # the default's days (scratch/exposure/days.py): log odds a car due per 100 drivers, calm and on a wave day
TUNE = set(json.load(open(HERE.parents[1] / "catalogue" / "seeds.json"))["tune"])


def default(row, parts, trust, desk):
    if sum(parts) >= 25:
        return None
    return max(row["fee"], row["fee"] * (1.2 + 0.8 * sum(parts) * row["p"]) + 100 * 150 * row["p"])


def cap(limit: int):
    def rule(row, parts, trust, desk):
        if max((n for n, _ in desk["night"].values()), default=0) < 10 and sum(o["due"] == sim.due_day(row) for o in desk["inflight"]) >= limit:
            return None
        return default(row, parts, trust, desk)
    return rule


DELIVERY: dict = {}  # (week, request id) -> drivers near the delivery place, read from the saved weeks


def delivery_counts(seeds: list[str]) -> dict:
    """The drivers near each request's delivery place, by week and request id, from the base's saved weeks (cached)."""
    import gzip
    path = data_dir() / "exposure" / f"delivery-{BASE}.pkl"
    if path.exists():
        return pickle.load(open(path, "rb"))
    from spreadlab.server import drivers_near, near_places
    near = near_places(json.loads((data_dir() / "map.json").read_text()))
    out = {}
    for wi, seed in enumerate(seeds):
        d = json.load(gzip.open(data_dir() / "runs" / BASE / f"{seed}-L8.json.gz"))
        notified = drivers_near(d["roster"], near)
        for r in d["reveal"]["requests"]:
            out[(wi, r["request"]["id"])] = notified[r["request"]["legs"][0]["delivery"]["placeId"]]
    pickle.dump(out, open(path, "wb"))
    return out


def car_of(r: dict) -> dict:
    return {"notified": r["notified"], "at_delivery": DELIVERY.get((r["w"], r["rid"]), 200), "premium": r["premium"], "drive": r["drive"], "note": r["note"]}


def book_of(row, desk, load: float):
    """The desk's book at the quote, as exposure.Book wants it, from the stand-in's orders in flight. A car is held while it is outside its
    course's minutes without a driver, and on the road once it is held past its last pickup. The nights are the saved week's, with the
    drops scaled to the cars this arm has due that day."""
    now, cars = desk["now"], []
    for o in desk["inflight"]:
        r = o["row"]
        if "hard" not in o:
            o["hard"] = exposure.hard(car_of(r), r["drivers"])
        age = now - o["won"]
        gap = next(((a, b) for a, b in o["iv"] if a <= age < b), None)
        hours = (o["won"] + o["last"] - now) / 60
        cars.append({"day": o["due"], "last": o["won"] + o["last"], "held": gap is None, "picked": gap is None and hours < 0, "hours": hours,
                     "night": hours - (o["due"] * DAY - now) / 60, "weight": 1.0, "waited": (age - gap[0]) / 60 if gap else 0.0, "hard": o["hard"]})
    nights = {}
    for d, (dropped, held) in desk["night"].items():
        mine = sum(1 for c in cars if c["day"] == d)
        nights[d] = (max(mine, 0), round(dropped * mine / held) if held else 0)
    resolved = desk["orders"] - len(cars)
    return exposure.Book(now, cars, nights, desk["drivers"], desk["orders"], resolved, desk["late"], load)


REC: dict = {"added": {}, "p": {}}  # per process: the model's late orders added at each quote (week, request) and P(under 90%, 92%) by (week, day) at its last quote


def view(row, desk, cache: dict, load: float, wave: bool = True):
    """The book at this quote (cached until a win, a delivery or half an hour), the candidate car and its due day, and P(under 90%) and the
    expected late of the book without it; records P at the day's last quote."""
    key = (id(desk["inflight"]), len(desk["inflight"]), desk["orders"], desk["now"] // 30)
    if cache.get("key") != key:
        book = book_of(row, desk, load)
        if not wave:
            book.weights = {None: 1.0}
        f0, e0 = book.risk()
        cache.update(key=key, book=book, base=(f0, e0, book.risk(line=0.08)[0]))
    book, (f0, e0, f92) = cache["book"], cache["base"]
    now, day = desk["now"], sim.due_day(row)
    REC["p"][(row["w"], now // DAY)] = (f0, f92)
    hours = row["h"] + (row["by"] - now) / 60
    car = {"day": day, "last": now + hours * 60, "held": False, "picked": False, "hours": hours, "night": hours - (day * DAY - now) / 60,
           "weight": exposure.M["candidate_waiting"], "waited": 0.0, "hard": exposure.hard(car_of(row), row["drivers"])}
    return book, day, car, f0, e0


def exposed(kappa: float = 1.0, load: float = 1.0, tail: bool = True, wave: bool = True, gate: int = 40):
    cache = {}

    def rule(row, parts, trust, desk):
        if sum(parts) >= gate:
            return None
        book, day, car, f0, e0 = view(row, desk, cache, load, wave)
        f1, e1 = book.risk(day, car)
        REC["added"][(row["w"], row["rid"])] = e1 - e0
        later, _ = book.future()
        value = (book.orders + later) * exposure.M["margin"]
        euros = exposure.M["late_euros"] * (e1 - e0) + (kappa * value * (f1 - f0) if tail else 0.0)
        return max(row["fee"], row["fee"] * 1.2 + 100 * euros)
    return rule


def watched(base):
    """`base`, with the model's view of each quote it makes recorded as the exposure arms record theirs."""
    cache = {}

    def rule(row, parts, trust, desk):
        cost = base(row, parts, trust, desk)
        if cost is not None:
            book, day, car, f0, e0 = view(row, desk, cache, 1.0)
            REC["added"][(row["w"], row["rid"])] = book.risk(day, car)[1] - e0
        return cost
    return rule


def default_24h(row, parts, trust, desk):
    """The target thread's neighbour: the default's surcharge on the waiting cars due within 24 hours only."""
    if sum(parts) >= 25:
        return None
    return max(row["fee"], row["fee"] * (1.2 + 0.8 * (parts[0] + parts[1]) * row["p"]) + 100 * 150 * row["p"])


RULES = {"default": default, "cap-70": cap(70), "default-24h": default_24h, "no-tail": exposed(tail=False), "no-wave": exposed(wave=False),
         **{f"k{k}-l{l}": exposed(k, l) for k in (0.5, 1, 2, 4, 8, 16, 32) for l in (0.5, 1)},
         **{f"k{k}-l1-g25": exposed(k, 1, gate=25) for k in (1, 2, 4, 8, 16, 32)}}
WEEKS, CROWD_ON, WATCH = None, True, set()


def run(job):
    name, draw, on = job
    REC["added"], REC["p"] = {}, {}
    rule = watched(RULES[name]) if name in WATCH else RULES[name]
    out = sim.simulate(WEEKS, rule, on, draw=draw, react=0.6, crowd=CROWD if CROWD_ON else None)
    return out, dict(REC)


def main() -> None:
    global WEEKS, CROWD_ON, WATCH
    draws = int(sys.argv[1])
    CROWD_ON = (sys.argv[2] if len(sys.argv) > 2 else "crowd") == "crowd"
    names = ["default", "cap-70"] + [a for a in sys.argv[3:] if a != "--watch"]
    if "--watch" in sys.argv:  # the model's view of the default's and the cap's quotes too (doubles their time)
        WATCH = {"default", "cap-70", "default-24h"}
    saved = pickle.load(open(target.OUT / f"{BASE}.pkl", "rb"))
    nights = {w["seed"]: (w["first_hour"], w["night"]) for w in pickle.load(open(data_dir() / "exposure" / f"{BASE}.pkl", "rb"))}
    weeks = target.load(saved)
    on = list(range(len(weeks.W)))
    weeks.fit(on, by_day=True)
    weeks.first_hour = {wi: {d: (nights[s][0].get(d, 0), held[1]) for d, held in nights[s][1].items()} for wi, s in enumerate(weeks.seeds) if s in nights}
    WEEKS = weeks
    DELIVERY.update(delivery_counts(weeks.seeds))
    jobs = [(name, d, on[i::8]) for name in names for d in range(draws) for i in range(8)]
    with Pool(2) as pool:
        done = pool.map(run, jobs, chunksize=1)
    res = collections.defaultdict(dict)
    model = collections.defaultdict(lambda: {"added": {}, "p": {}})
    for (name, d, chunk), (out, rec) in zip(jobs, done):
        for wi, wk in zip(chunk, out):
            res[(wi, d)][name] = wk
        if d == 0:
            model[name]["added"].update(rec["added"])
            model[name]["p"].update(rec["p"])
    groups = {
        "tune (cat-, tune list)": lambda s: s["seed"] in TUNE,
        "judge: natural fresh-": lambda s: s["seed"].startswith("fresh-") and s["drivers"] >= 720,
        "judge: thin fresh- (< 720)": lambda s: s["seed"].startswith("fresh-") and s["drivers"] < 720,
        "Friday wave (>= 10 drops 00-01 Fri)": lambda s: s["friday_wave"] >= 10,
        "Friday wave, >= 100 due Fri": lambda s: s["friday_wave"] >= 10 and s["friday_due"] >= 100,
        "all": lambda s: True,
    }
    print(f"{len(on)} weeks of {BASE}, {draws} draws, react 0.6, crowd {CROWD if CROWD_ON else 'off'}")
    print(f"{'group':36} {'rule':14} {'weeks':>5} {'margin':>7} {'vs dflt':>7} {'95% interval':>15} {'orders':>6} {'late':>5} {'mean OT':>7} {'lowest':>6} {'<90':>4} {'<90/60':>6} {'<92':>4}")
    for gname, keep in groups.items():
        idx = [wi for wi in on if keep(saved[wi])]
        if not idx:
            continue
        for name in names:
            rows, by_seed = [], collections.defaultdict(list)
            for wi in idx:
                for d in range(draws):
                    a, b = res[(wi, d)][name], res[(wi, d)]["default"]
                    m = a["margin"] - target.LOAD * max(0.0, a["orders"] - b["orders"]) / 100 * a["typ"] / 100
                    m0 = m if a["on_time"] >= 0.90 else 0.0
                    rows.append((m0, a))
                    by_seed[saved[wi]["seed"]].append(m0 - (b["margin"] if b["on_time"] >= 0.90 else 0.0))
            n = len(rows)
            lo, hi = target.interval(by_seed) if name != "default" else (0.0, 0.0)
            under = sum(a["on_time"] < 0.90 for _, a in rows)
            diff = sum(map(sum, by_seed.values())) / n
            print(f"{gname:36} {name:14} {n:5} {sum(m for m, _ in rows) / n:7.0f} {diff:+7.0f} {f'{lo:+.0f} to {hi:+.0f}':>15} {sum(a['orders'] for _, a in rows) / n:6.1f}"
                  f" {sum(a['late'] for _, a in rows) / n:5.1f} {sum(a['on_time'] for _, a in rows) / n:7.3f} {min(a['on_time'] for _, a in rows):6.3f} {under:4} {60 * under / n:6.2f}"
                  f" {sum(a['on_time'] < 0.92 for _, a in rows):4}")
        print()
    worst = sorted(on, key=lambda wi: min(res[(wi, d)]["default"]["on_time"] for d in range(draws)))[:12]
    print("lowest weeks of the default, on time by draw:")
    for wi in worst:
        s = saved[wi]
        print(f"  {s['seed']:10} drivers {s['drivers']:4} Fri due {s['friday_due']:3} Fri wave {s['friday_wave']:3}  " + "  ".join(
            f"{name} " + "/".join(f"{res[(wi, d)][name]['on_time']:.3f}" for d in range(draws)) for name in names))

    heavy = [wi for wi in on if saved[wi]["friday_wave"] >= 10 and saved[wi]["friday_due"] >= 100]
    print("\nFriday-wave weeks with 100 or more due on Friday (default's saved week), on time / orders / late, draw 0:")
    for wi in heavy:
        s = saved[wi]
        print(f"  {s['seed']:10} drivers {s['drivers']:4} Fri due {s['friday_due']:3}  " + "  ".join(
            f"{name} {res[(wi, 0)][name]['on_time']:.3f}/{res[(wi, 0)][name]['orders']}/{res[(wi, 0)][name]['late']}" for name in names))
    print("\nVolume and the model, draw 0, all weeks: extra orders and late a week against the default (ratio); the model's late orders added at the"
          " quote, summed over the orders won, against the stand-in's late a week")
    base = [res[(wi, 0)]["default"] for wi in on]
    for name in names:
        arm = [res[(wi, 0)][name] for wi in on]
        dor = sum(a["orders"] - b["orders"] for a, b in zip(arm, base)) / len(on)
        dla = sum(a["late"] - b["late"] for a, b in zip(arm, base)) / len(on)
        added = model[name]["added"]
        if added:
            exp = sum(added.get((wi, rid), 0.0) for wi, a in zip(on, arm) for rid in a.get("won", [])) / len(on)
            seen = f"model {exp:5.1f} against stand-in {sum(a['late'] for a in arm) / len(on):5.1f}"
        else:
            seen = "model not recorded"
        print(f"  {name:14} orders {dor:+6.1f} late {dla:+5.1f} ratio {dla / dor if dor else 0:5.2f}   {seen}")
    print("\nP bands at each evening's last quote (Mon to Thu) against the arm's own weeks, draw 0: band, evenings, mean P, share ended under")
    for name in names:
        p = model[name]["p"]
        if not p:
            continue
        for k, line in ((0, 0.90), (1, 0.92)):
            out = []
            for lo, hi in ((0, .01), (.01, .05), (.05, .15), (.15, .35), (.35, 1.01)):
                sel = [(v[k], res[(wi, 0)][name]["on_time"] < line) for (wi, day), v in p.items() if day < 4 and lo <= v[k] < hi]
                if sel:
                    out.append(f"{lo:.2f}-{hi:.2f}: {len(sel)} P {sum(x for x, _ in sel) / len(sel):.3f} ended {sum(y for _, y in sel) / len(sel):.3f}")
            print(f"  {name:14} under {line:.0%}: " + " | ".join(out))


if __name__ == "__main__":
    main()
