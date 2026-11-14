"""Scratch: one row per serious quote of a variant's played weeks, for the per-dealer filter (scratch/dealer_filter.py).

    PYTHONPATH=. uv run python scratch/dealer_rows.py steep-notes-offers-8 [seed-prefix ...]

Each row has what the desk knew at the quote: the curve's log odds at the list price (curve-day.json) with the dealer's
count of orders on time at that minute, rebuilt from the events as the policy counts it; the log of the quoted multiple
of the fastest option; the minute the answer came; and whether the dealer bought. Only one-car requests between two
dealer sites. Writes dealer_rows-<variant>.json to the data folder.
"""
import glob, json, math, os, sys
from multiprocessing import Pool

from spreadlab import curve
from spreadlab.play import load_run
from spreadlab.server import data_dir

SPEED = curve.SPEED
MODEL = curve.MODELS["day"]


def week(args):
    variant, seed = args
    run = load_run(variant, seed)
    requests = {r["request"]["id"]: r["request"] for r in run["reveal"]["requests"]}
    trust, orders, rows, asked = {}, {}, [], {}
    for e in run["events"]:
        k = e["kind"]
        if k == "price_request":
            q = requests.get(e["request"]["id"], e["request"])
            d = run["decisions"].get(q["id"])
            if not d or d["declined"] or d.get("explored") or len(q["legs"]) > 1:
                continue
            leg = q["legs"][0]
            if leg["pickup"]["privateAddress"] or leg["delivery"]["privateAddress"]:
                continue
            options = [o for o in q["options"] if o["kind"] in d["prices"]]
            first = curve.fastest(options)
            z = curve.at_list(q, options, trust.get(q["dealerId"], 0), MODEL)
            asked[q["id"]] = dict(seed=seed, dealer=q["dealerId"], at=q["arrivedAt"], day=q["arrivedAt"] // 1440, z=z,
                                  x=math.log(d["prices"][first["kind"]] / first["listPriceCents"]), trust=trust.get(q["dealerId"], 0),
                                  fee=q["referenceFeeCents"], list=first["listPriceCents"])
        elif k in ("order_won", "order_lost"):
            rid = e["order"]["id"] if k == "order_won" else e["requestId"]
            if k == "order_won":  # the saved event holds the order as the desk later changed it, so its deliveries start again here
                orders[rid] = {**e["order"], "deliveredAt": [None] * len(e["order"]["legs"])}
            if rid in asked:
                row = asked.pop(rid)
                row.update(answered=e["at"], won=k == "order_won")
                rows.append(row)
        elif k == "order_changed" and e["order"]["id"] in orders:
            orders[e["order"]["id"]] = {**e["order"], "deliveredAt": orders[e["order"]["id"]]["deliveredAt"]}
        elif k == "delivered":
            o = orders.get(e["orderId"])
            if o is None:
                continue
            o["deliveredAt"][e["leg"]] = e["at"]
            if all(at is not None for at in o["deliveredAt"]):
                dealer, count = o["dealerId"], trust.get(o["dealerId"], 0)
                trust[dealer] = min(25, count + 1) if all(at <= o["deadline"] for at in o["deliveredAt"]) else count // 2
    return rows


if __name__ == "__main__":
    variant, prefixes = sys.argv[1], sys.argv[2:] or [""]
    seeds = sorted({os.path.basename(p)[:-len("-L8.json.gz")] for p in glob.glob(str(data_dir() / "runs" / variant / "*-L8.json.gz"))})
    seeds = [s for s in seeds if any(s.startswith(p) for p in prefixes)]
    with Pool(os.cpu_count()) as pool:
        out = [r for rows in pool.map(week, [(variant, s) for s in seeds]) for r in rows]
    json.dump(out, open(data_dir() / f"dealer_rows-{variant}.json", "w"))
    print(len(seeds), "weeks", len(out), "rows")
