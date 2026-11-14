"""Scratch: an offline screen of the out-and-back pair variants (spreadlab/pairs.py) on the archive's recorded weeks,
before any of them plays. A recording cannot score a policy that acts differently: its dealers answered other quotes and
its drivers saw other gigs. So the screen only says whether a variant is worth playing. It runs PairPolicy over each
recorded week with that week's own requests and its own wins, and checks:

1. Mechanics, on every recorded week: no error, and every action the world would accept. That means no stop window that
   has ended, at most 12 hours of driving in a gig with two cars, no car in two live gigs, and no held car kept past its
   release minute.
2. Volume: pairs a week from the recording's real wins, on the weeks of the base and its family (the variants nearest to
   it). Under 10 pairs a week is not worth playing.
3. Held cars without a return: they are posted up to 4 hours later than in the recording. Their late share is read off
   the recordings' late share of one-car dealer orders by the hours from the first post to the last pickup minute, at
   the recorded post and at the held one. More than 1 point later fails, as in the plan.
4. The pair's fee: no dealer pair gig was ever played. The nearest gigs are trade-ins, one car out and one back. They are
   read by their opening fee over their typical fee, mapped to a pair's fee by the typical cents a drive minute of each
   kind. Fewer than 50% booked within the hour at the mapped fee fails (the plan's stop), and the 2-hour share should be 75%.
5. Money, on the base family's weeks: the fees saved by each pair against what its two cars were paid alone in the
   recording, at the opening fee and at the top. A pair waits for the slower of its two cars' recorded waits, and goes
   back to two gigs when that is too late. Less the late cost of the held cars, at 150 euros an order.
6. The return quote (`-return-0.75`): for each request that could run back with a held car, the policy's quote at the
   usual cost and at 0.75, the curve's chance of each with the day's correction, and the expected margin at the return's
   true extra cost. When it pairs, that cost is the pair's fee less what the held car would have cost alone; when it does
   not, the cost in the quote. It fails when the lower quote earns less.

    SPREAD_DATA=... PYTHONPATH=. uv run python scratch/pairs_screen.py [--variants v1,v2] [--limit N] [--out screen.jsonl]
    SPREAD_DATA=... PYTHONPATH=. uv run python scratch/pairs_screen.py --read screen.jsonl
"""
from __future__ import annotations

import argparse
import collections
import copy
import gzip
import json
import math
import statistics
import sys
import traceback
from multiprocessing import Pool
from pathlib import Path

from spreadlab import curve, notes
from spreadlab.late_wide import WidePairPolicy
from spreadlab.pairs import PairPolicy
from spreadlab.policy import Policy, kind
from spreadlab.server import data_dir
from spreadlab.variants import VARIANTS

def cached(fn):
    """The note readers, kept per note and minute: the policy reads the same note at each quote and post."""
    memo = {}

    def wrapper(note, at):
        key = (json.dumps(note, sort_keys=True), at)
        if key not in memo:
            memo[key] = fn(note, at)
        return memo[key]
    return wrapper


notes.limits, notes.read = cached(notes.limits), cached(notes.read)
SCREENED = "slow-friday-late-150-kinds-limits-pairs-0.7-return-0.75"  # the fee does not change what the desk does; the money is read for each fee below
FAMILY = ["slow-friday-late-150-kinds-limits", "slow-friday-late-150-kinds", "slow-step-gate-25-kinds-limits", "slow-step-gate-25-kinds", "search-16-kinds"]
FEES = (0.6, 0.7, 0.8)
LATE_EUROS = 150
BINS = [10, 12, 14, 16, 18, 20, 24, 30, 40, 10**6]  # hours from the first post to the last pickup minute
SKIP = {"gig_booked", "gig_dropped", "gig_started", "gig_expired", "visit_failed", "no_show", "offer_answered", "picked_up", "release", "driver_late"}


def hour_bin(minutes: float) -> int:
    return next(i for i, edge in enumerate(BINS) if minutes / 60 < edge)


def sig(v: float) -> float:
    return 1 / (1 + math.exp(-v)) if v > -500 else 0.0


