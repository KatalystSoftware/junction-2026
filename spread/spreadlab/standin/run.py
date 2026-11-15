"""Plays weeks on the stand-in world and compares arms on the same seeds.

    python -m spreadlab.standin.run --arms slow-friday-late-150-kinds-limits fee16-80-q24-wide-pairs-0.6-return-0.75 \\
        --seeds fresh-13 --limit 40 --draws 2 --jobs 8 --out out.json

The first arm is the one the others are compared with. `--seeds` takes seed names, prefixes of seed names, or a file with one
seed a line; a seed needs a world file, and a week file of `--base` to measure its market from (pack.py makes both from a
recording). `--params` adds an arm that is not in variants.py: name=JSON. Each (arm, seed, draw) is one week of the real desk
code on world.StandIn: nothing here reaches Bahn's server or needs the team key.

It prints, for natural and thin worlds apart (thin is under 720 drivers listed): the margin a week with a week under 90% on time
counted as no margin, the paired difference to the first arm with a bootstrap interval, orders, late orders, the on-time share,
and the weeks under 90% and 92%, as counts and a rate per 60 weeks.
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import random
import time
from multiprocessing import Pool
from pathlib import Path

from spread.starter import DAY

from ..play import policy_class
from ..server import world_map
from ..variants import VARIANTS
from . import fit, model, pack
from .world import StandIn

WEIGHTS = Path(__file__).with_name("weights.json")
THIN = 720


def anchor_of(variant: str, seed: str, weights: dict, prior: float = 15.0) -> dict:
    """How much faster or slower the base week's gigs were booked than the fitted chance says, as a log ratio for each day and for the
    week ("week"): the seed's own driver market, with the day its drivers stayed at home. A day with few bookings stays near the week."""
    rows = fit.week_rows((variant, seed))
    if rows["X"] is None or not len(rows["X"]):
        return {}
    beta = [weights["weights"][name] for name in model.NAMES]
    seen, expected = collections.Counter(), collections.Counter()
    for x, e, y, at in zip(rows["X"], rows["expo"], rows["y"], rows["at"]):
        day = int(at) // DAY
        expected[day] += float(e) * math.exp(max(-30.0, min(3.0, weights["intercept"] + sum(b * float(v) for b, v in zip(beta, x) if v))))
        seen[day] += float(y)
    clip = lambda value: max(-1.0, min(1.0, value))
    week = clip(math.log((sum(seen.values()) + 2 * prior) / (sum(expected.values()) + 2 * prior)))
    out = {day: clip(math.log((seen[day] + prior * math.exp(week)) / (expected[day] + prior))) for day in expected}
    return {**out, "week": week}


