"""Compact pickles of played weeks: cache.py <data dir> <out dir> <variant> [...]. One pickle per week."""
import gzip, json, glob, sys, pickle, os
from multiprocessing import Pool
KEEP = {"gig_booked", "gig_started", "picked_up", "delivered", "order_won", "ledger", "offer_answered", "gig_dropped", "order_lost", "deadline_close", "gig_expired", "visit_failed", "no_show", "order_changed", "order_cancelled"}
def one(args):
    f, out = args
    if os.path.exists(out):
        return
    d = json.load(gzip.open(f))
    week = {k: d.get(k) for k in ("variant", "seed", "params", "score", "gigs", "roster", "decisions")}
    week["requests"] = d["reveal"]["requests"]
    week["orders"] = d["reveal"]["orders"]
    week["views"] = d["reveal"]["views"]
    week["events"] = [e for e in d["events"] if e["kind"] in KEEP]
    pickle.dump(week, open(out, "wb"))
if __name__ == "__main__":
    data, out = sys.argv[1], sys.argv[2]
    jobs = []
    for v in sys.argv[3:]:
        os.makedirs(f"{out}/{v}", exist_ok=True)
        for f in sorted(glob.glob(f"{data}/runs/{v}/*.json.gz")):
            if f.endswith(".score.json"): continue
            jobs.append((f, f"{out}/{v}/{os.path.basename(f)[:-8]}.pkl"))
    with Pool(4) as p:
        p.map(one, jobs, chunksize=4)
    print(len(jobs), "weeks")
