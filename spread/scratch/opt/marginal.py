"""Where the margin of the extra orders goes in play: a played variant against the reference on the same seeds, split into
orders, price, typical fee, fees paid, refunds and the rest. PYTHONPATH=. python scratch/opt/marginal.py <data> <variant> [...]"""
import gzip, json, os, sys, collections
data, variants = sys.argv[1], sys.argv[2:]
REF = "steep-notes-offers-8"
def week(variant, seed):
    d = json.load(gzip.open(f"{data}/runs/{variant}/{seed}-L8.json.gz"))
    typ = {r["request"]["id"]: r["request"]["referenceFeeCents"] for r in d["reveal"]["requests"]}
    listp = {r["request"]["id"]: {o["kind"]: o["listPriceCents"] for o in r["request"]["options"]} for r in d["reveal"]["requests"]}
    out = collections.Counter()
    for e in d["events"]:
        if e["kind"] == "order_won":
            o = e["order"]; out["orders"] += 1; out["typ"] += typ[o["id"]]; out["price"] += o["priceCents"]; out["list"] += listp[o["id"]][o["option"]]
        elif e["kind"] == "ledger":
            out[e["line"]["kind"]] += e["line"]["cents"]
    quoted = [r for r in d["reveal"]["requests"] if r["outcome"] != "unquoted" and not d["decisions"][r["request"]["id"]]["declined"]]
    out["quotes"] = len(quoted)
    out["late"] = round(d["score"]["wonOrders"] * (1 - d["score"]["onTimeShare"]))
    out["margin"] = d["score"]["marginCents"]
    return out
cache = {}
for v in variants:
    seeds = sorted(f[:-11] for f in os.listdir(f"{data}/runs/{v}") if f.endswith("-L8.json.gz") and os.path.exists(f"{data}/runs/{REF}/{f}"))
    a, b = collections.Counter(), collections.Counter()
    for s in seeds:
        a.update(week(v, s))
        if s not in cache: cache[s] = week(REF, s)
        b.update(cache[s])
    n = len(seeds)
    f = lambda c, k: c[k] / n / 100
    print(f"\n{v} against the reference, {n} weeks, per week")
    for name, c in (("reference", b), (v, a)):
        print(f"  {name:28} quotes {c['quotes']/n:6.1f} orders {c['orders']/n:6.1f} late {c['late']/n:5.1f} | price/order {c['price']/c['orders']/100:6.1f} = {c['price']/c['list']:.3f} x list = {c['price']/c['typ']:.3f} x typical | typical fee/order {c['typ']/c['orders']/100:5.1f}"
              f" | fees paid {-c['driver_fee']/c['typ']:.3f} x typical | revenue {f(c,'revenue'):7.0f} fees {f(c,'driver_fee'):7.0f} refunds {f(c,'late_refund')+f(c,'undelivered_penalty'):6.0f} other {f(c,'failed_visit')+f(c,'waiting')+f(c,'release_fee')+f(c,'fine'):5.0f} margin {f(c,'margin'):7.0f}")
    d_orders = (a["orders"] - b["orders"]) / n
    print(f"  extra orders {d_orders:+.1f}: revenue {f(a,'revenue')-f(b,'revenue'):+.0f}, fees {f(a,'driver_fee')-f(b,'driver_fee'):+.0f}, refunds {f(a,'late_refund')+f(a,'undelivered_penalty')-f(b,'late_refund')-f(b,'undelivered_penalty'):+.0f}, margin {f(a,'margin')-f(b,'margin'):+.0f}"
          f" = {(f(a,'margin')-f(b,'margin'))/d_orders:+.1f} an extra order; revenue an extra order {(f(a,'revenue')-f(b,'revenue'))/d_orders:.1f}, fees an extra order {-(f(a,'driver_fee')-f(b,'driver_fee'))/d_orders:.1f}, typical fee an extra order {(a['typ']-b['typ'])/n/100/d_orders:.1f}")
    # had the reference's orders kept their price and fee ratio: what the price change and the fee change on all orders cost
    price_effect = (a["price"] / a["typ"] - b["price"] / b["typ"]) * a["typ"] / n / 100
    fee_effect = -(a["driver_fee"] / a["typ"] - b["driver_fee"] / b["typ"]) * a["typ"] / n / 100
    print(f"  on all its orders: the lower price over typical fee is worth {price_effect:+.0f} a week, the higher fees paid over typical {-fee_effect:+.0f} a week")
