"""Scratch: how the snow forecast changes lateness. For each won one-car order of a variant's saved weeks, whether a
`forecast` event named its pickup or delivery place for hours that overlap the order's work (from the first minute to
collect the car to the deadline), and whether the desk knew it at the quote. Prints the late share by group against
the chance that `slow.py` gives, and fits the extra log odds of a snow term with the other weights held.

    PYTHONPATH=. uv run python scratch/snow_report.py --variant steep-notes-offers-8 --model friday
"""
from __future__ import annotations

import argparse
import math

from spreadlab import curve, slow
from spreadlab.play import load_run
from spreadlab.policy import kind
from spreadlab.server import data_dir, drivers_near, near_places, world_map

DAY = 1440


def offset_fit(rows: list[tuple[float, list[float], bool]]) -> list[float]:
    """Logistic fit of extra terms on top of a fixed log odds per row, by Newton's method."""
    n = len(rows[0][1])
    w = [0.0] * n
    for _ in range(30):
        g, h = [0.0] * n, [[1e-9 * (i == j) for j in range(n)] for i in range(n)]
        for base, x, y in rows:
            p = 1 / (1 + math.exp(-(base + sum(a * b for a, b in zip(w, x)))))
            for i in range(n):
                g[i] += (y - p) * x[i]
                for j in range(n):
                    h[i][j] += p * (1 - p) * x[i] * x[j]
        if n == 1:
            step = [g[0] / h[0][0]]
        else:
            det = h[0][0] * h[1][1] - h[0][1] * h[1][0]
            step = [(h[1][1] * g[0] - h[0][1] * g[1]) / det, (h[0][0] * g[1] - h[1][0] * g[0]) / det]
        w = [a + b for a, b in zip(w, step)]
        if max(abs(s) for s in step) < 1e-7:
            break
    return w


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", default="steep-notes-offers-8")
    parser.add_argument("--model", default="friday")
    args = parser.parse_args()
    weights = slow.MODELS[args.model]
    map_ = world_map()
    near = near_places(map_)
    minutes = {(r["from"], r["to"]): r["minutes"] for r in map_["roads"]}
    seeds = sorted(p.name[:-len("-L8.score.json")] for p in (data_dir() / "runs" / args.variant).glob("*-L8.score.json"))
    groups: dict[str, list[tuple[float, bool]]] = {}
    rows = []
    weeks = 0
    snow_late_per_week = []
    for seed in seeds:
        try:
            run = load_run(args.variant, seed)
        except Exception:
            continue
        weeks += 1
        notified = drivers_near(run["roster"], near)
        forecasts = [e for e in run["events"] if e["kind"] == "forecast"]
        requests = {e["request"]["id"]: e["request"] for e in run["events"] if e["kind"] == "price_request"}
        won = {e["order"]["id"]: e["order"] for e in run["events"] if e["kind"] == "order_won"}
        lates = {e["line"]["orderId"] for e in run["events"] if e["kind"] == "ledger" and e["line"]["kind"] in ("late_refund", "undelivered_penalty")}
        week_snow_late = 0
        for id_, order in won.items():
            q = requests.get(id_)
            if q is None or kind(q):
                continue
            leg = q["legs"][0]
            a, b = leg["pickup"]["placeId"], leg["delivery"]["placeId"]
            drive = minutes[(a, b)]
            ready = max(q["respondBy"], leg["pickup"]["window"]["from"])
            options = [o for o in q["options"] if o["deadline"] - drive - ready >= 300]
            if not options:
                continue
            fastest = curve.fastest(options)
            x = slow.known(q, fastest, notified[a], drive, len(run["roster"]))
            base = sum(w * v for w, v in zip(weights, x))
            p = 1 / (1 + math.exp(-base))
            end = order["deadline"]

            def hits(f, places) -> bool:
                return bool(places & set(f["placeIds"])) and ready < f["to"] and end > f["from"]
            ends = {a, b}
            around = set(near[a]) | set(near[b])
            truth = any(hits(f, ends) for f in forecasts)
            known = any(hits(f, ends) and f["at"] <= q["arrivedAt"] for f in forecasts)
            near_known = not known and any(hits(f, around) and f["at"] <= q["arrivedAt"] for f in forecasts)
            later = truth and not known
            late = id_ in lates
            group = "known at quote" if known else "forecast after quote" if later else "near, known" if near_known else "no snow"
            groups.setdefault(group, []).append((p, late))
            if known:
                last = fastest["deadline"] - drive
                kf = [f for f in forecasts if hits(f, ends) and f["at"] <= q["arrivedAt"]]
                at_pickup = any(a in f["placeIds"] for f in kf)
                # Snow over the pickup's possible minutes (ready to the last pickup on time with the fastest option), or only later.
                over_pickup = any(ready < f["to"] and last > f["from"] for f in kf)
                starts_before = any(f["from"] <= ready for f in kf)
                lead = min(f["from"] - q["arrivedAt"] for f in kf) / 60
                for sub in (f"known: {'pickup place' if at_pickup else 'delivery place only'}",
                            f"known: {'snow before last pickup' if over_pickup else 'snow only after last pickup'}",
                            f"known: {'snowing at ready' if starts_before else 'snow starts after ready'}",
                            f"known: snow starts {'<12h' if lead < 12 else '12-24h' if lead < 24 else '>=24h'} after the request"):
                    groups.setdefault(sub, []).append((p, late))
            rows.append((base, [float(known), float(near_known)], late))
            week_snow_late += late and truth
        snow_late_per_week.append(week_snow_late)
    print(f"{args.variant}: {weeks} weeks, {len(rows)} one-car orders, late chance from slow.MODELS[{args.model!r}]")
    for group, items in sorted(groups.items()):
        n = len(items)
        print(f"  {group:22s} {n / weeks:6.1f} a week  predicted {100 * sum(p for p, _ in items) / n:5.1f}%  late {100 * sum(y for _, y in items) / n:5.1f}%"
              f"  extra late a week {(sum(y for _, y in items) - sum(p for p, _ in items)) / weeks:+.2f}")
    w = offset_fit(rows)
    print(f"extra log odds: snow known at quote {w[0]:+.3f} (odds x{math.exp(w[0]):.2f}), near a known snow place {w[1]:+.3f}")
    # Bands of the predicted chance, snow known against none.
    for group in ("known at quote", "no snow"):
        items = groups.get(group, [])
        out = []
        for low, high in ((0, 0.03), (0.03, 0.06), (0.06, 0.12), (0.12, 1)):
            band = [(p, y) for p, y in items if low <= p < high]
            if band:
                out.append(f"{100 * low:.0f}-{100 * high:.0f}%: n {len(band)} pred {100 * sum(p for p, _ in band) / len(band):.1f} late {100 * sum(y for _, y in band) / len(band):.1f}")
        print(f"  {group}: " + "; ".join(out))


main()
