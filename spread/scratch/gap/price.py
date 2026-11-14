"""Why quotes are lost, and what volume the win curve gives at other costs. Static: trust and the competitor stay as played.
PYTHONPATH=. uv run --with numpy python scratch/gap/price.py <data> <cache> <variant>"""
import sys, json, math, collections
import lib
from spreadlab import curve
data, cache, variant = sys.argv[1:4]
minutes = lib.minutes_of(json.load(open(f"{data}/map.json")))
weeks = lib.cached(data, variant, minutes, cache)
M = curve.MODELS["day"]; B = M["slope"]
DAY = 1440
rows = []  # one per serious quote
for wi, w in enumerate(weeks):
    # trust per dealer over time, as the policy counts it
    changes = collections.defaultdict(list)  # dealer -> [(minute, on_time)]
    for o in w["orders"].values():
        if o["delivered"] is not None and not o["cancelled"]:
            changes[o["dealer"]].append((o["delivered"], not o["late"]))
    for d in changes: changes[d].sort()
    def trust_at(dealer, minute):
        c = 0
        for at, ok in changes.get(dealer, []):
            if at > minute: break
            c = min(25, c + 1) if ok else c // 2
        return c
    nreq = collections.Counter(r["request"]["dealerId"] for r in w["reqs"].values())
    for rid, r in w["reqs"].items():
        dec = w["decisions"][rid]
        if dec["declined"]: continue
        q = r["request"]
        options = [o for o in q["options"] if o["kind"] in dec["prices"]]
        first = curve.fastest(options)
        t = trust_at(q["dealerId"], q["arrivedAt"])
        a = curve.at_list(q, options, t, M)
        m = dec["prices"][first["kind"]] / first["listPriceCents"]
        rows.append({"w": wi, "day": q["arrivedAt"] // DAY, "min": q["arrivedAt"] % DAY, "a": a, "m": m, "won": r["outcome"] == "won", "list": first["listPriceCents"],
                     "fee": q["referenceFeeCents"], "trust": t, "dealer": q["dealerId"], "dealer_n": nreq[q["dealerId"]], "rid": rid, "at": q["arrivedAt"],
                     "from": q["legs"][0]["pickup"]["placeId"], "to": q["legs"][0]["delivery"]["placeId"], "kinds": "+".join(sorted(dec["prices"]))})
# the day's level, fitted after the fact on the whole day's answers (flat prior sd 0.3)
def fit(answers, sd=0.3):
    d = 0.0
    for _ in range(30):
        ch = [1 / (1 + math.exp(-(z + B * d))) for z, _ in answers]
        rise = B * sum(won - c for (_, won), c in zip(answers, ch)) - d / sd ** 2
        curv = B * B * sum(c * (1 - c) for c in ch) + 1 / sd ** 2
        d += max(-0.3, min(0.3, rise / curv))
    return d
