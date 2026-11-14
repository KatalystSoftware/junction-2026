"""The demand side of the scenario map: the week's price level, the price-war day, the competitor's answer to our wins,
and what the day's live shift loses while it learns. Expected values from the win curve; no drivers.

    PYTHONPATH=. python scratch/scenarios/market.py <rows.json from extract.py>
"""
import collections, json, math, sys
import numpy as np
from spreadlab import curve

DAY, HOUR = 1440, 60
SLOPE = curve.MODELS["day"]["slope"]
W = json.load(open(sys.argv[1])); n = len(W)
COST = 1.5  # what the reference prices an order at on average, as a multiple of its typical fee (cost 1.3 plus the backlog surcharge)
MULT = np.array([curve.LOW + curve.STEP * k for k in range(int(round((curve.HIGH - curve.LOW) / curve.STEP)) + 1)]); LOGM = np.log(MULT)


def mle(z, y, sd=1.0, start=0.0, mean=0.0):
    d = start
    for _ in range(12):
        p = 1 / (1 + np.exp(-(z + SLOPE * d)))
        d += np.clip((SLOPE * (y - p).sum() - (d - mean) / sd**2) / (SLOPE**2 * (p * (1 - p)).sum() + 1 / sd**2), -0.3, 0.3)
    return d


def best(z, shift, list_, cost):
    em = (MULT * list_ - cost) / (1 + np.exp(-(z - SLOPE * (LOGM - shift))))
    return MULT[em.argmax()]


def em(z, m, shift, list_, cost):
    return (m * list_ - cost) / (1 + math.exp(-(z - SLOPE * (math.log(m) - shift))))


