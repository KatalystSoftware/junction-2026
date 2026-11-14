"""Driver capacity: who uses the app on a day, who drives, and who is idle while the desk prices up or declines.
PYTHONPATH=. uv run --with numpy python scratch/gap/capacity.py <data> <cache> <variant>"""
import sys, json, collections
import lib
data, cache, variant = sys.argv[1:4]
minutes = lib.minutes_of(json.load(open(f"{data}/map.json")))
weeks = lib.cached(data, variant, minutes, cache)
n = len(weeks); DAY = 1440
tot = collections.Counter(); perday = collections.defaultdict(lambda: collections.Counter())
gigs_per_driver_day = collections.Counter()
rows = []
for wi, w in enumerate(weeks):
    roster = {d["id"] for d in w["roster"]}
    viewers = collections.defaultdict(set); bookers = collections.defaultdict(set); drove = collections.defaultdict(lambda: collections.Counter())
    for e in w["ev"]["gig_viewed"]: viewers[e["at"] // DAY].add(e["driverId"])
    for e in w["ev"]["gig_booked"]: bookers[e["at"] // DAY].add(e["driverId"])
    for e in w["ev"]["gig_started"]: drove[e["at"] // DAY][e["driverId"]] += 1
    seen = set().union(*viewers.values()) if viewers else set()
    booked = set().union(*bookers.values()) if bookers else set()
    drivers = set().union(*[set(c) for c in drove.values()]) if drove else set()
    tot["roster"] += len(roster); tot["ever viewed"] += len(seen); tot["ever booked"] += len(booked); tot["ever drove"] += len(drivers)
    tot["views"] += len(w["ev"]["gig_viewed"]); tot["bookings"] += len(w["ev"]["gig_booked"])
    for d in range(5):
        v = viewers[d]; dr = set(drove[d])
        perday[d]["viewers"] += len(v); perday[d]["drove"] += len(dr); perday[d]["gigs started"] += sum(drove[d].values())
        perday[d]["viewers who drove nothing that day"] += len(v - dr)
        perday[d]["viewers who booked nothing that day"] += len(v - bookers[d])
        for c in drove[d].values(): gigs_per_driver_day[min(c, 4)] += 1
    rows.append((len(roster), len(seen), len(drivers), w["score"]["wonOrders"], w["score"]["onTimeShare"], w["score"]["marginCents"] / 100))
print(variant, n, "weeks. Per week:", {k: round(v / n, 1) for k, v in tot.items()})
print("per weekday (mean per week):")
for d in range(5): print("  day", d, {k: round(v / n, 1) for k, v in perday[d].items()})
print("gigs started per driver and day:", {k: round(v / sum(gigs_per_driver_day.values()), 3) for k, v in sorted(gigs_per_driver_day.items())})
# by roster size
rows.sort()
print("\nroster | ever viewed | ever drove | orders | on time | margin   (thirds of the weeks by roster)")
for i in range(3):
    part = rows[i * n // 3:(i + 1) * n // 3]
    print("  %4.0f  %4.0f  %4.0f  %4.0f  %.3f  %6.0f  lowest on time %.3f" % (*[lib.mean(r[j] for r in part) for j in range(6)], min(r[4] for r in part)))