byday = collections.defaultdict(list)
for r in rows: byday[(r["w"], r["day"])].append((r["a"] - B * math.log(r["m"]), r["won"]))
level = {k: fit(v) for k, v in byday.items()}
for r in rows: r["s"] = level[(r["w"], r["day"])]
n = len(weeks)
P = lambda r, m: 1 / (1 + math.exp(-(r["a"] - B * (math.log(m) - r["s"]))))
print("quotes/wk", len(rows) / n, "won/wk", sum(r["won"] for r in rows) / n, "model expects", sum(P(r, r["m"]) for r in rows) / n)
lv = sorted(level.values())
print("day levels: min %.2f p10 %.2f median %.2f p90 %.2f max %.2f" % (lv[0], lv[len(lv) // 10], lv[len(lv) // 2], lv[9 * len(lv) // 10], lv[-1]))
# lowest day of each week (the price war)
war = {}
for wi in range(n):
    days = {d: level[(wi, d)] for d in range(5) if (wi, d) in level}
    war[wi] = min(days, key=days.get)
print("war day by weekday:", collections.Counter(war.values()), "mean level of war day %.3f, of other days %.3f" % (
    lib.mean(level[(wi, war[wi])] for wi in range(n)), lib.mean(v for (wi, d), v in level.items() if d != war[wi])))
def table(name, key, order=None):
    g = collections.defaultdict(list)
    for r in rows: g[key(r)].append(r)
    print(f"\n{name:26} quotes/wk  won/wk  win%   quote/list quote/fee  margin@1.08fee/quote  expected chance")
    for k in (order or sorted(g)):
        v = g[k]
        if not v: continue
        print(f"{str(k):26} {len(v) / n:8.1f} {sum(r['won'] for r in v) / n:7.1f} {100 * lib.mean(r['won'] for r in v):5.1f}  {lib.mean(r['m'] for r in v):8.3f} {lib.mean(r['m'] * r['list'] / r['fee'] for r in v):8.3f}"
              f"  {lib.mean(r['won'] * (r['m'] * r['list'] - 1.08 * r['fee']) for r in v) / 100:8.2f} {100 * lib.mean(P(r, r['m']) for r in v):12.1f}")
table("weekday", lambda r: r["day"])
table("war day", lambda r: "war" if r["day"] == war[r["w"]] else "other")
table("dealer trust at quote", lambda r: "0" if r["trust"] == 0 else "1-4" if r["trust"] < 5 else "5-9" if r["trust"] < 10 else "10-14" if r["trust"] < 15 else "15-24" if r["trust"] < 25 else "25", ["0", "1-4", "5-9", "10-14", "15-24", "25"])
table("dealer requests in week", lambda r: "1-9" if r["dealer_n"] < 10 else "10-29" if r["dealer_n"] < 30 else "30-99" if r["dealer_n"] < 100 else "100+", ["1-9", "10-29", "30-99", "100+"])
table("hour", lambda r: r["min"] // 120 * 2)
table("options quoted", lambda r: r["kinds"])
# how far above the winning price were the lost quotes? The curve gives, for each lost quote, the price cut that would have made it a coin flip.
cut = sorted(max(0.0, (math.log(r["m"]) - r["s"]) - r["a"] / B) for r in rows if not r["won"])
print("\nlost quotes: the price cut (in log) to reach a 50%% chance: median %.3f, p25 %.3f, p75 %.3f; share needing under 5%%: %.2f, under 10%%: %.2f" % (
    cut[len(cut) // 2], cut[len(cut) // 4], cut[3 * len(cut) // 4], lib.mean(c < 0.05 for c in cut), lib.mean(c < 0.10 for c in cut)))
# the frontier: the best price at a cost c x the typical fee, trust and levels as played
print("\ncost in quote | orders/wk | revenue/order | margin/order and margin/wk when an order really costs k x its typical fee (k = 0.9, 1.0, 1.08, 1.15, 1.25)")
mult = [1.0 + 0.02 * i for i in range(71)]
for c in (0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.4):
    wins = rev = fee = 0.0
    for r in rows:
        best = max(mult, key=lambda m: (m * r["list"] - c * r["fee"]) * P(r, m))
        p = P(r, best); wins += p; rev += p * best * r["list"]; fee += p * r["fee"]
    line = f"{c:4.1f} | {wins / n:6.0f} | {rev / wins / 100:6.1f} | fee/order {fee / wins / 100:5.1f} |"
    for k in (0.9, 1.0, 1.08, 1.15, 1.25):
        line += f" {(rev - k * fee) / wins / 100:5.1f} / {(rev - k * fee) / n / 100:6.0f} |"
    print(line)
json.dump({"level": {f"{a}|{b}": v for (a, b), v in level.items()}, "war": war}, open(f"{cache}/levels-{variant}.json", "w"))
import pickle; pickle.dump(rows, open(f"{cache}/quotes-{variant}.pkl", "wb"))