def play_week(params: dict, seed: str, base: str | None, weights: dict, design: dict | None = None, draw: int = 0, level: int = 8) -> dict:
    """One week of the desk with these parameters on the stand-in world of the seed."""
    started = time.process_time()
    world_file = pack.load_world(seed)
    has_base = bool(base) and pack.week_path(base, seed).exists()
    base_week = pack.load_week(base, seed) if has_base else None
    map_ = world_map()
    world = StandIn(world_file, base_week, weights, map_, design, draw, anchor_of(base, seed, weights) if has_base else None)
    roster = world.roster()
    desk = policy_class(params)(world, level, 0, params, roster, map_)
    ends_at = world.snapshot()["endsAt"]
    while desk.now < ends_at:
        actions, desk.outbox = desk.outbox, []
        step = world.advance(until=desk.wake_on, max=min(ends_at, (desk.now // DAY + 1) * DAY, desk.wake_at()), actions=actions)
        desk.read_results(actions, step["results"])
        desk.now = step["now"]
        for event in step["events"]:
            desk.handle(event)
        desk.look()
    score = world.score()
    kinds = collections.Counter(e["kind"] for e in world.history)
    late = sum(1 for st in world.state.values() if st["late"])
    # The late orders by when the driver who delivered them booked: after the last pickup that was on time, or before it.
    booked = {oid: gig.get("bookedAt") for gig in world.gigs.values() if gig["status"] == "done" for oid, _ in gig["cars"]}
    after = sum(1 for oid, st in world.state.items() if st["late"] and (booked.get(oid) is None or booked[oid] > world.orders[oid]["lastPickupAt"]))
    return {"late_after": after, "late_in_time": late - after, "seed": seed, "drivers": len(roster), "margin": score["marginCents"] / 100, "orders": score["wonOrders"], "late": late, "on_time": score["onTimeShare"] or 0.0,
            "ledger": {k: v / 100 for k, v in world.ledger.items()}, "booked": kinds["gig_booked"], "dropped": kinds["gig_dropped"], "expired": kinds["gig_expired"],
            "gigs": len(world.gigs), "refused": len(desk.refused), "wave": sorted(world.base["wave"]), "based": has_base, "cpu": round(time.process_time() - started, 1)}


def played_week(variant: str, seed: str) -> dict | None:
    """The same summary of a played week, from its week file."""
    if not pack.week_path(variant, seed).exists():
        return None
    week = pack.load_week(variant, seed)
    ledger = collections.Counter()
    for _, kind, cents, _, _ in week["ledger"]:
        ledger[kind] += cents / 100
    orders = week["score"]["orders"]
    booked = {}
    for gig in week["gigs"]:
        for at, oid, _ in gig["delivered"]:
            booked[oid] = max((b[0] for b in gig["booked"] if b[0] <= at), default=None)
    lates = [oid for oid, o in week["orders"].items() if o.get("late") and not o["cancelled"]]
    after = sum(1 for oid in lates if booked.get(oid) is None or booked[oid] > week["orders"][oid]["lastPickupAt"])
    return {"late_after": after, "late_in_time": len(lates) - after, "seed": seed, "drivers": week["drivers"], "margin": week["score"]["margin"] / 100, "orders": orders, "on_time": week["score"]["on_time"] or 0.0,
            "late": round(orders * (1 - (week["score"]["on_time"] or 0.0))), "ledger": dict(ledger), "booked": sum(len(g["booked"]) for g in week["gigs"]),
            "dropped": sum(1 for g in week["gigs"] for d in g["dropped"] if d[2] == "gig_dropped"), "expired": sum(1 for g in week["gigs"] if g["expired"]),
            "gigs": len(week["gigs"]), "wave": sorted(d for d, n in fit.wave_days(week).items() if n >= fit.WAVE)}


SETUP: dict = {}


def job(task: tuple) -> tuple:
    arm, seed, draw, base = task
    try:
        return arm, seed, draw, play_week(SETUP["arms"][arm], seed, base, SETUP["weights"], SETUP["design"], draw)
    except Exception as error:  # one broken week does not end a screen
        import traceback
        return arm, seed, draw, {"error": f"{error!r}\n{traceback.format_exc()[-1500:]}"}


def interval(diffs: list[float], rounds: int = 2000) -> tuple[float, float]:
    r = random.Random(1)
    means = sorted(sum(r.choices(diffs, k=len(diffs))) / len(diffs) for _ in range(rounds)) if diffs else [0.0]
    return means[int(0.025 * len(means))], means[min(len(means) - 1, int(0.975 * len(means)))]


def ranked(week: dict) -> float:
    """The week's margin as the rule counts it: nothing when under 90% on time."""
    return week["margin"] if week["on_time"] >= 0.90 else 0.0


def table(results: dict, arms: list[str], label: str = "") -> list[str]:
    """`results`: arm -> seed -> [week of each draw]."""
    lines = []
    first = arms[0]
    groups = {"natural": lambda w: w["drivers"] >= THIN, "thin (< 720 drivers)": lambda w: w["drivers"] < THIN, "all": lambda w: True}
    lines.append(f"{label}{'group':22} {'arm':52} {'weeks':>5} {'margin':>7} {'vs 1st':>7} {'95% interval':>16} {'orders':>6} {'late':>5} {'on time':>7} {'lowest':>6} {'<90':>4} {'/60':>5} {'<92':>4}")
    for name, keep in groups.items():
        for arm in arms:
            weeks = [w for seed, ws in results[arm].items() for w in ws if keep(w)]
            if not weeks:
                continue
            diffs = [sum(ranked(a) - ranked(b) for a, b in zip(ws, results[first][seed])) / len(ws) for seed, ws in results[arm].items()
                     if seed in results[first] and keep(ws[0])]
            lo, hi = interval(diffs) if arm != first else (0.0, 0.0)
            n = len(weeks)
            under = sum(w["on_time"] < 0.90 for w in weeks)
            lines.append(f"{label}{name:22} {arm:52} {n:5} {sum(map(ranked, weeks)) / n:7.0f} {sum(diffs) / max(1, len(diffs)):+7.0f} {f'{lo:+.0f} to {hi:+.0f}':>16} "
                         f"{sum(w['orders'] for w in weeks) / n:6.1f} {sum(w['late'] for w in weeks) / n:5.1f} {sum(w['on_time'] for w in weeks) / n:7.3f} "
                         f"{min(w['on_time'] for w in weeks):6.3f} {under:4} {60 * under / n:5.2f} {sum(w['on_time'] < 0.92 for w in weeks):4}")
    return lines


def seeds_for(names: list[str], base: str, limit: int) -> list[str]:
    worlds = sorted(p.name[: -len(".json.gz")] for p in (pack.root() / "worlds").glob("*.json.gz"))
    out: list[str] = []
    for name in names:
        if Path(name).is_file():
            out += [line.strip() for line in Path(name).read_text().splitlines() if line.strip()]
        elif name in worlds:
            out.append(name)
        else:
            out += [s for s in worlds if s.startswith(name) and (not base or pack.week_path(base, s).exists())]
    out = list(dict.fromkeys(out))
    return out[:limit] if limit else out


def run(arms: dict[str, dict], seeds: list[str], base: str | None, weights: dict, design: dict | None, draws: int, workers: int) -> dict:
    SETUP.update(arms=arms, weights=weights, design=design)
    tasks = [(arm, seed, draw, base) for seed in seeds for arm in arms for draw in range(draws)]
    results: dict = {arm: collections.defaultdict(list) for arm in arms}
    errors = []
    with Pool(workers) as pool:
        for arm, seed, draw, week in pool.imap(job, tasks, chunksize=1):
            if "error" in week:
                errors.append((arm, seed, draw, week["error"]))
            else:
                results[arm][seed].append(week)
    for arm in arms:  # a seed counts only with all its draws
        results[arm] = {seed: ws for seed, ws in results[arm].items() if len(ws) == draws}
    return {"results": results, "errors": errors}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--arms", nargs="+", default=[], help="names from variants.py; the first is the one to compare with")
    parser.add_argument("--params", nargs="*", default=[], help="name=JSON: an arm by its parameters")
    parser.add_argument("--seeds", nargs="+", required=True)
    parser.add_argument("--base", default="slow-friday-late-150-kinds-limits", help="the played variant whose weeks measure each seed's market")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--draws", type=int, default=1)
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--weights", default=str(WEIGHTS))
    parser.add_argument("--design", default="{}", help="JSON: world.DESIGN options")
    parser.add_argument("--out", default="")
    args = parser.parse_args()
    arms = {name: VARIANTS[name] for name in args.arms}
    for text in args.params:
        name, _, value = text.partition("=")
        arms[name] = json.loads(value)
    seeds = seeds_for(args.seeds, args.base, args.limit)
    weights = json.loads(Path(args.weights).read_text())
    started = time.time()
    out = run(arms, seeds, args.base, weights, json.loads(args.design), args.draws, args.jobs)
    print(f"{len(seeds)} seeds, {args.draws} draws, base {args.base}, {time.time() - started:.0f} s")
    print("\n".join(table(out["results"], list(arms))))
    for arm, seed, draw, error in out["errors"][:5]:
        print(f"ERROR {arm} {seed} draw {draw}: {error}")
    if args.out:
        Path(args.out).write_text(json.dumps({"arms": arms, "seeds": seeds, "base": args.base, "design": json.loads(args.design), "draws": args.draws, **out}) + "\n")


if __name__ == "__main__":
    main()
