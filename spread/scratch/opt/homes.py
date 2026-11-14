"""Does a driver's home say what a gig costs them? Each look at a one-car gig of the reference, by where the driver lives
against the gig's pickup and delivery places, with the share of looks that end in a booking by that driver and the fee paid.
PYTHONPATH=. uv run --with numpy python scratch/opt/homes.py <data> <cache>"""
import sys, json, pickle, collections
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "gap"))
import lib
from spreadlab.server import near_places
data, cache = sys.argv[1:3]
map_ = json.load(open(f"{data}/map.json")); near = near_places(map_); minutes = lib.minutes_of(map_)
weeks = lib.cached(data, "steep-notes-offers-8", minutes, cache)
g = collections.defaultdict(lambda: [0, 0, 0.0, 0])  # looks, bookings, fee over typical of the bookings, first looks
first = collections.defaultdict(lambda: [0, 0])
for w in weeks:
    home = {d["id"]: d["homePlaceId"] for d in w["roster"]}
    gig = {x["id"]: x for x in w["gigs"]}
    booked = collections.defaultdict(list)
    for e in w["ev"]["gig_booked"]:
        booked[(e["gigId"], e["driverId"])].append((e["at"], e["feeCents"]))
    seen = set()
    for v in w["views"]:
        x = gig.get(v["gigId"])
        if x is None or len({s["orderId"] for s in x["stops"]}) != 1 or len(x["stops"]) != 2:
            continue
        o = w["orders"].get(x["stops"][0]["orderId"])
        if o is None or len(o["request"]["legs"]) != 1:
            continue
        leg, h = o["request"]["legs"][0], home[v["driverId"]]
        a, b = leg["pickup"]["placeId"], leg["delivery"]["placeId"]
        where = ("pickup town" if h == a else "within 30 km of the pickup" if h in near[a] else "delivery town" if h == b else "within 30 km of the delivery" if h in near[b]
                 else "under 2 h from the pickup" if minutes[(h, a)] <= 120 else "further")
        ratio = v["feeCents"] / o["request"]["referenceFeeCents"]
        fee = "under 1.05" if ratio < 1.05 else "1.05 to 1.25" if ratio < 1.25 else "over 1.25"
        took = [f for at, f in booked.get((v["gigId"], v["driverId"]), []) if 0 <= at - v["at"] <= 30]
        for key in ((where, "all fees"), (where, fee)):
            row = g[key]; row[0] += 1; row[1] += bool(took); row[2] += took[0] / o["request"]["referenceFeeCents"] if took else 0
        if (v["gigId"], v["driverId"]) not in seen:
            seen.add((v["gigId"], v["driverId"])); first[where][0] += 1; first[where][1] += bool(took)
n = len(weeks)
print(f"{n} weeks. where the driver lives | fee seen over typical | looks a week | booked within 30 minutes of the look | fee paid over typical | first looks booked")
for where in ("pickup town", "within 30 km of the pickup", "delivery town", "within 30 km of the delivery", "under 2 h from the pickup", "further"):
    for fee in ("all fees", "under 1.05", "1.05 to 1.25", "over 1.25"):
        looks, books, paid, _ = g[(where, fee)]
        if looks:
            print(f"{where:30} {fee:13} {looks / n:8.1f} {100 * books / looks:6.1f}%  {paid / books if books else 0:5.2f}" + (f"  {100 * first[where][1] / first[where][0]:5.1f}%" if fee == "all fees" else ""))
