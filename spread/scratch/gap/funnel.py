"""Where the requests of a week go: declined by which rule, quoted, won. PYTHONPATH=. uv run --with numpy python scratch/gap/funnel.py <data> <cache> <variant>"""
import sys, json, collections
import lib
data, cache, variant = sys.argv[1:4]
minutes = lib.minutes_of(json.load(open(f"{data}/map.json")))
weeks = lib.cached(data, variant, minutes, cache)
n = len(weeks)
print(variant, n, "weeks; margin", lib.mean(w["score"]["marginCents"] for w in weeks) / 100, "orders", lib.mean(w["score"]["wonOrders"] for w in weeks),
      "on time", lib.mean(w["score"]["onTimeShare"] for w in weeks))
print("ledger per week:", {k: round(sum(w["ledger"].get(k, 0) for w in weeks) / n / 100) for k in set().union(*[w["ledger"] for w in weeks])})
funnel = collections.Counter(); bykind = collections.Counter(); wonk = collections.Counter(); optq = collections.Counter(); optw = collections.Counter()
for w in weeks:
    for rid, r in w["reqs"].items():
        dec = w["decisions"][rid]
        k = lib.req_kind(r["request"])
        bykind[k] += 1
        if dec["declined"]:
            funnel["declined:" + dec["declined"]] += 1
        else:
            funnel["quoted"] += 1
            funnel["won" if r["outcome"] == "won" else "lost"] += 1
            optq["+".join(sorted(dec["prices"]))] += 1
            if r["outcome"] == "won":
                optw[r["option"]] += 1
            offered = [o["kind"] for o in r["request"]["options"]]
            if "same_day" in offered and "same_day" not in dec["prices"]:
                funnel["quoted without same_day (slack)"] += 1
for k, v in sorted(funnel.items(), key=lambda x: -x[1]):
    print(f"{k:40} {v / n:7.1f}")
print("kinds/wk", {k: round(v / n, 1) for k, v in bykind.items()})
print("options quoted/wk", {k: round(v / n, 1) for k, v in optq.items()})
print("option won/wk", {k: round(v / n, 1) for k, v in optw.items()})
print("orders/wk min/median/max", sorted(w["score"]["wonOrders"] for w in weeks)[::max(1, n // 10)])
print("roster min/med/max", sorted(len(w["roster"]) for w in weeks)[::max(1, n // 6)])
