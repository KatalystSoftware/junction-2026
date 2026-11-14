"""Scratch: the exposure spec's three calibration checks on the saved weeks left out of the fits (`fresh-1301` to `fresh-1460`), from the
books of book_rows.py at 20:00 of each evening.

1. Days: the model's expected late orders among the cars due the next day, with that day the flu day if its night had a wave (10 or
   more first-hour drops of the desk's gigs) and not otherwise, against the late orders they had, by cars due per 100 drivers.
2. Flu weights: the weight of "tomorrow is the flu day" at 20:00, by band, against how often tomorrow's night had a wave.
3. The tail: the over-dispersion ω that makes (late - μ) / sd of the book's late count have variance 1 under the flu day that came,
   and the chance of a week under 90% on the evening before the wave of each week that ended under 90% or 92%.

    PYTHONPATH=. uv run --with numpy python scratch/exposure/checks.py [all]    # all: every saved week, fits included
    PYTHONPATH=. uv run --with numpy python scratch/exposure/checks.py all <variant,...>    # every week of other variants' books
"""
from __future__ import annotations

import collections
import math
import pickle
import sys

import numpy as np

from spreadlab import exposure
from spreadlab.server import data_dir

DAY, HOUR, WAVE = 1440, 60, 10
VARIANTS = ["slow-friday-late-150-kinds-limits", "steep-notes-offers-8", "thin-premium-0.4"]


def feats_of(w: dict) -> dict:
    feats = {}
    for r in w["rows"]:
        if r["order"] not in feats:
            feats[r["order"]] = {k: r[k] for k in ("notified", "at_delivery", "last", "premium", "drive", "note")}
            feats[r["order"]]["hard"] = exposure.hard(feats[r["order"]], w["drivers"])
    return feats


def cars_of(w: dict, snap: dict, feats: dict) -> list[dict]:
    since = {}
    for r in w["rows"]:
        if r["at"] <= snap["at"]:
            since[r["order"]] = r["at"]
    out = []
    for oid, due, held, hours, picked in snap["cars"]:
        if oid not in feats:
            continue
        night = hours - (due * DAY - snap["at"]) / HOUR
        out.append({"id": oid, "day": due, "held": held, "picked": picked, "hours": hours, "night": night, "weight": 1.0,
                    "waited": (snap["at"] - since.get(oid, snap["at"])) / HOUR, **feats[oid]})
    return out


GRID = np.arange(-3.0, 3.01, 0.25)
GH = list(zip(*np.polynomial.hermite_e.hermegauss(9)))
GH = [(x, w / sum(w_ for _, w_ in GH)) for x, w in GH]


def dispersion(days: list[tuple]) -> None:
    """The sd of a day's shared shift in log odds, by a likelihood over a grid: each day's count is normal (in whole orders) around the cars'
    chances moved by the shift. `days`: (wave, cars due per 100 drivers, [(mean, var) at each shift of GRID], late)."""
    from math import erf, sqrt
    cdf = lambda z: 0.5 * (1 + erf(z / sqrt(2)))
    for wave in (False, True):
        for lo, hi in ((0, 7), (7, 99), (0, 99)):
            sel = [d for d in days if d[0] == wave and lo <= d[1] < hi]
            if len(sel) < 20:
                continue
            best = None
            for sd in np.arange(0.0, 1.21, 0.05):
                ll = 0.0
                for _, _, curve, late in sel:
                    lik = 0.0
                    for x, w in GH:
                        k = min(max(np.searchsorted(GRID, sd * x), 1), len(GRID) - 1)
                        t = (sd * x - GRID[k - 1]) / (GRID[k] - GRID[k - 1])
                        mean = curve[k - 1][0] * (1 - t) + curve[k][0] * t
                        sdv = sqrt(max(curve[k - 1][1] * (1 - t) + curve[k][1] * t, 0.25))
                        lik += w * max(cdf((late + 0.5 - mean) / sdv) - cdf((late - 0.5 - mean) / sdv), 1e-12)
                    ll += math.log(lik)
                if best is None or ll > best[0]:
                    best = (ll, sd)
            print(f"   {'wave' if wave else 'calm'} days, {lo}-{hi} cars due per 100 drivers: {len(sel)} days, sd of the day's shift {best[1]:.2f}")


