"""The stand-in against played weeks, arm by arm on the same seeds.

    python -m spreadlab.standin.check --arms steep-notes-offers-8 slow-friday-late-150-kinds-limits --base steep-notes-offers-8 --seeds fresh-13 --limit 40

For each arm that has played weeks on the seeds it prints the stand-in's week beside the played one: margin, orders, late orders,
the on-time share, the money lines, bookings, drops and expired gigs, and how the two go together seed by seed. With `--base`
set to another arm than the one checked, the arm's own weeks are not used to play it.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from ..variants import VARIANTS
from . import pack, run


def corr(a: list[float], b: list[float]) -> float:
    n = len(a)
    if n < 3:
        return float("nan")
    ma, mb = sum(a) / n, sum(b) / n
    va, vb = sum((x - ma) ** 2 for x in a), sum((y - mb) ** 2 for y in b)
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / math.sqrt(va * vb) if va and vb else float("nan")


def compare(arm: str, sim: dict, played: dict) -> list[str]:
    seeds = [s for s in sim if s in played]
    mean = lambda rows, f: sum(f(r) for r in rows) / max(1, len(rows))
    s_rows, p_rows = [w for s in seeds for w in sim[s]], [played[s] for s in seeds]
    lines = [f"{arm}: {len(seeds)} seeds"]
    for name, f in (("margin", lambda w: w["margin"]), ("orders", lambda w: w["orders"]), ("late", lambda w: w["late"]), ("late, booked after", lambda w: w["late_after"]), ("late, booked before", lambda w: w["late_in_time"]), ("on time", lambda w: w["on_time"]),
                    ("revenue", lambda w: w["ledger"].get("revenue", 0)), ("driver fees", lambda w: -w["ledger"].get("driver_fee", 0)),
                    ("late refunds", lambda w: -w["ledger"].get("late_refund", 0)), ("bookings", lambda w: w["booked"]), ("drops", lambda w: w["dropped"]),
                    ("expired gigs", lambda w: w["expired"]), ("gigs", lambda w: w["gigs"])):
        by_seed = [mean(sim[s], f) for s in seeds]
        lines.append(f"  {name:19} stand-in {mean(s_rows, f):10.2f}  played {mean(p_rows, f):10.2f}  ratio {mean(s_rows, f) / mean(p_rows, f) if mean(p_rows, f) else float('nan'):5.2f}"
                     f"  r by seed {corr(by_seed, [f(played[s]) for s in seeds]):5.2f}")
    for line_ in (0.90, 0.92):
        lines.append(f"  weeks under {line_:.0%}: stand-in {sum(w['on_time'] < line_ for w in s_rows) / max(1, len(s_rows)) * 60:5.2f} per 60, played {sum(w['on_time'] < line_ for w in p_rows) / max(1, len(p_rows)) * 60:5.2f} per 60"
                     f" ({sum(w['on_time'] < line_ for w in p_rows)} of {len(p_rows)})")
    low = sorted(seeds, key=lambda s: played[s]["on_time"])[:6]
    lines.append("  lowest played weeks, on time played / stand-in: " + ", ".join(f"{s} {played[s]['on_time']:.3f}/" + "/".join(f"{w['on_time']:.3f}" for w in sim[s]) for s in low))
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--arms", nargs="+", required=True)
    parser.add_argument("--seeds", nargs="+", required=True)
    parser.add_argument("--base", default="slow-friday-late-150-kinds-limits")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--draws", type=int, default=1)
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--weights", default=str(run.WEIGHTS))
    parser.add_argument("--design", default="{}")
    parser.add_argument("--out", default="")
    args = parser.parse_args()
    seeds = run.seeds_for(args.seeds, args.base, 0)
    seeds = [s for s in seeds if all(pack.week_path(arm, s).exists() for arm in args.arms)]
    seeds = seeds[: args.limit] if args.limit else seeds
    arms = {}
    for name in args.arms:  # an arm that variants.py no longer names plays by the parameters its played weeks saved
        arms[name] = VARIANTS.get(name) or {k: v for k, v in pack.load_week(name, seeds[0])["params"].items()}
    out = run.run(arms, seeds, args.base, json.loads(Path(args.weights).read_text()), json.loads(args.design), args.draws, args.jobs)
    played = {arm: {s: run.played_week(arm, s) for s in seeds} for arm in arms}
    for arm in arms:
        print("\n".join(compare(arm, out["results"][arm], played[arm])))
    for arm, seed, draw, error in out["errors"][:3]:
        print(f"ERROR {arm} {seed} draw {draw}: {error}")
    if args.out:
        Path(args.out).write_text(json.dumps({"seeds": seeds, "base": args.base, "sim": out["results"], "played": played}) + "\n")


if __name__ == "__main__":
    main()
