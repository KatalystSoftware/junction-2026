"""Two-car trade-in gigs by their opening fee over the typical fee: how fast a driver books them. usage: tradein_fee.py <data dir> <variant> [...]"""
import gzip, json, glob, sys, collections, statistics as st
from multiprocessing import Pool
data = sys.argv[1]
def week(f):
    d = json.load(gzip.open(f)); out = []
    req = {r["request"]["id"]: r["request"] for r in d["reveal"]["requests"]}
    booked = {}
    for e in d["events"]:
        if e["kind"] == "gig_booked": booked.setdefault(e["gigId"], (e["at"], e["feeCents"]))
    late = {e["line"]["orderId"] for e in d["events"] if e["kind"] == "ledger" and e["line"]["kind"] in ("late_refund", "undelivered_penalty")}
    for g in d["gigs"]:
        if len({(s["orderId"], s["leg"]) for s in g["stops"]}) != 2: continue
        r = req[g["stops"][0]["orderId"]]
        ref = r["referenceFeeCents"]; b = booked.get(g["id"])
        out.append((g["schedule"][0]["feeCents"] / ref, (b[0] - g["postedAt"]) / 60 if b else None, b[1] / ref if b else None, r["id"] in late, d["variant"]))
    return out
if __name__ == "__main__":
    files = [f for v in sys.argv[2:] for f in sorted(glob.glob(f"{data}/runs/{v}/*.json.gz"))]
    with Pool(4) as p: rows = [x for r in p.map(week, files, chunksize=2) for x in r]
    print(len(files), "weeks,", len(rows), "two-car gigs posted")
    for lo, hi in ((0, 1.05), (1.05, 1.25), (1.25, 1.45), (1.45, 1.7), (1.7, 9)):
        x = [r for r in rows if lo <= r[0] < hi]
        if not x: continue
        bk = [r for r in x if r[1] is not None]
        print(" opening %.2f-%.2f x typical: %4d gigs, booked within 1 h %3.0f%%, within 4 h %3.0f%%, ever %3.0f%%, paid %.2f, order late %.0f%%" % (
            lo, hi, len(x), 100 * sum(r[1] <= 1 for r in bk) / len(x), 100 * sum(r[1] <= 4 for r in bk) / len(x), 100 * len(bk) / len(x), st.mean(r[2] for r in bk) if bk else 0, 100 * st.mean(r[3] for r in x)))
