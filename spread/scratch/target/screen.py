"""Scratch: an offline screen of the on-time target variants (`target-93`, `target-91`) against the default on recorded weeks.

A recording cannot score a policy that quotes otherwise, so this only says whether a variant is worth playing. It replays
each recorded week of a base variant in the stand-in of scratch/opt/sim.py, quote by quote, once under the default's cost
rule and once under each target rule, on the same luck: the dealers answer by the win curve with each quote's hidden draw
held to the recorded answer, the competitor answers what the desk wins (react 0.6, scratch/opt/calibrate.py), what is won
fills the backlog, and a new order ends late by the late model fitted on the base's weeks with an intercept for its week
and for the day its car must be collected. That day's intercept is what carries a night when drivers drop their gigs into
the new orders due that day; the desk's rule never sees it, as the live desk would not.

The rules are policy.py's quote cost for a one-car dealer request, in cents, with the late chance known at the quote:
    fee x (1.2 + slow_step x waiting cars x p) + 100 x (late_cost x p + rule_cost x (p - 0.10)), never under the fee,
and no quote while `max_unbooked` cars wait. The default: slow_step 0.8, late_cost 150, gate 25. target-T: slow_step 0.4,
late_cost 85, gate 40; once 40 orders are won and the projected on-time share (policy.Policy.on_time) is under T, slow_step
0.8, late_cost 150, rule_cost 800 and gate 12.

What it cannot see: driver fees rising with volume beyond a fixed load (2.6% of the typical fee for each 100 more orders),
drivers getting scarcer beyond the late model's waiting-car terms, private and trade-in requests (both rules alike), and
whether the projected share is rebuilt the same after a restart.

    PYTHONPATH=. uv run --with numpy python scratch/target/screen.py extract all       # each base's weeks as rows, once: 8 minutes on 2 cores
    PYTHONPATH=. uv run --with numpy python scratch/target/screen.py screen slow-friday-late-150-kinds-limits 2   # the default's weeks, 2 draws
    PYTHONPATH=. uv run --with numpy python scratch/target/screen.py screen all 1 quick  # every base, each with its own late model

Words after the draws: `react-0` (no competitor answer), `week-only` (no due-day intercept), `fitted-p` (the rules price
with the stand-in's late model in place of slow.py's), `quick` (no unguarded rule), `extra` (also target-95, and the default's surcharge on the cars due within 24 hours alone,
without and with the guard at 93%).
"""
from __future__ import annotations

import collections
import json
import math
import pickle
import random
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / "gap"), str(HERE.parent / "opt")]
import lib  # noqa: E402
import sim  # noqa: E402

from spreadlab import curve, slow  # noqa: E402
from spreadlab.server import data_dir, near_places  # noqa: E402

DAY, THIN, FRIDAY, WAVE, LOAD = 1440, 720, 4, 10, 0.026
OPTIONS = set(sys.argv[4:])
REACT = 0.0 if "react-0" in OPTIONS else 0.6
SLOW = "fitted-p" not in OPTIONS
B = sim.B
OUT = data_dir() / "screen-target"
MAP = json.loads((data_dir() / "map.json").read_text())
MINUTES, NEAR = lib.minutes_of(MAP), near_places(MAP)


def quotes_levels(w: dict) -> tuple[dict, dict]:
    """The recorded quotes (scratch/gap/price.py): the curve's log odds at list price with the dealer's trust, the multiple
    quoted and the answer; and each day's level fitted on the whole day's answers."""
    changes = collections.defaultdict(list)
    for o in w["orders"].values():
        if o["delivered"] is not None and not o["cancelled"]:
            changes[o["dealer"]].append((o["delivered"], not o["late"]))
    for d in changes:
        changes[d].sort()

    def trust_at(dealer, minute):
        c = 0
        for at, ok in changes.get(dealer, []):
            if at > minute:
                break
            c = min(25, c + 1) if ok else c // 2
        return c

    quotes, byday = {}, collections.defaultdict(list)
    for rid, r in w["reqs"].items():
        dec = w["decisions"][rid]
        if dec["declined"]:
            continue
        q = r["request"]
        options = [o for o in q["options"] if o["kind"] in dec["prices"]]
        first = curve.fastest(options)
        a = curve.at_list(q, options, trust_at(q["dealerId"], q["arrivedAt"]), sim.M)
        m, won, day = dec["prices"][first["kind"]] / first["listPriceCents"], r["outcome"] == "won", q["arrivedAt"] // DAY
        quotes[(0, rid)] = {"a": a, "m": m, "won": won, "day": day}
        byday[day].append((a - B * math.log(m), won))

    def fit(answers, sd=0.3):
        d = 0.0
        for _ in range(30):
            ch = [1 / (1 + math.exp(-(z + B * d))) for z, _ in answers]
            d += max(-0.3, min(0.3, (B * sum(won - c for (_, won), c in zip(answers, ch)) - d / sd ** 2) / (B * B * sum(c * (1 - c) for c in ch) + 1 / sd ** 2)))
        return d

    level = {(0, day): fit(v) for day, v in byday.items()}
    for q in quotes.values():
        q["s"] = level[(0, q["day"])]
    return quotes, level