def main() -> None:
    global VARIANTS
    every = len(sys.argv) > 1 and sys.argv[1] == "all"
    if every and len(sys.argv) > 2:
        VARIANTS = sys.argv[2].split(",")
    if len(sys.argv) > 1 and sys.argv[1] == "dispersion":  # on the fit weeks
        days = []
        for v in VARIANTS:
            for w in pickle.load(open(data_dir() / "exposure" / f"book-{v}.pkl", "rb")):
                s = w["seed"]
                if s.startswith("fresh-") and 1301 <= int(s.split("-")[1]) <= 1460:
                    continue
                feats = feats_of(w)
                for snap in w["snaps"]:
                    at = snap["at"]
                    if at % DAY != 20 * HOUR or at // DAY > 3:
                        continue
                    day, cars = at // DAY + 1, cars_of(w, snap, feats)
                    tomorrow = [c for c in cars if c["day"] == day]
                    if len(tomorrow) < 10:
                        continue
                    wave = w["first_hour"].get(day, 0) >= WAVE
                    other = sum(1 for c in cars if c["day"] != day and not c["held"])
                    curve = [exposure.day_late(tomorrow, day, wave, w["drivers"], other, 1.0, exposure.M["wave_share"], False, at, x) for x in GRID]
                    days.append((wave, 100 * len(tomorrow) / w["drivers"], curve, sum(w["fate"].get(c["id"], False) for c in tomorrow)))
        print(f"0. Dispersion on the fit weeks: {len(days)} days")
        dispersion(days)
        return
    days, flu_rows, resid, tails, seen = [], [], [], [], []
    for v in VARIANTS:
        for w in pickle.load(open(data_dir() / "exposure" / f"book-{v}.pkl", "rb")):
            s = w["seed"]
            if not every and not (s.startswith("fresh-") and 1301 <= int(s.split("-")[1]) <= 1460):
                continue
            feats = feats_of(w)
            seen.append((v, w["on_time"], len({r["order"] for r in w["rows"]})))
            wave_day = next((d for d in range(1, 5) if w["first_hour"].get(d, 0) >= WAVE), None)
            for snap in w["snaps"]:
                at = snap["at"]
                if at % DAY != 20 * HOUR or at // DAY > 3:
                    continue
                day = at // DAY + 1  # tomorrow
                cars = cars_of(w, snap, feats)
                book = exposure.Book(at, cars, snap["nights"], w["drivers"], snap["resolved"] + len(cars), snap["resolved"], snap["late"])
                tomorrow = [c for c in cars if c["day"] == day]
                wave = w["first_hour"].get(day, 0) >= WAVE
                if tomorrow:
                    counts = book.count(day, tomorrow)
                    mean, var = counts[(day, 2, 2)] if wave and (day, 2, 2) in counts else counts[(None, 2)]
                    late = sum(w["fate"].get(c["id"], False) for c in tomorrow)
                    days.append((v, wave, len(tomorrow), 100 * len(tomorrow) / w["drivers"], mean, late))
                last = w["snaps"][-1]["nights"].get(day)
                flu_rows.append((v, day, book.weights.get(day, 0.0), wave, bool(last and exposure.ratio(*last) > 1)))
                # the book's late count under the flu day that came (if it is still ahead), against what happened
                came = wave_day if wave_day is not None and wave_day >= day else None
                mean = var = 0.0
                for d, counts in book.sums.items():
                    m, vv = counts[(d, 2, 2)] if d == came and (d, 2, 2) in counts else counts[(None, 2)]
                    mean, var = mean + m, var + vv
                late = sum(w["fate"].get(c["id"], False) for c in cars)
                if var > 0:
                    resid.append((late - mean) / math.sqrt(var))
                risks = [book.risk(line=line)[0] for line in (0.10, 0.08, 0.06)]
                tails.append((v, s, w["on_time"], wave_day, day, risks, w["due"], book.weights.get(day, 0.0)))
    print(f"1. Days (evening before; expected / actual late among the cars due the next day), {len(days)} days")
    for wave in (False, True):
        for a, b in ((0, 4), (4, 7), (7, 10), (10, 13), (13, 99)):
            sel = [x for x in days if x[1] == wave and a <= x[3] < b]
            if sel:
                e, l = sum(x[4] for x in sel), sum(x[5] for x in sel)
                print(f"   {'wave' if wave else 'calm'} days, {a}-{b} cars due per 100 drivers: {len(sel):4} days, cars {sum(x[2] for x in sel) / len(sel):5.1f},"
                      f" expected {e:7.1f}, actual {l:5d}, ratio {l / e if e else float('nan'):.2f}{'' if len(sel) < 20 or abs(l / e - 1) <= 0.2 else '  <- off by more than a fifth'}")
        for a, b in ((0, 90), (90, 999)):
            sel = [x for x in days if x[1] == wave and a <= x[2] < b]
            if sel:
                print(f"   {'wave' if wave else 'calm'} days with {a}-{b} cars due: {len(sel)} days, expected {sum(x[4] for x in sel):.1f}, actual {sum(x[5] for x in sel)}")
    print("\n2. Flu weights at 20:00 for tomorrow (weight band: days, mean weight, share with a wave of 10 or more drops, share whose night's drops are likelier under a wave)")
    for a, b in ((0, 0.05), (0.05, 0.2), (0.2, 0.3), (0.3, 0.4), (0.4, 0.6), (0.6, 1.01)):
        sel = [x for x in flu_rows if a <= x[2] < b]
        if sel:
            print(f"   {a:.2f}-{b:.2f}: {len(sel):4}, weight {np.mean([x[2] for x in sel]):.3f}, wave {np.mean([x[3] for x in sel]):.3f}, by ratio {np.mean([x[4] for x in sel]):.3f}")
    for day in range(1, 5):
        sel = [x for x in flu_rows if x[1] == day]
        calm = [x for x in sel if x[2] > 0.05]
        print(f"   tomorrow day {day}: mean weight {np.mean([x[2] for x in sel]):.3f}, wave {np.mean([x[3] for x in sel]):.3f};"
              f" where no wave seen yet: weight {np.mean([x[2] for x in calm]) if calm else float('nan'):.3f}, wave {np.mean([x[3] for x in calm]) if calm else float('nan'):.3f},"
              f" by ratio {np.mean([x[4] for x in calm]) if calm else float('nan'):.3f} ({len(calm)})")
    r = np.array(resid)
    print(f"\n3. The tail: {len(r)} evenings; var of (late - mu) / sd at the central shifts under the flu day that came: {r.var():.2f}; mean {r.mean():+.2f}")
    for k, line in enumerate((0.90, 0.92, 0.94)):
        print(f"   P(week under {line:.0%}) at 20:00 (band: evenings, mean P, share of their weeks that ended under {line:.0%}):")
        for a, b in ((0, 0.01), (0.01, 0.05), (0.05, 0.15), (0.15, 0.35), (0.35, 1.01)):
            sel = [t for t in tails if a <= t[5][k] < b]
            if sel:
                print(f"     {a:.2f}-{b:.2f}: {len(sel):4}, P {np.mean([t[5][k] for t in sel]):.3f}, ended under {np.mean([t[2] < line for t in sel]):.3f}")
    print("   Weeks by variant (weeks, one-car orders a week, ended under 90%, under 92%):")
    for v in VARIANTS:
        sel = [x for x in seen if x[0] == v]
        if sel:
            print(f"     {v:36} {len(sel):3}  {np.mean([x[2] for x in sel]):5.0f}  {sum(x[1] < 0.90 for x in sel):2}  {sum(x[1] < 0.92 for x in sel):2}")
    print("   Thursday 20:00, weeks with a Friday wave, by orders due on Friday (seed, on time, P under 90/92/94%, Friday's weight):")
    for v, s, on_time, wave_day, day, risks, due, wt in sorted(tails, key=lambda t: t[2]):
        if day == 4 and wave_day == 4:
            fri = sum(1 for d in due.values() if d == 4)
            print(f"     {v[:20]:20} {s:10} Fri due {fri:3} on time {on_time:.3f}  P {risks[0]:.3f} / {risks[1]:.3f} / {risks[2]:.3f}  weight {wt:.2f}")


if __name__ == "__main__":
    main()
