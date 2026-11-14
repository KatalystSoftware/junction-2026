"""An offline stand-in for a played week, for the optimisation formulation: it prices the saved reference weeks again
under another rule for an order's cost, with the feedback that the quotes have on the backlog, the day's live shift,
each dealer's trust and the desk's projected on-time share. It reads saved weeks only and plays nothing.

It follows scratch/gap/replay.py and needs that folder's caches (funnel.py, price.py, backlog.py for the variant).
What differs:
- a new order ends late by a fitted chance (late model below) with an intercept for its week, so a hard week stays hard;
  the gap replay drew a saved order's fate from all weeks alike;
- the cost rule is the per-decision optimiser's: fees, a waiting-car surcharge, the late chance times the cost of a late
  order, and the price of the 90% rule while the desk is behind;
- every random draw is fixed for a request and a draw number, so two rules are compared on the same luck.

What it cannot show: anything on the driver side (opening fee, rises, offers), drivers getting scarcer beyond the late
model's waiting-car terms, and the competitor's answer to what the desk wins.
"""
from __future__ import annotations

import collections
import json
import math
import pickle
import sys
import zlib
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "gap"))
import lib  # noqa: E402

from spreadlab import curve  # noqa: E402
from spreadlab.server import drivers_near, near_places  # noqa: E402

DAY = 1440
M = curve.MODELS["day"]
B, TW = M["slope"], M["trust"]
MULT = np.array([curve.LOW + curve.STEP * k for k in range(int(round((curve.HIGH - curve.LOW) / curve.STEP)) + 1)])
LOGM = np.log(MULT)
LATE_HELD, LATE_WAITING, LATE_WAITING_LONG, LONG_WAIT = 0.03, 0.15, 0.40, 120  # policy.py's projection
FEATURES = ["under 6 h", "6 to 8 h", "8 to 12 h", "12 to 24 h", "36 h or more", "ln(1 + drivers notified)", "drive over 400 min", "drive 180 to 400 min",
            "Friday", "note", "premium", "100 drivers under 800", "waiting, due within 8 h", "waiting, due in 8 to 24 h", "waiting, due later"]
sig = lambda z: 1 / (1 + math.exp(-z))


def best(a: float, shift: float, list_c: float, cost_c: float) -> float:
    return float(MULT[np.argmax((MULT * list_c - cost_c) / (1 + np.exp(-(a - B * (LOGM - shift)))))])


def live_shift(zs: list, wons: list, sd: float) -> float:
    if not zs:
        return 0.0
    z, w, d = np.array(zs), np.array(wons, float), 0.0
    for _ in range(8):
        c = 1 / (1 + np.exp(-(z + B * d)))
        d += max(-0.3, min(0.3, (B * (w - c).sum() - d / sd ** 2) / (B * B * (c * (1 - c)).sum() + 1 / sd ** 2)))
    return d


def band(h: float) -> str:
    return "<6" if h < 6 else "6-8" if h < 8 else "8-12" if h < 12 else "12-30" if h < 30 else "30+"


def features(row: dict, parts) -> list[float]:
    h = row["h"]
    return [h < 6, 6 <= h < 8, 8 <= h < 12, 12 <= h < 24, h >= 36, math.log(1 + row["notified"]), row["drive"] > 400, 180 < row["drive"] <= 400,
            row["day"] == 4, row["note"], row["premium"], (800 - row["drivers"]) / 100, parts[0], parts[1], parts[2]]


