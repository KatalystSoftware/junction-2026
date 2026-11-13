import json, statistics, sys, collections
rows = [r for r in json.load(open(sys.argv[1])) if r["legs"] == 1]
print(len(rows), "single-car won orders;", sum(r["fees"] > r["price"] for r in rows), "below fees")
def q(xs, p): xs = sorted(xs); return xs[min(len(xs) - 1, int(p * len(xs)))]
def table(name, key, rows=rows):
    groups = collections.defaultdict(list)
    for r in rows: groups[key(r)].append(r)
    print(f"\n{name:22s} {'n':>5s} {'fee/ref p25':>11s} {'p50':>6s} {'p75':>6s} {'p90':>6s} {'mean':>6s} {'ref/list':>8s} {'fee/list':>8s} {'below fees':>10s} {'late':>6s}")
    for k in sorted(groups):
        g = groups[k]; ratio = [r["fees"] / r["ref"] for r in g]
        print(f"{str(k):22s} {len(g):>5d} {q(ratio, .25):>11.2f} {q(ratio, .5):>6.2f} {q(ratio, .75):>6.2f} {q(ratio, .9):>6.2f} {statistics.fmean(ratio):>6.2f} "
              f"{statistics.fmean(r['ref'] / r['list'] for r in g):>8.2f} {statistics.fmean(r['fees'] / r['list'] for r in g):>8.2f} {sum(r['fees'] > r['price'] for r in g) / len(g):>10.1%} {sum(not r['onTime'] for r in g) / len(g):>6.1%}")
def band(value, edges): return next((f"<{e}" for e in edges if value < e), f">={edges[-1]}")
table("variant", lambda r: r["variant"])
table("option", lambda r: r["option"])
table("notified at pickup", lambda r: band(r["notified"], [3, 6, 11, 21, 51, 101, 201]).rjust(6))
table("notified at delivery", lambda r: band(r["notifiedDelivery"], [3, 6, 11, 21, 51, 101, 201]).rjust(6))
table("drive minutes", lambda r: band(r["minutes"], [30, 60, 120, 180, 240, 360]).rjust(6))
table("slack hours", lambda r: band(r["slack"] / 60, [5, 8, 12, 24, 36, 48]).rjust(6))
table("week cars/driver", lambda r: band(r["weekTight"], [1.2, 1.3, 1.4, 1.5]).rjust(6))
table("day", lambda r: r["day"])
table("hour", lambda r: band(r["hour"], [10, 12, 14, 16]).rjust(6))
table("situation", lambda r: r["situation"])
table("ref/list", lambda r: band(r["ref"] / r["list"], [0.7, 0.8, 0.9, 1.0, 1.1, 1.2]).rjust(6))
table("list price eur", lambda r: band(r["list"] / 100, [40, 60, 90, 130, 200]).rjust(6))
table("premium", lambda r: r["premium"]); table("note", lambda r: r["note"])
table("seed", lambda r: r["seed"], [r for r in rows if r["variant"] == "with-same-day"])