def waiting(w: dict) -> dict:
    """The won cars without a driver at each request, by when their order must be collected (scratch/gap/backlog.py)."""
    out, orders = {}, {}
    for e in sorted((e for v in w["ev"].values() for e in v), key=lambda e: e["seq"]):
        k = e["kind"]
        if k == "price_request":
            now, open_ = e["at"], [o for o in orders.values() if not o["booked"]]
            out[(0, e["request"]["id"])] = {"u8": sum(o["last"] - now <= 480 for o in open_), "u24": sum(480 < o["last"] - now <= 1440 for o in open_),
                                            "ulater": sum(o["last"] - now > 1440 for o in open_)}
        elif k == "order_won":
            orders[e["order"]["id"]] = {"booked": False, "last": e["order"]["lastPickupAt"]}
        elif k == "order_changed" and e["order"]["id"] in orders:
            orders[e["order"]["id"]]["last"] = e["order"]["lastPickupAt"]
        elif k == "gig_booked" or k in ("gig_dropped", "no_show", "gig_expired"):
            for oid in w["gig_orders"].get(e["gigId"], []):
                if oid in orders:
                    orders[oid]["booked"] = k == "gig_booked"
        elif k == "visit_failed" and e["orderId"] in orders:
            orders[e["orderId"]]["booked"] = False
        elif k in ("delivered", "order_cancelled"):
            orders.pop(e["orderId"], None)
    return out