class World:
    """Accepts what the world would accept, and books a gig after its cars' recorded wait."""

    def __init__(self, map_: dict, waits: dict[str, int | None]):
        self.minutes = {(r["from"], r["to"]): r["minutes"] for r in map_["roads"]}
        self.waits, self.n, self.now = waits, 0, 0
        self.live: dict[tuple, str] = {}  # (order id, leg) -> gig
        self.gigs: dict[str, dict] = {}  # gig id -> post, posted at, book at
        self.violations: list[str] = []
        self.orders: dict[str, dict] = {}

    def act(self, actions):
        out = []
        for a in actions:
            if a["type"] == "post":
                self.n += 1
                gig_id = f"S{self.n}"
                cars = [(s["orderId"], s["leg"]) for s in a["stops"] if s["kind"] == "pickup"]
                for s in a["stops"]:
                    if "window" in s and s["window"]["to"] < self.now:
                        self.violations.append(f"{self.now}: a stop window of {s['orderId']} ended at {s['window']['to']}")
                ids = list(dict.fromkeys(c[0] for c in cars))
                if len(cars) > 1:
                    places = [self.orders[s["orderId"]]["legs"][s["leg"]][s["kind"]]["placeId"] for s in a["stops"]]
                    drive = sum(self.minutes[(x, y)] for x, y in zip(places, places[1:]))
                    if drive > 720 and len(ids) == 1:  # a trade-in over the limit: the world refuses it, and the desk posts each car alone
                        out.append({"ok": False, "reason": "12 hours"})
                        continue
                    if drive > 720:
                        self.violations.append(f"{self.now}: {drive} minutes of driving in a pair gig")
                for car in cars:
                    if car in self.live:
                        self.violations.append(f"{self.now}: {car} posted while in live gig {self.live[car]}")
                    self.live[car] = gig_id
                waits = [self.waits.get(i) for i in ids]
                book = None if any(w is None for w in waits) else self.now + max(waits)
                self.gigs[gig_id] = {"post": a, "at": self.now, "book": book, "ids": ids, "cars": cars}
                out.append({"ok": True, "id": gig_id})
            else:
                if a["type"] == "withdraw":
                    self.drop(a["gigId"])
                out.append({"ok": True})
        return out

    def drop(self, gig_id: str) -> None:
        for car in self.gigs[gig_id]["cars"]:
            if self.live.get(car) == gig_id:
                del self.live[car]