rows = []  # per week
loss = collections.defaultdict(float); cnt = collections.Counter()
dealer_drift = collections.defaultdict(list)
level_by_day = []
for w in W:
    Q = sorted([q for q in w["quotes"] if q["z"] is not None and q["outcome"] in ("won", "lost")], key=lambda q: q["at"])
    z0 = np.array([q["z"] - SLOPE * q["x"] for q in Q]); y = np.array([q["outcome"] == "won" for q in Q], float); day = np.array([q["at"] // DAY for q in Q])
    shifts = np.array([mle(z0[day == d], y[day == d]) for d in range(5)])
    war = int(shifts.argmin()); others = np.delete(shifts, war)
    level_by_day.append(shifts)
    won_day = collections.Counter(o["day"] for o in w["orders"] if not o["cancelled"])
    margin_day = collections.Counter()
    for o in w["orders"]:
        if not o["cancelled"]: margin_day[o["day"]] += (o["price"] - o["fees"] - o["refund"]) / 100
    rows.append(dict(seed=w["seed"], level=float(np.median(others)), war=war, war_gap=float(shifts[war] - np.median(others)), second_gap=float(np.sort(shifts)[1] - np.median(shifts)),
                     orders=w["score"]["wonOrders"], margin=w["score"]["marginCents"] / 100, ontime=w["score"]["onTimeShare"], drivers=w["drivers"],
                     war_orders=won_day[war], other_orders=np.mean([won_day[d] for d in range(5) if d != war]), war_margin=margin_day[war], other_margin=np.mean([margin_day[d] for d in range(5) if d != war]),
                     war_quotes=int((day == war).sum()), mon_shift=float(shifts[0]), day_sd=float(others.std())))
    # the largest dealer against the others, day by day: does it accept less as the week goes on?
    top = collections.Counter(q["dealer"] for q in Q).most_common(1)[0][0]; is_top = np.array([q["dealer"] == top for q in Q])
    for d in range(5):
        s = (day == d) & is_top
        if s.sum() >= 15 and ((day == d) & ~is_top).sum() >= 15:
            dealer_drift[d].append((mle(z0[s], y[s]) - mle(z0[(day == d) & ~is_top], y[(day == d) & ~is_top]), y[s].mean()))
    # what the live shift loses while it learns: the price by four live estimates against the price that knows the day's shift
    prev = []
    for d in range(5):
        idx = np.nonzero(day == d)[0]; true = shifts[d]
        zs, ys, ats = [], [], []
        carry = float(np.mean(prev)) * 0.5 if prev else 0.0  # half of the mean of the earlier days: the week's level, shrunk
        for i in idx:
            q = Q[i]; z = q["z"]; list_, cost = q["list"], COST * q["ref"]
            known = [k for k in range(len(ats)) if ats[k] + 15 <= q["at"]]
            kz, ky = np.array([zs[k] for k in known]), np.array([ys[k] for k in known])
            live = mle(kz, ky, 0.16) if len(known) else 0.0
            live_carry = mle(kz, ky, 0.16, mean=carry) if len(known) else carry
            # two hypotheses: an ordinary day around the carried level (sd 0.12), or a war day 0.22 lower (sd 0.05); pick by posterior weight
            if len(known):
                a, b = mle(kz, ky, 0.12, mean=carry), mle(kz, ky, 0.05, mean=carry - 0.22)
                ll = lambda dd: (ky * np.log(1 / (1 + np.exp(-(kz + SLOPE * dd)))) + (1 - ky) * np.log(1 - 1 / (1 + np.exp(-(kz + SLOPE * dd))) + 1e-12)).sum()
                la = ll(a) - (a - carry) ** 2 / (2 * 0.12**2) + math.log(0.8 / 0.12); lb = ll(b) - (b - carry + 0.22) ** 2 / (2 * 0.05**2) + math.log(0.2 / 0.05)
                wb = 1 / (1 + math.exp(min(50, la - lb))); two = (1 - wb) * a + wb * b
            else:
                two = carry - 0.2 * 0.22
            opt = em(z, best(z, true, list_, cost), true, list_, cost)
            kind = "war" if d == war else "monday" if d == 0 else "other"
            for name, est in [("zero", 0.0), ("live", live), ("carry", live_carry), ("two", two)]:
                loss[(name, kind)] += (opt - em(z, best(z, est, list_, cost), true, list_, cost)) / 100
                loss[(name, "first5" if len(known) < 5 else "first15" if len(known) < 15 else "later")] += (opt - em(z, best(z, est, list_, cost), true, list_, cost)) / 100
            cnt[kind] += 1; cnt["first5" if len(known) < 5 else "first15" if len(known) < 15 else "later"] += 1
            zs.append(z0[i]); ys.append(y[i]); ats.append(q["at"])
        prev.append(true)

A = {k: np.array([r[k] for r in rows], float) for k in rows[0] if k != "seed"}
c = lambda a, b: np.corrcoef(a, b)[0, 1]
L = np.array(level_by_day)
print(f"{n} weeks. day shifts (log price, against the curve): mean {L.mean():+.3f}; week level sd {A['level'].std():.3f} range {A['level'].min():+.2f} to {A['level'].max():+.2f}; ordinary days within a week sd {A['day_sd'].mean():.3f}")
print(f"lowest day: {A['war_gap'].mean():+.3f} under the week's other days (sd {A['war_gap'].std():.3f}); gap under -0.12 in {np.mean(A['war_gap'] < -.12):.2f} of weeks; which day {sorted(collections.Counter(A['war'].astype(int).tolist()).items())}")
print(f"  on it: {A['war_quotes'].mean():.0f} quotes, {A['war_orders'].mean():.1f} orders against {A['other_orders'].mean():.1f} on other days; margin {A['war_margin'].mean():.0f} against {A['other_margin'].mean():.0f}: the day costs {A['other_margin'].mean() - A['war_margin'].mean():.0f}")
for d in range(5):
    s = A["war"] == d
    if s.sum() >= 5: print(f"  war on {'Mon Tue Wed Thu Fri'.split()[d]}: weeks {int(s.sum()):3d} margin {A['margin'][s].mean():6.0f} orders {A['orders'][s].mean():4.0f} on time {A['ontime'][s].mean():.3f} lowest {A['ontime'][s].min():.3f}")
print(f"week level: corr with orders {c(A['level'], A['orders']):+.2f}, margin {c(A['level'], A['margin']):+.2f}, on time {c(A['level'], A['ontime']):+.2f}, drivers {c(A['level'], A['drivers']):+.2f}")
X = np.column_stack([np.ones(n), A["level"] - A["level"].mean(), (A["drivers"] - 800) / 100])
for name in ["orders", "margin", "ontime"]:
    wgt, *_ = np.linalg.lstsq(X, A[name], rcond=None); r = A[name] - X @ wgt; se = np.sqrt(np.diag(np.linalg.inv(X.T @ X)) * r.var(ddof=3))
    print(f"  {name:7s} = {wgt[0]:.3f} + {wgt[1] * 0.1:+.3f} per 0.10 of level (se {se[1] * 0.1:.3f}) {wgt[2]:+.3f} per 100 drivers (se {se[2]:.3f})")
order = np.argsort(A["level"])
for name, idx in [("lowest fifth of levels", order[: n // 5]), ("middle", order[n // 5: -(n // 5)]), ("highest fifth", order[-(n // 5):])]:
    print(f"  {name:24s} level {A['level'][idx].mean():+.3f} orders {A['orders'][idx].mean():4.0f} margin {A['margin'][idx].mean():6.0f} on time {A['ontime'][idx].mean():.3f} lowest {A['ontime'][idx].min():.3f}")
print("the largest dealer against the other dealers, by day (shift in log price; its win share):")
for d in range(5):
    v = np.array(dealer_drift[d]); print(f"  {'Mon Tue Wed Thu Fri'.split()[d]}: {v[:, 0].mean():+.3f} (se {v[:, 0].std() / math.sqrt(len(v)):.3f}), win share {v[:, 1].mean():.2f}, weeks {len(v)}")
print(f"\nexpected margin lost a week to not knowing the day's shift (cost {COST} x fee; the price that knows the shift is 0):")
print("  estimate   " + "".join(f"{k:>10s}" for k in ["war", "monday", "other", "first5", "first15", "later", "total"]))
for name in ["zero", "live", "carry", "two"]:
    print(f"  {name:10s} " + "".join(f"{loss[(name, k)] / n:10.0f}" for k in ["war", "monday", "other", "first5", "first15", "later"]) + f"{sum(loss[(name, k)] for k in ['war', 'monday', 'other']) / n:10.0f}")
print("  quotes a week: " + ", ".join(f"{k} {cnt[k] / n:.0f}" for k in ["war", "monday", "other", "first5", "first15", "later"]))
json.dump(rows, open(sys.argv[1].replace(".json", "-market.json"), "w"))
