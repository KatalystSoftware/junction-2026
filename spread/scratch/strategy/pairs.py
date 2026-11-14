"""Round-trip pairs among a week's requests (scans): two one-car dealer requests that one driver can run out and
back as one gig, and how many a desk would hold if it kept a won car unposted while a return request may still come.
usage: pairs.py <data dir> <n scans> [near_km] [longest hold in hours]"""
import gzip, json, glob, sys, math, random, statistics as st
from multiprocessing import Pool
data, n = sys.argv[1], int(sys.argv[2])
NEAR = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0
MAXHOLD = float(sys.argv[4]) * 60 if len(sys.argv) > 4 else 10**9   # the longest a won car waits unposted for a return request, in hours
m = json.load(open(f"{data}/map.json"))
MIN = {(r["from"], r["to"]): r["minutes"] for r in m["roads"]}
P = {p["id"]: (p["lat"], p["lon"]) for p in m["places"]}
def km(a, b):
    (la, lo), (lb, lob) = P[a], P[b]
    x = math.radians(lob - lo) * math.cos(math.radians((la + lb) / 2)); y = math.radians(lb - la)
    return 6371 * math.hypot(x, y)
NEARP = {(a, b): km(a, b) <= NEAR for a in P for b in P}
DAY, HOUR = 1440, 60
HOLD = 8 * HOUR   # a held car is posted alone once it has this long to its last pickup minute
def next_open(t, hours):
    """The first minute from t that the site is open."""
    if hours is None: return t
    for _ in range(12):
        d, mi = divmod(t, DAY)
        wd = d % 7
        if wd in hours["weekdays"]: o, c = hours["opens"], hours["closes"]
        elif wd == 5 and hours.get("saturday"): o, c = hours["saturday"]["opens"], hours["saturday"]["closes"]
        else: t = (d + 1) * DAY; continue
        if mi < o: return d * DAY + o
        if mi < c: return t
        t = (d + 1) * DAY
    return t
def kind(r):
    if len(r["legs"]) > 1: return "trade_in"
    l = r["legs"][0]
    return "private" if l["pickup"]["privateAddress"] or l["delivery"]["privateAddress"] else ""
def facts(r, which):
    l = r["legs"][0]
    opts = sorted(r["options"], key=lambda o: o["deadline"])
    T = MIN[(l["pickup"]["placeId"], l["delivery"]["placeId"])]
    # the fastest option that leaves 5 hours to find a driver, as the policy's min_slack does
    ok = [o for o in opts if o["deadline"] - T - max(r["respondBy"], l["pickup"]["window"]["from"]) >= 300]
    if not ok: return None
    o = ok[0] if which == "fast" else ok[-1]
    return dict(id=r["id"], t=r["arrivedAt"], a=l["pickup"]["placeId"], b=l["delivery"]["placeId"], ready=l["pickup"]["window"]["from"], D=o["deadline"], T=T,
                ph=l["pickup"]["hours"], dh=l["delivery"]["hours"], ref=r["referenceFeeCents"], list=o["listPriceCents"], last=o["deadline"] - T)
def run(x, y, now):
    """The earliest end of the gig x then y that starts at `now` or later, or None."""
    between = MIN[(x["b"], y["a"])]
    if x["T"] + between + y["T"] > 12 * HOUR: return None
    t0 = max(now, x["ready"])
    for _ in range(4):
        s = next_open(t0, x["ph"])
        arrive = s + x["T"]
        if next_open(arrive, x["dh"]) > x["D"]: return None
        p2 = next_open(max(arrive + between, y["ready"]), y["ph"])
        end = p2 + y["T"]
        if next_open(end, y["dh"]) <= y["D"] and end - s <= 14 * HOUR:
            return end
        t0 = (s // DAY + 1) * DAY
    return None
def week(f):
    d = json.load(gzip.open(f))
    out = {}
    for which in ("fast", "slow"):
        rs = [x for x in (facts(e["request"], which) for e in d["events"] if e["kind"] == "price_request" and kind(e["request"]) == "") if x]
        rs.sort(key=lambda r: r["t"])
        partners = {r["id"]: [] for r in rs}   # earlier request id -> later requests that can pair with it while it is held
        for i, e in enumerate(rs):
            release = e["last"] - HOLD
            for l in rs[i + 1:]:
                if l["t"] + 15 > release or l["t"] - e["t"] > MAXHOLD: break
                if not ((l["a"] == e["b"] or NEARP[(l["a"], e["b"])]) and (l["b"] == e["a"] or NEARP[(l["b"], e["a"])])): continue
                now = l["t"] + 15 + HOUR
                if run(e, l, now) or run(l, e, now):
                    partners[e["id"]].append(l["id"])
        has = sum(1 for v in partners.values() if v)
        later = {x for v in partners.values() for x in v}
        # the most pairs, if the desk won every request: greedy by arrival
        used, pairs = set(), 0
        for e in rs:
            if e["id"] in used: continue
            for l in partners[e["id"]]:
                if l not in used:
                    used |= {e["id"], l}; pairs += 1; break
        # a desk that wins a lone request with chance p1 and the return of a held car with chance p2
        sims = {}
        by = {r["id"]: r for r in rs}
        for p1, p2 in ((0.30, 0.30), (0.30, 0.55), (0.30, 0.70), (0.40, 0.70)):
            tot, extra = 0, 0
            for k in range(20):
                rnd = random.Random(k)
                held, paired, wins = set(), set(), 0
                back = {}
                for e in rs:
                    for l in partners[e["id"]]: back.setdefault(l, []).append(e["id"])
                for r in rs:
                    cands = [e for e in back.get(r["id"], []) if e in held]
                    u = rnd.random()
                    if cands and u < p2:
                        held.discard(cands[0]); paired |= {cands[0], r["id"]}; tot += 1
                        extra += u >= p1
                    elif u < p1:
                        if partners[r["id"]]: held.add(r["id"])
            sims[(p1, p2)] = (tot / 20, extra / 20)
        out[which] = (len(rs), has, len(later | {k for k, v in partners.items() if v}), pairs, sims,
                      st.mean(by[k]["T"] for k, v in partners.items() if v) if has else 0, st.mean(r["T"] for r in rs))
    return out
if __name__ == "__main__":
    files = sorted(glob.glob(f"{data}/scans/fresh-*.json.gz"))[:n]
    with Pool(4) as p: res = p.map(week, files)
    for which in ("fast", "slow"):
        rows = [r[which] for r in res]
        print(f"== {which}est option quoted, near {NEAR} km, {len(rows)} weeks")
        print(" one-car dealer requests a week %.0f; with a later return request while held %.0f; in any pair %.0f; most pairs if all were won %.0f" % tuple(st.mean(r[i] for r in rows) for i in range(4)))
        print(" drive minutes: requests with a return %.0f, all %.0f" % (st.mean(r[5] for r in rows), st.mean(r[6] for r in rows)))
        for k in rows[0][4]:
            print("  win alone %.2f, win the return of a held car %.2f: pairs a week %.1f (sd %.1f), of which the return is an order the desk would not have won %.1f" % (k[0], k[1], st.mean(r[4][k][0] for r in rows), st.pstdev([r[4][k][0] for r in rows]), st.mean(r[4][k][1] for r in rows)))
