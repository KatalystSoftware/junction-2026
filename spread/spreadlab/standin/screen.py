"""Screens policy variants on the stand-in before they bid for practice worlds: each arm and the baseline play the same saved
seeds offline, and the result is one row a week and a summary with natural and thin worlds apart.

    python -m spreadlab.standin.screen --arms my-variant other-variant [--baseline fee16-80-q24-wide-pairs-0.6-return-0.75] --out out

The seeds are those the default desk has a played week on (`seeds-natural.txt`, 114 worlds with 720 drivers or more, and
`seeds-thin.txt`, 92 with fewer); each seed's market is measured on that played week. `--half a` and `--half b` take every other
seed of each set: a search climbs on one half and confirms on the other. Arms are names in variants.py of the
checkout that runs this, so a lane's branch screens its own desk code. Nothing here reaches Bahn's server or needs the team key.

`out/rows.csv` has a row for each arm, seed and draw; `out/summary.md` has, for each group, the margin a week (a week under 90% on
time counts as none), the paired gain over the baseline with a 95% interval, orders, late orders, the on-time share and the weeks
under 90% and 92%, and for each arm what the merge gate reads from it: PASS, FAIL or NEEDS PLAYED THIN WEEKS. README.md says how far these numbers were from play on held-out checks.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import time
from pathlib import Path

from ..variants import VARIANTS
from . import run

HERE = Path(__file__).parent
MERGE_1 = "fee16-80-q24-wide-pairs-0.6-return-0.75"
DEFAULT = "slow-friday-late-150-kinds-limits"
# A short driver list: the line under which the base counts every waiting car (`tight_drivers`), and slow.py's reference for a full list.
# All 7 weeks of merge 1's first exam under 92% had 648 to 723 drivers.
SHORT = 760
COLUMNS = ["variant", "seed", "draw", "group", "drivers", "orders", "late", "on_time", "margin", "ranked_margin", "late_booked_after_last_pickup", "gigs", "bookings", "drops",
           "expired_gigs", "refused", "wave_days", "revenue", "driver_fees", "late_refunds"]


def verdict(rows: dict, arm: str, first: str, bar: float = 500.0) -> tuple[str, list[str]]:
    """What the stand-in can say about merging the arm onto the baseline, on the seeds of this run (README.md, "The merge gate").

    FAIL: the gain on natural worlds is not over `bar` euros a week with its 95% interval above zero, or the arm loses on thin worlds
    (interval below zero), or it has more weeks under 90% than the baseline on natural worlds. A gain on thin worlds does not count
    towards the bar: play returned 0.18 to 0.39 of it, and the stand-in sees about a third of play's thin weeks under 90%.
    NEEDS PLAYED THIN WEEKS: it does not fail, and on worlds with a short driver list (under `SHORT` drivers) it wins over 3% more
    orders or has over 10% more late orders than the baseline; the margins are what one half's noise allows. More orders with few
    drivers is what took merge 1 under 90% in three played thin weeks, and the stand-in does not see it.
    PASS: neither. Weeks under 90% are compared with the baseline's, not with 1 in 60: half a set has 46 to 57 weeks."""
    reasons, notes, load = [], [], []
    for group, thin in (("natural", False), ("thin", True)):
        seeds = [s for s, ws in rows[arm].items() if (ws[0]["drivers"] < run.THIN) == thin and s in rows[first]]
        if not seeds:
            continue
        gains = [sum(run.ranked(a) - run.ranked(b) for a, b in zip(rows[arm][s], rows[first][s])) / len(rows[arm][s]) for s in seeds]
        gain = sum(gains) / len(gains)
        lo, hi = run.interval(gains)
        weeks = [w for s in seeds for w in rows[arm][s]]
        base = [w for s in seeds for w in rows[first][s]]
        under, base_under = sum(w["on_time"] < 0.90 for w in weeks), sum(w["on_time"] < 0.90 for w in base)
        under92, base_under92 = sum(w["on_time"] < 0.92 for w in weeks), sum(w["on_time"] < 0.92 for w in base)
        if not thin and (gain <= bar or lo <= 0):
            reasons.append(f"natural worlds {gain:+.0f} a week ({lo:+.0f} to {hi:+.0f}), not over {bar:.0f}")
        if not thin and under > base_under:
            reasons.append(f"{under} weeks under 90% on natural worlds against the baseline's {base_under} of {len(weeks)}")
        if thin and hi < 0:
            reasons.append(f"loses on thin worlds ({gain:+.0f}, {lo:+.0f} to {hi:+.0f})")
        if thin and (under > base_under or under92 > base_under92 + len(weeks) / 30):
            notes.append(f"thin weeks under 90%: {under} against the baseline's {base_under} of {len(weeks)}, under 92%: {under92} against {base_under92}")
    seeds = [s for s, ws in rows[arm].items() if ws[0]["drivers"] < SHORT and s in rows[first]]
    if seeds:
        orders, late = (sum(w[key] for s in seeds for w in rows[arm][s]) / max(1, sum(w[key] for s in seeds for w in rows[first][s])) for key in ("orders", "late"))
        if orders > 1.03 or late > 1.10:
            load.append(f"on the {len(seeds)} worlds under {SHORT} drivers {orders - 1:+.0%} orders and {late - 1:+.0%} late orders against the baseline: the stand-in cannot judge "
                        "on-time or margin there")
    return ("FAIL" if reasons else "NEEDS PLAYED THIN WEEKS" if load else "PASS"), reasons + load + notes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--arms", nargs="+", required=True, help="names in variants.py")
    parser.add_argument("--baseline", default="", help=f"default: {MERGE_1}, or {DEFAULT} where variants.py lacks it")
    parser.add_argument("--sets", nargs="+", default=["natural", "thin"], help="natural, thin, cat (60 seeds the fit has seen), or files with a seed a line")
    parser.add_argument("--limit", type=int, default=0, help="at most this many seeds a set")
    parser.add_argument("--half", default="", choices=["", "a", "b"], help="every other seed of each set: climb on a, confirm on b, so a search does not fit its own seeds")
    parser.add_argument("--anchor", default="", help=f"the variant whose played week of each seed its market is measured on (default: {DEFAULT}); "
                        "seeds the default never played need another desk's week")
    parser.add_argument("--draws", type=int, default=1)
    parser.add_argument("--bar", type=float, default=500.0, help="euros a week an arm must gain on natural worlds: two variants nearer than this are a tie here")
    parser.add_argument("--jobs", type=int, default=os.cpu_count() or 2)
    parser.add_argument("--design", default="{}")
    parser.add_argument("--weights", default=str(run.WEIGHTS))
    parser.add_argument("--out", default="out")
    args = parser.parse_args()
    first = args.baseline or (MERGE_1 if MERGE_1 in VARIANTS else DEFAULT)
    names = list(dict.fromkeys([first] + [a for name in args.arms for a in name.split(",") if a]))
    missing = [n for n in names if n not in VARIANTS]
    if missing:
        raise SystemExit(f"Not in this checkout's variants.py: {missing}")
    seeds: list[str] = []
    for name in args.sets:
        path = HERE / f"seeds-{name}.txt" if (HERE / f"seeds-{name}.txt").exists() else Path(name)
        found = [line.strip() for line in path.read_text().splitlines() if line.strip()]
        found = found[{"": slice(None), "a": slice(0, None, 2), "b": slice(1, None, 2)}[args.half]]
        seeds += found[: args.limit] if args.limit else found
    seeds = list(dict.fromkeys(seeds))
    started = time.time()
    out = run.run({n: VARIANTS[n] for n in names}, seeds, args.anchor or DEFAULT, json.loads(Path(args.weights).read_text()), json.loads(args.design), args.draws, args.jobs)
    rows, folder = out["results"], Path(args.out)
    folder.mkdir(parents=True, exist_ok=True)
    with open(folder / "rows.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(COLUMNS)
        for arm in names:
            for seed, weeks in rows[arm].items():
                for draw, w in enumerate(weeks):
                    writer.writerow([arm, seed, draw, "thin" if w["drivers"] < run.THIN else "natural", w["drivers"], w["orders"], w["late"], round(w["on_time"], 4), round(w["margin"]),
                                     round(run.ranked(w)), w["late_after"], w["gigs"], w["booked"], w["dropped"], w["expired"], w["refused"], " ".join(map(str, w["wave"])),
                                     round(w["ledger"].get("revenue", 0)), round(-w["ledger"].get("driver_fee", 0)), round(-w["ledger"].get("late_refund", 0))])
    lines = [f"# Stand-in screen: {', '.join(names[1:])} against {first}", "",
             f"{len(seeds)} seeds, {args.draws} draw(s), {time.time() - started:.0f} s on {args.jobs} cores. Stand-in weeks, not played ones: read README.md of spreadlab/standin for how far to trust them.", ""]
    if args.anchor and args.anchor != DEFAULT:
        lines += [f"Each seed's market is measured on the played week of {args.anchor}, not of the default desk.", ""]
    if not args.baseline:
        lines += [f"**No baseline was named, so this compares with {first}.** For the merge gate pass the current base: `-f baseline=<base variant>`.", ""]
    for arm in names[1:]:
        result, why = verdict(rows, arm, first, args.bar)
        lines.append(f"- **{arm}: {result}**" + (": " + "; ".join(why) if why else ""))
    lines += ["", "```"] + run.table(rows, names) + ["```"]
    if out["errors"]:
        lines += ["", f"{len(out['errors'])} weeks failed and are left out, with their seed in every arm:", "```"] + [f"{a} {s} draw {d}: {e.splitlines()[0]}" for a, s, d, e in out["errors"][:10]] + ["```"]
    (folder / "summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    if out["errors"]:
        print(out["errors"][0][3])


if __name__ == "__main__":
    main()
