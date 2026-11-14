"""Dealer trust through the week: when it arrives, what halves it, and what a quote earns at each level.
PYTHONPATH=. uv run --with numpy python scratch/gap/trust.py <data> <cache> <variant>"""
import sys, json, collections, pickle
import lib
data, cache, variant = sys.argv[1:4]
minutes = lib.minutes_of(json.load(open(f"{data}/map.json")))
weeks = lib.cached(data, variant, minutes, cache)
quotes = pickle.load(open(f"{cache}/quotes-{variant}.pkl", "rb"))
n = len(weeks); DAY = 1440
# rank dealers of each week by their requests
rank = {}
for wi, w in enumerate(weeks):
    c = collections.Counter(r["request"]["dealerId"] for r in w["reqs"].values())
    for i, (d, k) in enumerate(c.most_common()): rank[(wi, d)] = (i, k)
grp = lambda i: "largest" if i == 0 else "2nd" if i == 1 else "3rd" if i == 2 else "4th-10th" if i < 10 else "rest"
G = ["largest", "2nd", "3rd", "4th-10th", "rest"]
print("requests a week by dealer rank:", {g: round(sum(k for (wi, d), (i, k) in rank.items() if grp(i) == g) / n, 1) for g in G}, "dealers a week:", round(len(rank) / n, 1))
print("\nmean trust at the quote, by day (and share of quotes at 25) | quotes/wk | won/wk | win% | margin a quote at 1.08 x fee")
for g in G:
    rows = [q for q in quotes if grp(rank[(q["w"], q["dealer"])][0]) == g]
    line = f"{g:9}"
    for d in range(5):
        v = [q for q in rows if q["day"] == d]
        line += f"  {lib.mean(q['trust'] for q in v):5.1f} ({100 * lib.mean(q['trust'] == 25 for q in v):3.0f}%)"
    print(line, f"| {len(rows) / n:6.1f} | {sum(q['won'] for q in rows) / n:6.1f} | {100 * lib.mean(q['won'] for q in rows):4.1f} | {lib.mean(q['won'] * (q['m'] * q['list'] - 1.08 * q['fee']) for q in rows) / 100:5.2f}")
# halvings
halv = collections.Counter(); lost = collections.Counter(); first25 = collections.defaultdict(list); lag = collections.defaultdict(list)
late_by = collections.Counter(); orders_by = collections.Counter()
for wi, w in enumerate(weeks):
    ch = collections.defaultdict(list)
    for o in w["orders"].values():
        if o["cancelled"]: continue
        g = grp(rank[(wi, o["dealer"])][0]); orders_by[g] += 1; late_by[g] += o["late"]
        if o["delivered"] is not None:
            ch[o["dealer"]].append((o["delivered"], not o["late"]))
            leg = o["request"]["legs"][0]
            ready = max(leg["pickup"]["window"]["from"], o["wonAt"])
            lag[o["option"]].append((o["delivered"] - ready, o["delivered"] // DAY - ready // DAY, o["delivered"] - o["wonAt"]))
    for d, v in ch.items():
        g = grp(rank[(wi, d)][0]); c = 0; reached = None
        for at, ok in sorted(v):
            if ok:
                c = min(25, c + 1)
                if c == 25 and reached is None: reached = at
            else:
                halv[g] += 1; lost[g] += c - c // 2; c //= 2
        if rank[(wi, d)][0] < 3: first25[g].append(reached)
print("\norders/wk, late/wk, late %, halvings/wk, trust counts lost to halvings/wk:")
for g in G: print(f"  {g:9} {orders_by[g] / n:6.1f} {late_by[g] / n:5.2f} {100 * late_by[g] / max(orders_by[g], 1):5.1f}% {halv[g] / n:5.2f} {lost[g] / n:6.1f}")
for g in G[:3]:
    v = first25[g]; got = sorted(x for x in v if x is not None)
    print(f"  {g}: reaches 25 in {len(got)} of {len(v)} weeks; median at day {got[len(got) // 2] // DAY} {got[len(got) // 2] % DAY // 60}:00" if got else f"  {g}: never")
print("\nfrom the first minute the car can go (ready, or the win) to the delivery, and from the win to the delivery:")
for k, v in lag.items():
    a = sorted(x[0] for x in v); c = sorted(x[2] for x in v)
    print(f"  {k:14} n/wk {len(v) / n:6.1f}  ready->delivered median {a[len(a) // 2] / 60:5.1f} h, p75 {a[3 * len(a) // 4] / 60:5.1f} h; delivered on the ready day {100 * lib.mean(x[1] == 0 for x in v):4.1f}%, a day later {100 * lib.mean(x[1] == 1 for x in v):4.1f}%, later {100 * lib.mean(x[1] > 1 for x in v):4.1f}%; win->delivered median {c[len(c) // 2] / 60:5.1f} h")
# what trust is worth: quotes by trust, the same request features
print("\nwin share and margin a quote by trust at the quote, for the three largest dealers, Wednesday to Friday:")
for lo, hi in ((0, 4), (5, 9), (10, 14), (15, 19), (20, 24), (25, 25)):
    v = [q for q in quotes if rank[(q["w"], q["dealer"])][0] < 3 and q["day"] >= 2 and lo <= q["trust"] <= hi]
    if v: print(f"  trust {lo:2}-{hi:2}: quotes/wk {len(v) / n:6.1f} win {100 * lib.mean(q['won'] for q in v):4.1f}% quote/fee {lib.mean(q['m'] * q['list'] / q['fee'] for q in v):.3f} margin/quote {lib.mean(q['won'] * (q['m'] * q['list'] - 1.08 * q['fee']) for q in v) / 100:5.2f}")