class Screening:
    """The pair desk that also notes, for each return quote, the quote the policy would have sent at its usual cost."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.return_quotes: list[dict] = []

    def answer(self, request, prices) -> tuple[float, float]:
        """The curve's chance at these prices with today's correction, and the price of the fastest option quoted."""
        dealer, day, log_odds = self.asked[request["id"]]
        shift = self.shift(day, self.params(), request["legs"][0]["pickup"]["placeId"])
        fastest = curve.fastest([o for o in request["options"] if o["kind"] in prices])
        return sig(log_odds + self.model["slope"] * shift), prices[fastest["kind"]]

    def quote(self, request) -> None:
        self.requests[request["id"]] = request
        partner = self.partner(request) if self.p["pair_hold"] else None
        if partner is None:
            return super().quote(request)
        dealer = request["dealerId"]
        before = self.requested.get(dealer, 0)
        Policy.quote(self, request)  # self.pairing is False here: the usual cost
        self.outbox.pop()
        self.requested[dealer] = before
        hi = self.answer(request, self.decisions[request["id"]]["prices"])
        super().quote(request)
        lo = self.answer(request, self.decisions[request["id"]]["prices"])
        self.return_quotes.append({"id": request["id"], "partner": partner, "hi": hi, "lo": lo, "typical": request["referenceFeeCents"],
                             "partner_typical": self.requests[partner]["referenceFeeCents"]})


class Screen(Screening, PairPolicy):
    pass


class ScreenWide(Screening, WidePairPolicy):
    pass


def screen(path: str) -> dict:
    run = json.loads(gzip.open(path).read())
    out = {"path": path, "variant": run["variant"], "seed": run["seed"]}
    try:
        events = sorted(run["events"], key=lambda e: e["seq"])
        gigs = run["gigs"]
        order_of = {g["id"]: g["stops"][0]["orderId"] for g in gigs}
        first_post, first_book, fees, late = {}, {}, collections.Counter(), set()
        for g in sorted(gigs, key=lambda g: g["postedAt"]):
            first_post.setdefault(order_of[g["id"]], g["postedAt"])
        won = {}
        for e in events:
            if e["kind"] == "gig_booked":
                first_book.setdefault(order_of.get(e["gigId"]), e["at"])
            elif e["kind"] == "order_won":
                won[e["order"]["id"]] = e
            elif e["kind"] == "ledger" and e["line"].get("orderId"):
                if e["line"]["kind"] in ("late_refund", "undelivered_penalty"):
                    late.add(e["line"]["orderId"])
            if e["kind"] == "ledger" and e["line"]["kind"] == "driver_fee" and e["line"].get("gigId") in order_of:
                fees[order_of[e["line"]["gigId"]]] -= e["line"]["cents"]
        waits = {i: first_book[i] - first_post[i] if i in first_book and i in first_post else None for i in won}
        requests = {e["request"]["id"]: e["request"] for e in events if e["kind"] == "price_request"}
        # The recordings' late share by the hours from the first post to the last pickup minute, one-car dealer orders.
        slack = [(hour_bin(e["order"]["lastPickupAt"] - first_post[i]), i in late, fees[i] / requests[i]["referenceFeeCents"])
                 for i, e in won.items() if i in first_post and len(e["order"]["legs"]) == 1 and kind(requests[i]) == ""]
        out["slack"] = slack
        map_ = json.loads((data_dir() / "map.json").read_text())
        world = World(map_, waits)
        params = VARIANTS[SCREENED]
        desk_class = ScreenWide if params.get("late_wide") else Screen  # as play.py takes the desk
        d = desk_class(world, 8, 0, params, run["roster"], map_)

        def until(t: int) -> None:
            for _ in range(10_000):
                due = [g for g, x in world.gigs.items() if x["book"] is not None and x["book"] <= t and g not in d.booked
                       and any(world.live.get(c) == g for c in x["cars"])]
                wake = d.wake_at()
                nxt = min([wake] + [world.gigs[g]["book"] for g in due])
                if nxt > t:
                    return
                world.now = d.now = max(d.now, nxt)
                for g in due:
                    if world.gigs[g]["book"] <= d.now:
                        d.booked.add(g)
                if wake <= d.now:
                    d.look()
                d.send()
            raise RuntimeError("the desk wakes in a loop")

        for e in events:
            if e["kind"] in SKIP:
                continue
            until(e["at"])
            world.now = d.now = max(d.now, e["at"])
            e = copy.deepcopy(e)
            if e["kind"] in ("order_won", "order_changed"):
                o = e["order"]
                ours = d.orders.get(o["id"])
                o["deliveredAt"] = list(ours["deliveredAt"]) if ours else [None] * len(o["legs"])
                if e["kind"] == "order_won":
                    if o["id"] not in d.requests:
                        continue
                    world.orders[o["id"]] = o
                elif o["id"] not in d.orders:
                    continue
                else:
                    world.orders[o["id"]] = o
            elif e["kind"] == "order_cancelled":
                mine = d.gigs_of(e["orderId"])
                e["gigs"] = [{"gigId": g, "outcome": ("shortened" if len(world.gigs[g]["ids"]) > 1 else "released") if g in d.booked else "withdrawn"}
                             for g in mine]
                for g, outcome in zip(mine, e["gigs"]):
                    for car in world.gigs[g]["cars"]:  # an open gig leaves the app whole; a booked one keeps the other order's car
                        if (car[0] == e["orderId"] or outcome["outcome"] == "withdrawn") and world.live.get(car) == g:
                            del world.live[car]
            elif e["kind"] == "deadline_close":
                if e["orderId"] not in d.orders or any(g in d.booked for g in d.gigs_of(e["orderId"])):
                    continue
            elif e["kind"] == "delivered":
                g = d.leg_gigs.get(e["orderId"], {}).get(e["leg"])
                if g is None or g not in d.booked:
                    continue
                e["gigId"] = g
                world.live.pop((e["orderId"], e["leg"]), None)
            elif e["kind"] == "gig_viewed":
                e["gigId"] = None
            d.handle(e)
            d.send()
            for i, until_ in d.pair_wait.items():
                if until_ < d.now - 1:
                    world.violations.append(f"{d.now}: {i} still held after {until_}")
        until(events[-1]["at"])
        held = {i: dec["held"] for i, dec in d.decisions.items() if "held" in dec}
        pairs = collections.defaultdict(list)
        for i, dec in d.decisions.items():
            if "gig" in dec.get("paired", {}):
                pairs[dec["paired"]["gig"]].append(i)
        out["pairs"] = []
        for g, ids in pairs.items():
            x = world.gigs[g]
            split = any("split" in d.decisions[i]["paired"] for i in ids)
            out["pairs"].append({"typical": sum(requests[i]["referenceFeeCents"] for i in ids), "alone": sum(fees[i] for i in ids),
                                 "booked_after": None if g not in d.booked else x["book"] - x["at"], "split": split,
                                 "late_alone": sum(i in late for i in ids)})
        out["held"] = len(held)
        out["alone"] = [{"rec": hour_bin(won[i]["order"]["lastPickupAt"] - first_post[i]), "cf": hour_bin(won[i]["order"]["lastPickupAt"] - h["alone"])}
                        for i, h in held.items() if "alone" in h and i in first_post]
        out["splits"] = collections.Counter(d.decisions[i]["paired"]["split"]["why"] for ids in pairs.values() for i in ids if "split" in d.decisions[i]["paired"])
        out["returns"] = [{**r, "won": r["id"] in won, "partner_fee": fees.get(r["partner"], 0), "paired": r["id"] in d.decisions and "gig" in d.decisions[r["id"]].get("paired", {})}
                          for r in d.return_quotes]
        out["violations"] = world.violations[:5]
        out["n_violations"] = len(world.violations)
        out["won"] = len(d.orders)
        # Trade-in gigs of the recording: opening fee over the typical fee, minutes to the first booking.
        out["tradein"] = [(g["schedule"][0]["feeCents"] / requests[order_of[g["id"]]]["referenceFeeCents"],
                           next((e["at"] - g["postedAt"] for e in events if e["kind"] == "gig_booked" and e["gigId"] == g["id"]), None))
                          for g in gigs if sum(s["kind"] == "pickup" for s in g["stops"]) == 2 and order_of[g["id"]] in requests]
        minutes = {(r["from"], r["to"]): r["minutes"] for r in map_["roads"]}
        per_min = collections.Counter()
        for r in requests.values():
            k = "trade" if len(r["legs"]) == 2 else "one" if kind(r) == "" else None
            if k:
                per_min[k + "_c"] += r["referenceFeeCents"]
                per_min[k + "_m"] += sum(minutes[(l["pickup"]["placeId"], l["delivery"]["placeId"])] for l in r["legs"])
        out["per_min"] = per_min
    except Exception:
        out["error"] = traceback.format_exc()[-1500:]
    return out


def screening(variant: str) -> None:
    global SCREENED
    SCREENED = variant


def read(rows: list[dict]) -> None:
    errors = [r for r in rows if "error" in r]
    bad = [r for r in rows if r.get("n_violations")]
    print(f"== 1. Mechanics: {len(rows)} recorded weeks of {len({r['variant'] for r in rows})} variants: {len(errors)} with an error, "
          f"{len(bad)} with an action the world would refuse ({sum(r['n_violations'] for r in bad)} actions)")
    for r in (errors + bad)[:5]:
        print(f"   {r['variant']} {r['seed']}: {r.get('error', '').strip().splitlines()[-1:] or r['violations'][:2]}")
    ok = [r for r in rows if "error" not in r]
    # The recordings' late share by hours from the first post to the last pickup, over all weeks.
    table = collections.defaultdict(lambda: [0, 0])
    for r in ok:
        for b, is_late, _ in r["slack"]:
            table[b][0] += 1
            table[b][1] += is_late
    rate = {b: table[b][1] / table[b][0] for b in table}
    print("   late share of one-car dealer orders by hours from the first post to the last pickup, all weeks: "
          + ", ".join(f"<{BINS[b]}h {rate[b]:.1%} ({table[b][0]})" for b in sorted(table) if BINS[b] < 10**6) + f", more {rate[max(table)]:.1%}")
    per = collections.Counter()
    for r in ok:
        per.update(r["per_min"])
    ratio = (per["one_c"] / per["one_m"]) / (per["trade_c"] / per["trade_m"])
    trade = [x for r in ok for x in r["tradein"]]
    for group, sel in (("base family", [r for r in ok if r["variant"] in FAMILY]), ("all recorded weeks", ok)):
        n = len(sel)
        if not n:
            continue
        pairs = [p for r in sel for p in r["pairs"]]
        alone = [a for r in sel for a in r["alone"]]
        held = sum(r["held"] for r in sel)
        d_late = sum(rate.get(a["cf"], 0) - rate.get(a["rec"], 0) for a in alone)
        base_late = sum(rate.get(a["rec"], 0) for a in alone)
        print(f"== {group}: {n} weeks")
        print(f"   2. pairs a week {len(pairs) / n:.1f} ({2 * len(pairs) / n:.0f} orders); held {held / n:.1f}, of which alone {len(alone) / n:.1f}; "
              f"pairs back to two gigs {sum(p['split'] for p in pairs) / n:.1f} a week, by reason {dict(sum((collections.Counter(r['splits']) for r in sel), collections.Counter()))}")
        print(f"   3. held cars without a return: late {base_late / max(1, len(alone)):.2%} at the recorded post, "
              f"{(base_late + d_late) / max(1, len(alone)):.2%} when held: {100 * d_late / max(1, len(alone)):+.2f} points")
        booked = [p for p in pairs if p["booked_after"] is not None and not p["split"]]
        for fee in FEES:
            # The pair books after the slower of its two cars' recorded waits; the fee rises a tenth an hour to 1.0.
            pay = sum(min(fee + 0.1 * (p["booked_after"] // 60), 1.0) * p["typical"] for p in booked)
            saved = sum(p["alone"] for p in booked) - pay
            held_cost = LATE_EUROS * 100 * d_late
            band = [w for m, w in trade if abs(m - fee * ratio) <= 0.1]
            in1 = sum(w is not None and w <= 60 for w in band) / max(1, len(band))
            in2 = sum(w is not None and w <= 120 for w in band) / max(1, len(band))
            rets = [x for r in sel for x in r["returns"]]
            gain = 0.0
            pp = sum(y["paired"] for y in rets if y["won"]) / max(1, sum(y["won"] for y in rets))  # the share of won returns that pair
            for x in rets:
                (c_hi, p_hi), (c_lo, p_lo) = x["hi"], x["lo"]
                paired_cost = fee * (x["typical"] + x["partner_typical"]) - (x["partner_fee"] or 1.08 * x["partner_typical"])
                cost = pp * paired_cost + (1 - pp) * 1.2 * x["typical"]
                gain += c_lo * (p_lo - cost) - c_hi * (p_hi - cost)
            print(f"   pairs-{fee}: 4. trade-ins at {fee * ratio:.2f} x their typical fee ({len(band)} gigs): booked within 1 h {in1:.0%}, 2 h {in2:.0%}; "
                  f"5. fees saved {saved / 100 / n:+,.0f} a week on {len(booked) / n:.1f} booked pairs, less held cars' lateness {held_cost / 100 / n:,.0f}: {(saved - held_cost) / 100 / n:+,.0f}; "
                  f"6. -return-0.75: {len(rets) / n:.1f} return quotes a week, expected margin {gain / 100 / n:+,.0f} a week, "
                  f"orders {sum(x['lo'][0] - x['hi'][0] for x in rets) / n:+.1f}")
    print(f"   one-way typical fee over a trade-in's, a drive minute: {ratio:.2f}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--variants", help="comma-separated; all recorded variants by default")
    parser.add_argument("--limit", type=int, default=0, help="at most this many weeks of each variant")
    parser.add_argument("--others", type=int, default=0, help="at most this many weeks of each variant outside the base family")
    parser.add_argument("--out", default=str(data_dir() / "pairs-screen.jsonl"))
    parser.add_argument("--read", help="only print the screen from this file")
    parser.add_argument("--processes", type=int, default=4)
    parser.add_argument("--screened", default=SCREENED, help=f"the pair variant to run over the recorded weeks (default {SCREENED})")
    args = parser.parse_args()
    if args.read:
        return read([json.loads(line) for line in open(args.read)])
    runs = data_dir() / "runs"
    names = args.variants.split(",") if args.variants else [*FAMILY, *sorted(p.name for p in runs.iterdir() if p.name not in FAMILY)]
    paths = []
    for name in names:
        found = sorted(str(p) for p in (runs / name).glob("*-L8.json.gz"))
        paths += found[: (args.others if args.others and name not in FAMILY else args.limit) or None]
    rows = [json.loads(line) for line in open(args.out)] if Path(args.out).exists() else []  # a screen that stopped goes on
    done = {r["path"] for r in rows}
    paths = [p for p in paths if p not in done]
    with Pool(args.processes, initializer=screening, initargs=(args.screened,)) as pool, open(args.out, "a") as f:
        for i, row in enumerate(pool.imap(screen, paths, chunksize=2)):
            rows.append(row)
            f.write(json.dumps(row) + "\n")
            if i % 200 == 0:
                print(f"{i + 1} of {len(paths)}", file=sys.stderr, flush=True)
    read(rows)


if __name__ == "__main__":
    main()