class Weeks:
    """The saved weeks of a variant as plain rows, and the late model fitted on the weeks in `fit_on`."""

    def __init__(self, data: str, cache: str, variant: str = "steep-notes-offers-8"):
        map_ = json.load(open(f"{data}/map.json"))
        minutes, near = lib.minutes_of(map_), near_places(map_)
        weeks = lib.cached(data, variant, minutes, cache)
        quotes = {(r["w"], r["rid"]): r for r in pickle.load(open(f"{cache}/quotes-{variant}.pkl", "rb"))}
        state = {(s["w"], s["rid"]): s for s in pickle.load(open(f"{cache}/state-{variant}.pkl", "rb"))}
        level = {tuple(int(x) for x in k.split("|")): v for k, v in json.load(open(f"{cache}/levels-{variant}.json"))["level"].items()}
        self.seeds, self.drivers, self.played, self.W = [], [], [], []
        self.pool, self.took = collections.defaultdict(list), collections.defaultdict(collections.Counter)

        def slack(q, o):
            leg = q["legs"][0]
            return o["deadline"] - minutes[(leg["pickup"]["placeId"], leg["delivery"]["placeId"])] - max(q["respondBy"], leg["pickup"]["window"]["from"])

        for wi, w in enumerate(weeks):
            notified = drivers_near(w["roster"], near)
            self.seeds.append(w["seed"]); self.drivers.append(len(w["roster"])); self.played.append(w["score"])
            unbooked = {}
            for o in w["orders"].values():  # the minutes, from the win, in which no driver held the order's car
                ev = sorted([(b[0], 1) for b in o["bookings"]] + [(d[0], 0) for d in o["drops"]])
                open_from, iv = o["wonAt"], []
                for at, kind in ev:
                    if kind == 1 and open_from is not None:
                        iv.append((open_from - o["wonAt"], at - o["wonAt"])); open_from = None
                    elif kind == 0 and open_from is None:
                        open_from = at
                if open_from is not None:
                    iv.append((open_from - o["wonAt"], (o["pickedUp"] or o["lastPickupAt"] + 600) - o["wonAt"]))
                unbooked[o["id"]] = iv
            reqs = []
            for rid, r in sorted(w["reqs"].items(), key=lambda kv: (kv[1]["request"]["arrivedAt"], kv[0])):
                q, dec = r["request"], w["decisions"][rid]
                if lib.req_kind(q) != "dealer" or dec["declined"] == "slack":
                    continue
                opts = [o for o in q["options"] if slack(q, o) >= 300]
                if dec["declined"] is None:
                    opts = [o for o in q["options"] if o["kind"] in dec["prices"]]
                day = q["arrivedAt"] // DAY
                if not opts or (wi, day) not in level:
                    continue
                first, leg = curve.fastest(opts), q["legs"][0]
                drive = minutes[(leg["pickup"]["placeId"], leg["delivery"]["placeId"])]
                row = {"w": wi, "rid": rid, "at": q["arrivedAt"], "by": q["respondBy"], "dealer": q["dealerId"], "day": day, "a0": curve.at_list(q, opts, 0, M),
                       "list": first["listPriceCents"], "lists": {o["kind"]: o["listPriceCents"] for o in opts}, "fee": q["referenceFeeCents"], "s": level[(wi, day)],
                       "kinds": "+".join(sorted(o["kind"] for o in opts)), "ready": leg["pickup"]["window"]["from"], "played": None, "life": None,
                       "premium": leg["car"]["premium"], "note": q["note"] is not None, "drive": drive, "notified": notified[leg["pickup"]["placeId"]],
                       "drivers": len(w["roster"]), "h": (first["deadline"] - drive - q["respondBy"]) / 60, "u": {}}
                pq = quotes.get((wi, rid))
                if pq is not None:
                    row["played"] = (sig(pq["a"] - B * (math.log(pq["m"]) - pq["s"])), pq["won"])
                o = w["orders"].get(rid)
                if o is not None and not o["cancelled"]:
                    st = state[(wi, rid)]
                    row["life"] = {"iv": unbooked[rid], "lag": None if o["delivered"] is None else o["delivered"] - max(row["ready"], o["wonAt"]), "late": o["late"],
                                   "last": o["lastPickupAt"] - o["wonAt"], "fee": o["fees"] / q["referenceFeeCents"], "refund": o["refund"] / max(o["price"], 1),
                                   "other": o["other"], "option": o["option"], "u": (st["u8"], st["u24"], st["ulater"])}
                    self.pool[(wi, band(row["h"]))].append(row["life"]); self.pool[(band(row["h"]),)].append(row["life"])
                    self.took[row["kinds"]][o["option"]] += 1
                reqs.append(row)
            self.W.append(reqs)
        self.refund_late = lib.mean(l["refund"] for k, v in self.pool.items() if len(k) == 1 for l in v if l["late"])
        self.beta, self.week = None, [0.0] * len(self.W)

    def fit(self, fit_on: list[int]) -> None:
        """The late model on the won orders of the weeks `fit_on`, then each week's own intercept (prior sd 0.5)."""
        rows = [r for wi in fit_on for r in self.W[wi] if r["life"]]
        X = np.array([[1.0] + [float(v) for v in features(r, r["life"]["u"])] for r in rows]); y = np.array([float(r["life"]["late"]) for r in rows])
        beta = np.zeros(X.shape[1]); beta[0] = math.log(y.mean() / (1 - y.mean()))
        for _ in range(30):
            p = 1 / (1 + np.exp(-X @ beta))
            beta += np.linalg.solve(X.T @ (X * (p * (1 - p))[:, None]) + 1e-3 * np.eye(len(beta)), X.T @ (y - p) - 1e-3 * beta)
        self.beta = beta
        for wi, reqs in enumerate(self.W):
            own = [r for r in reqs if r["life"]]
            z = np.array([self.logit(r, r["life"]["u"]) for r in own]); late = np.array([float(r["life"]["late"]) for r in own]); d = 0.0
            for _ in range(20):
                p = 1 / (1 + np.exp(-(z + d)))
                d += ((late - p).sum() - d / 0.25) / ((p * (1 - p)).sum() + 1 / 0.25)
            self.week[wi] = d

    def logit(self, row: dict, parts) -> float:
        return float(self.beta[0] + sum(b * float(v) for b, v in zip(self.beta[1:], features(row, parts))))

    def late(self, row: dict, parts) -> float:
        """The chance that the order ends late, as the desk can know it at the quote: without the week's intercept."""
        return sig(self.logit(row, parts))