def extract(path: str) -> dict:
    w = lib.week(path, MINUTES)
    quotes, level = quotes_levels(w)
    reqs, took = sim.week_rows(0, w, quotes, waiting(w), level, MINUTES, NEAR)
    for row in reqs:  # the late chance that the desk prices with (slow.py, the default's model)
        q = w["reqs"][row["rid"]]["request"]
        fastest = curve.fastest([o for o in q["options"] if o["kind"] in row["lists"]])
        row["p"] = slow.chance(slow.known(q, fastest, row["notified"], row["drive"], len(w["roster"])), slow.MODELS["friday"])
    first_hour = collections.Counter(e["at"] // DAY for kind in ("gig_dropped", "no_show") for e in w["ev"][kind] if e["at"] % DAY < 60)
    due = collections.Counter(o["lastPickupAt"] // DAY for o in w["orders"].values() if not o["cancelled"])
    return {"seed": w["seed"], "drivers": len(w["roster"]), "score": w["score"], "reqs": reqs, "took": {k: dict(v) for k, v in took.items()},
            "friday_due": due[FRIDAY], "friday_wave": first_hour[FRIDAY], "waves": sum(n >= WAVE for n in first_hour.values())}


def rule(slow_step: float, late_cost: float, gate: int, target: float = 0.0, weeks=None, count=None, within_24: bool = False):
    """The quote cost of policy.py for the stand-in (see the module's docstring). `within_24` counts in the surcharge only the
    waiting cars due within 24 hours, which policy.py cannot do yet: a screen of that idea, not of a variant."""
    def cost(row, parts, trust, desk):
        behind = bool(target) and desk["orders"] >= 40 and desk["on_time"] < target
        step, late, rule_cost, limit = (0.8, 150, 800, 12) if behind else (slow_step, late_cost, 0, gate)
        if count is not None:
            count["quotes"] += 1; count["behind"] += behind
        if sum(parts) >= limit:
            return None
        p = row["p"] if SLOW else weeks.late(row, (0, 0, 0))
        counted = parts[0] + parts[1] if within_24 and not behind else sum(parts)
        return max(row["fee"], row["fee"] * (1.2 + step * counted * p) + 100 * (late * p + rule_cost * (p - 0.10)))
    return cost


WEEKS, RULES = None, {}  # set before the pool forks


def run(job: tuple[str, int, list[int]]) -> tuple[list[dict], collections.Counter]:
    name, draw, on = job
    count = collections.Counter()
    out = sim.simulate(WEEKS, RULES[name](count), on, draw=draw, react=REACT)
    return out, count


def interval(diffs: dict[str, list[float]], draws: int = 2000) -> tuple[float, float]:
    """The 95% interval of the mean difference, drawing the seeds again: a seed's weeks under several bases and draws go together."""
    rng, seeds = random.Random(1), list(diffs.values())
    means = []
    for _ in range(draws):
        picked = [rng.choice(seeds) for _ in seeds]
        means.append(sum(map(sum, picked)) / sum(map(len, picked)))
    means.sort()
    return means[int(0.025 * draws)], means[int(0.975 * draws)]


def load(saved: list[dict]) -> sim.Weeks:
    weeks = object.__new__(sim.Weeks)
    weeks.seeds, weeks.drivers, weeks.played, weeks.W = [], [], [], []
    weeks.pool, weeks.took = collections.defaultdict(list), collections.defaultdict(collections.Counter)
    for s in saved:
        weeks.add(s["seed"], s["drivers"], s["score"], s["reqs"], s["took"])
    weeks.finish()
    return weeks


def screen(base: str, draws: int, names: list[str]) -> tuple[list[dict], dict]:
    """Each recorded week of the base under each rule: one record a week with the stand-in's result for each rule and draw."""
    global WEEKS
    saved = pickle.load(open(OUT / f"{base}.pkl", "rb"))
    weeks = load(saved)
    on = list(range(len(weeks.W)))
    weeks.fit(on, by_day="week-only" not in OPTIONS)
    WEEKS = weeks
    rules = {"default": lambda c: rule(0.8, 150, 25, weeks=weeks), "target-93": lambda c: rule(0.4, 85, 40, 0.93, weeks, c),
             "target-91": lambda c: rule(0.4, 85, 40, 0.91, weeks, c), "no guard": lambda c: rule(0.4, 85, 40, weeks=weeks),
             "target-95": lambda c: rule(0.4, 85, 40, 0.95, weeks, c), "default 24h": lambda c: rule(0.8, 150, 25, weeks=weeks, within_24=True),
             "target-93 24h": lambda c: rule(0.8, 150, 25, 0.93, weeks, c, within_24=True)}
    RULES.clear(); RULES.update({name: rules[name] for name in names})
    chunks = [on[i::8] for i in range(8)]
    jobs = [(name, d, chunk) for name in names for d in range(draws) for chunk in chunks if chunk]
    with Pool(2) as pool:
        done = pool.map(run, jobs, chunksize=1)
    records = [{"base": base, **{k: s[k] for k in ("seed", "drivers", "score", "friday_due", "friday_wave")}, "res": {name: [None] * draws for name in names}}
               for s in saved]
    counts = collections.defaultdict(collections.Counter)
    for (name, d, chunk), (out, count) in zip(jobs, done):
        for i, wk in zip(chunk, out):
            records[i]["res"][name][d] = wk
        counts[name].update(count)
    return records, counts


GROUPS = {
    "all": lambda s: True,
    "natural (fresh-)": lambda s: s["seed"].startswith("fresh-"),
    f"thin (< {THIN} drivers)": lambda s: s["drivers"] < THIN,
    "Friday-heavy (>= 100 due Fri)": lambda s: s["friday_due"] >= 100,
    f"Friday wave (>= {WAVE} drops 00-01 Fri)": lambda s: s["friday_wave"] >= WAVE,
    "Friday-heavy and wave": lambda s: s["friday_due"] >= 100 and s["friday_wave"] >= WAVE,
}


def report(records: list[dict], draws: int, names: list[str]) -> None:
    head = (f"{'group':38} {'rule':10} {'weeks':>5} {'margin':>7} {'vs dflt':>7} {'95% interval':>15} {'orders':>6} {'late':>5} {'mean OT':>7} {'lowest':>6} {'<90':>4}"
            f" {'<90/60':>6} {'<92':>4} {'unzeroed':>8}")
    print("\nMargin a week in euros over the stand-in's requests, a week under 90% counted as 0; driver fees loaded 2.6% of the typical fee for each 100 more orders"
          " than the default; 'unzeroed' is the difference to the default without that zero. Weeks and counts are over all draws.\n" + head)
    for gname, keep in GROUPS.items():
        kept = [r for r in records if keep(r)]
        if not kept:
            continue
        for name in names:
            rows, diffs, raw, by_seed = [], [], [], collections.defaultdict(list)
            for r in kept:
                for d in range(draws):
                    a, b = r["res"][name][d], r["res"]["default"][d]
                    m = a["margin"] - LOAD * max(0.0, a["orders"] - b["orders"]) / 100 * a["typ"] / 100
                    rows.append((m if a["on_time"] >= 0.90 else 0.0, a))
                    diffs.append((m if a["on_time"] >= 0.90 else 0.0) - (b["margin"] if b["on_time"] >= 0.90 else 0.0))
                    raw.append(m - b["margin"]); by_seed[r["seed"]].append(diffs[-1])
            n = len(rows)
            lo, hi = interval(by_seed) if name != "default" else (0.0, 0.0)
            under90 = sum(a["on_time"] < 0.90 for _, a in rows)
            print(f"{gname:38} {name:10} {n:5} {sum(m for m, _ in rows) / n:7.0f} {sum(diffs) / n:+7.0f} {f'{lo:+.0f} to {hi:+.0f}':>15} {sum(a['orders'] for _, a in rows) / n:6.1f}"
                  f" {sum(a['late'] for _, a in rows) / n:5.1f} {sum(a['on_time'] for _, a in rows) / n:7.3f} {min(a['on_time'] for _, a in rows):6.3f} {under90:4} {60 * under90 / n:6.2f}"
                  f" {sum(a['on_time'] < 0.92 for _, a in rows):4} {sum(raw) / n:+8.0f}")
        print()
    lowest = sorted(records, key=lambda r: min(r["res"]["target-93"][d]["on_time"] for d in range(draws)))[:10]
    print("The lowest weeks of target-93 (on time by draw), with the other rules:")
    for r in lowest:
        print(f"  {r['base'][:28]:28} {r['seed']:12} drivers {r['drivers']:4} Fri due {r['friday_due']:3} Fri wave {r['friday_wave']:3} recorded {r['score']['onTimeShare']:.3f}  "
              + "  ".join(f"{name} " + "/".join(f"{r['res'][name][d]['on_time']:.3f}" for d in range(draws)) for name in names))


def main() -> None:
    action, which = sys.argv[1], sys.argv[2]
    OUT.mkdir(parents=True, exist_ok=True)
    every = sorted(p.name for p in (data_dir() / "runs").iterdir() if p.is_dir())
    if action == "extract":
        for base in every if which == "all" else which.split(","):
            cache = OUT / f"{base}.pkl"
            if which == "all" and cache.exists():
                continue
            paths = lib.runs(str(data_dir()), base)
            with Pool(2) as pool:
                weeks = [w for w in pool.imap(extract_safe, paths, chunksize=2) if w is not None]
            pickle.dump(weeks, open(cache, "wb"))
            print(f"{len(weeks)} of {len(paths)} weeks of {base} -> {cache}", flush=True)
        return
    draws = int(sys.argv[3]) if len(sys.argv) > 3 else 2
    bases = [b for b in every if (OUT / f"{b}.pkl").exists()] if which == "all" else which.split(",")
    names = ["default", "target-93", "target-91"] + ([] if "quick" in OPTIONS else ["no guard"]) + (["target-95", "default 24h", "target-93 24h"] if "extra" in OPTIONS else [])
    records, counts, skipped = [], collections.defaultdict(collections.Counter), []
    for base in bases:
        done = OUT / f"result-{base}-{draws}-{'-'.join(sorted(OPTIONS))}.pkl"
        try:
            recs, cnt = pickle.load(open(done, "rb")) if done.exists() else screen(base, draws, names)
        except (ValueError, ZeroDivisionError, OverflowError, np.linalg.LinAlgError, KeyError, IndexError) as e:  # too few won orders to fit or replay
            skipped.append(f"{base} ({type(e).__name__})")
            continue
        pickle.dump((recs, cnt), open(done, "wb"))
        own = [r["res"]["default"][d] for r in recs for d in range(draws)]
        if sum(w["on_time"] for w in own) / len(own) < 0.90:  # the default's rule far under its 96% on these weeks: the late model does not fit the base
            skipped.append(f"{base} (the default's rule at {sum(w['on_time'] for w in own) / len(own):.0%} on time)")
            continue
        records += recs
        for name, c in cnt.items():
            counts[name].update(c)
        played = [r["score"] for r in recs]
        own = [r["res"]["default"][d] for r in recs for d in range(draws)]
        print(f"{base}: {len(recs)} weeks; the default's rule {sum(w['orders'] for w in own) / len(own):.1f} orders and {sum(w['on_time'] for w in own) / len(own):.3f} on time,"
              f" the recording {sum(p['wonOrders'] for p in played) / len(played):.1f} and {sum(p['onTimeShare'] for p in played) / len(played):.3f}", flush=True)
    print(f"\n{len(records)} weeks from {len(bases) - len(skipped)} bases, {draws} draws, react {REACT}, options {sorted(OPTIONS) or 'none'}")
    if skipped:
        print("skipped: " + ", ".join(skipped))
    for name in ("target-93", "target-91"):
        print(f"{name}: behind at {counts[name]['behind'] / max(1, counts[name]['quotes']):.1%} of its quotes")
    report(records, draws, names)


def extract_safe(path: str):
    try:
        return extract(path)
    except (KeyError, IndexError, TypeError, ValueError):  # an old recording without a field the rows need
        return None


if __name__ == "__main__":
    main()
