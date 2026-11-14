"""Drops: how fast a dropped gig is booked again, by the fee showing at the drop, the clock hour and the fee over the lane's usual. Arguments: data folder, lane fees JSON (feenoise.py), variants."""
import gzip, json, sys, glob
import numpy as np
lanefee = json.load(open(sys.argv[2])); out = []
for variant in sys.argv[3:]:
    for path in sorted(glob.glob(f"{sys.argv[1]}/runs/{variant}/*-L8.json.gz")):
        run = json.load(gzip.open(path)); req = {r["request"]["id"]: r["request"] for r in run["reveal"]["requests"]}; gig = {g["id"]: g for g in run["gigs"]}
        open_drop = {}; kinds = {e["kind"] for e in run["events"]}
        for e in run["events"]:
            if e["kind"] == "gig_dropped": open_drop[e["gigId"]] = dict(at=e["at"], views=0, driver=e["driverId"])
            elif e["kind"] == "gig_viewed" and e["gigId"] in open_drop: open_drop[e["gigId"]]["views"] += 1
            elif e["kind"] in ("gig_booked", "gig_expired") and e["gigId"] in open_drop:
                dr = open_drop.pop(e["gigId"]); g = gig[e["gigId"]]; q = req.get(g["stops"][0]["orderId"])
                if q is None or len(q["legs"]) != 1: continue
                leg = q["legs"][0]; lf = lanefee.get(f'{leg["pickup"]["placeId"]}|{leg["delivery"]["placeId"]}|{leg["pickup"]["privateAddress"] or leg["delivery"]["privateAddress"]}', [None, 0])
                fee_at_drop = ([s["feeCents"] for s in g["schedule"] if s["at"] <= dr["at"]] or [g["schedule"][0]["feeCents"]])[-1]
                out.append((dr["at"], e["at"] - dr["at"], e["kind"] == "gig_booked", e.get("feeCents", 0) / q["referenceFeeCents"], fee_at_drop / q["referenceFeeCents"], dr["views"], dr["at"] % 1440 / 60, e.get("driverId") == dr["driver"], g["schedule"][0]["feeCents"] / q["referenceFeeCents"], (dr["at"] - g["postedAt"]) / 60, np.log(q["referenceFeeCents"]) - lf[0] if lf[1] >= 20 else np.nan))
A = np.array(out, float); at, wait, booked, fee, feedrop, views, clock, same, open_, held, resid = A.T
print(len(A), "drops; rebooked", booked.mean().round(3), "; rebooked by the same driver", same[booked == 1].mean().round(3))
print("fee over typical showing at the drop: quantiles 10/25/50/75/90", np.round(np.quantile(feedrop, [.1, .25, .5, .75, .9]), 2), "| schedule opened at", np.round(np.quantile(open_, [.1, .5, .9]), 2), "| hours from post to drop", np.round(np.quantile(held, [.1, .5, .9]), 1))
print("minutes from drop to the next booking: quantiles 25/50/75/90", np.round(np.quantile(wait[booked == 1], [.25, .5, .75, .9])), "| within 5 min", np.mean(wait[booked == 1] <= 5).round(3), "within 60", np.mean(wait[booked == 1] <= 60).round(3), "| looks before the booking, median", np.median(views[booked == 1]))
for lo, hi in [(1.1, 1.25), (1.25, 1.5), (1.5, 1.74), (1.74, 1.9), (1.9, 9)]:
    s = (feedrop >= lo) & (feedrop < hi) & (booked == 1)
    if s.sum() > 20: print(f"  fee at the drop {lo}-{hi}: n={s.sum()} rebooked within 5 min {np.mean(wait[s] <= 5):.3f} within 60 {np.mean(wait[s] <= 60):.3f}; looks median {np.median(views[s]):.0f}")
print("by clock hour of the drop, rebooked within 60 min:", " ".join(f"{h:02d}:{np.mean(wait[(clock >= h) & (clock < h + 3) & (booked == 1)] <= 60):.2f}(n={int(((clock >= h) & (clock < h + 3)).sum())})" for h in range(0, 24, 3)))
s = (feedrop >= 1.74) & (feedrop < 1.9) & (booked == 1) & ~np.isnan(resid); q = np.quantile(resid[s], [0, .33, .67, 1])
print("at the 1.8 cap, by fee over the lane's usual: " + "  ".join(f"{1.8 * np.exp(resid[s & (resid >= a) & (resid <= b)]).mean():.2f}: within 5 min {np.mean(wait[s & (resid >= a) & (resid <= b)] <= 5):.3f}, within 60 {np.mean(wait[s & (resid >= a) & (resid <= b)] <= 60):.3f}" for a, b in zip(q[:-1], q[1:])))