def draws(row: dict, draw: int) -> np.ndarray:
    """Four numbers from 0 to 1 that are fixed for a request and a draw number: the dealer's answer, the option, the saved order whose course a new order takes, and lateness."""
    if draw not in row["u"]:
        row["u"][draw] = np.random.default_rng(zlib.crc32(f"{row['w']}|{row['rid']}|{draw}".encode())).random(4)
    return row["u"][draw]


def simulate(weeks: Weeks, rule, on: list[int], draw: int = 0, learn: float = 0.16, react: float = 0.0, halve: bool = True) -> list[dict]:
    """Plays the weeks `on` again. `rule(row, parts, trust, desk)` returns (the order's cost in cents, or None to decline). `parts` are the won cars without a driver that are due within
    8 hours, in 8 to 24 hours, and later; `desk` has the won orders so far and the projected on-time share. Returns one dict a week.

    `react` is the competitor's answer, which the handbook describes and no reveal shows: each morning a dealer accepts prices lower by `react` x (the share of its requests of the day
    before that the desk won here - the share it won in the saved week), in log price and at most 0.15 either way. With `halve` off a late order does not halve its dealer's count: the
    difference to a normal run is what lateness costs in trust."""
    out = []
    for wi in on:
        trust, orders, pending, deliveries, today = collections.Counter(), [], [], [], (-1, [], [])
        wk = collections.Counter()
        asked, here, saved, moved, day_now = collections.Counter(), collections.Counter(), collections.Counter(), {}, -1

        resolved = [0, 0.0]  # the orders that have arrived or are overdue, and how many of them late

        def settle(now):
            for o in [o for o in orders if o["done"] <= now]:
                resolved[0] += 1; resolved[1] += o["late"]
                orders.remove(o)

        def parts_at(now):
            parts = [0, 0, 0]
            for o in orders:
                if any(a <= now - o["won"] < b for a, b in o["iv"]):
                    left = o["won"] + o["last"] - now
                    parts[0 if left <= 480 else 1 if left <= 1440 else 2] += 1
            return parts

        def projected(now):
            late = resolved[1]
            for o in orders:
                if any(a <= now - o["won"] < b for a, b in o["iv"]):
                    late += LATE_WAITING_LONG if now - o["won"] >= LONG_WAIT else LATE_WAITING
                else:
                    late += LATE_HELD
            return 1 - late / (resolved[0] + len(orders)) if resolved[0] + len(orders) else 1.0

        def answer(by, r, won, z, mult):
            nonlocal today
            if today[0] != r["day"]:
                today = (r["day"], [], [])
            today[1].append(z); today[2].append(won)
            here[(r["dealer"], r["day"])] += won
            if not won:
                return
            u, parts, life = draws(r, draw), parts_at(by), r["life"]
            if life is None:
                kinds = weeks.took[r["kinds"]]
                names, total, acc, option = sorted(kinds), sum(kinds.values()), 0.0, next(iter(r["lists"]))
                for name in names:  # the option the dealer takes, by how often it took each from this menu
                    acc += kinds[name] / total
                    if u[1] < acc:
                        option = name if name in r["lists"] else option
                        break
                pool = weeks.pool.get((wi, band(r["h"]))) or weeks.pool[(band(r["h"]),)]
                life = pool[int(u[2] * len(pool))]
                late = u[3] < sig(weeks.logit(r, parts) + weeks.week[wi])
            else:  # its own course; its lateness moves with the backlog at the win, against the backlog it was saved under
                option, late = life["option"], life["late"]
                p0, p1 = sig(weeks.logit(r, life["u"]) + weeks.week[wi]), sig(weeks.logit(r, parts) + weeks.week[wi])
                if not late and p1 > p0 and u[3] < (p1 - p0) / (1 - p0):
                    late = True
                elif late and p1 < p0 and u[3] < (p0 - p1) / p0:
                    late = False
            price = mult * r["lists"].get(option, r["list"])
            refund = (life["refund"] if life["late"] else weeks.refund_late) * price if late else 0
            done = max(r["ready"], by) + (life["lag"] if life["lag"] is not None else 3 * DAY)
            orders.append({"won": by, "iv": life["iv"], "last": life["last"], "done": done, "late": late})
            deliveries.append((done, r["dealer"], not late))
            wk["orders"] += 1; wk["late"] += late; wk["revenue"] += price; wk["fees"] += life["fee"] * r["fee"]; wk["refund"] += refund; wk["other"] += life["other"]; wk["typ"] += r["fee"]

        for row in weeks.W[wi]:
            now = row["at"]
            pending.sort(key=lambda p: p[0])
            while pending and pending[0][0] <= now:
                answer(*pending.pop(0))
            deliveries.sort()
            while deliveries and deliveries[0][0] <= now:
                _, dealer, ok = deliveries.pop(0)
                trust[dealer] = min(25, trust[dealer] + 1) if ok or not halve else trust[dealer] // 2
            if react and row["day"] != day_now:  # the morning: the competitor looks at each dealer's requests of the day before
                day_now = row["day"]
                moved = {d: max(-0.15, min(0.15, -react * (here[(d, day)] - saved[(d, day)]) / n)) for (d, day), n in asked.items() if day == day_now - 1 and n >= 5}
            asked[(row["dealer"], row["day"])] += 1
            saved[(row["dealer"], row["day"])] += bool(row["played"] and row["played"][1])
            settle(now)
            parts, t = parts_at(now), trust[row["dealer"]]
            cost = rule(row, parts, t, {"orders": resolved[0] + len(orders), "on_time": projected(now), "now": now})
            if cost is None:
                wk["declined"] += 1
                continue
            a = row["a0"] + TW * math.log(1 + 0.01 * t)
            shift = live_shift(today[1], today[2], learn) if today[0] == row["day"] else 0.0
            m = best(a, shift, row["list"], cost)
            p, u = sig(a - B * (math.log(m) - row["s"] - moved.get(row["dealer"], 0.0))), draws(row, draw)[0]
            if row["played"] is not None:  # a hidden draw that agrees with the saved answer at the saved price
                p0, won0 = row["played"]
                u = u * p0 if won0 else p0 + u * (1 - p0)
            wk["quotes"] += 1
            pending.append((row["by"], row, u < p, a - B * math.log(m), m))
        for p in sorted(pending, key=lambda p: p[0]):
            answer(*p)
        wk["margin"] = (wk["revenue"] - wk["fees"] - wk["refund"] - wk["other"]) / 100
        wk["on_time"] = 1 - wk["late"] / max(1, wk["orders"])
        out.append(dict(wk, w=wi))
    return out


def reference_rule(row, parts, trust, desk):
    """`steep-notes-offers-8`: cost 1.3 and 0.04 for each won car without a driver; no quote while 15 wait."""
    return None if sum(parts) >= 15 else row["fee"] * (1.3 + 0.04 * sum(parts))


def shadow_rule(weeks: Weeks, cost=1.3, late_cost=0.0, step=0.04, step_hours=0, gate=15, min_on_time=0.0, rule_cost=0.0, behind_gate=15, behind_from=40, hours=None, floor=1.0):
    """The per-decision optimiser's cost of an order, in cents:
    fee x (cost + step x waiting cars) + 100 x [late_cost x p + rule_cost x (p - 0.10)], never under `floor` x fee.
    `rule_cost` and `behind_gate` apply while the projected on-time share is under `min_on_time` and `behind_from` orders are won. `hours` replaces `cost` by the hours to find a driver:
    [[hours, cost], ...]."""
    def rule(row, parts, trust, desk):
        behind = bool(min_on_time) and desk["orders"] >= behind_from and desk["on_time"] < min_on_time
        if sum(parts) >= (behind_gate if behind else gate):
            return None
        counted = sum(parts) if behind or not step_hours else parts[0] + (parts[1] if step_hours >= 24 else 0)
        base = next((c for under, c in hours or [] if row["h"] < under), cost)
        p = weeks.late(row, parts) if late_cost or (behind and rule_cost) else 0.0
        euros = late_cost * p + (rule_cost * (p - 0.10) if behind else 0.0)
        return max(floor * row["fee"], row["fee"] * (base + (max(step, 0.04) if behind else step) * counted) + 100 * euros)
    return rule


def loss(rows: list[dict], ref: list[dict], load: float = 0.026) -> dict:
    """The search's objective on paired weeks, and what it is made of. A week under 91% on time counts as no margin, and each
    point under 93% costs 300. Driver fees are taken to rise `load` x the typical fee for each 100 orders more than the reference."""
    n, j, margin = len(rows), 0.0, 0.0
    for a, b in zip(rows, ref):
        m = a["margin"] - load * max(0.0, a["orders"] - b["orders"]) / 100 * a["typ"] / 100
        margin += m - b["margin"]
        j += (m if a["on_time"] >= 0.91 else 0.0) - b["margin"] - 300 * max(0.0, 93 - 100 * a["on_time"])
    return {"J": j / n, "margin": margin / n, "orders": sum(a["orders"] for a in rows) / n, "late": sum(a["late"] for a in rows) / n,
            "lowest": min(a["on_time"] for a in rows), "under90": sum(a["on_time"] < 0.90 for a in rows), "under91": sum(a["on_time"] < 0.91 for a in rows),
            "under92": sum(a["on_time"] < 0.92 for a in rows)}
