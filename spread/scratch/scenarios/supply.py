"""Which live signals mark a week short of drivers, and when. And: is there a day a week with far fewer drivers (the flu)?

    python scratch/scenarios/supply.py <rows.json from extract.py> [<more rows.json> ...]
"""
import collections, json, sys
import numpy as np

DAY, HOUR = 1440, 60
W = [w for path in sys.argv[1:] for w in json.load(open(path))]
n = len(W)
c = lambda a, b: np.corrcoef(a, b)[0, 1]


def feats(w):
    O = [o for o in w["orders"] if not o["cancelled"] and o["post"] is not None]
    late = np.array([o["late"] for o in O], float); day = np.array([o["day"] for o in O])
    wait = np.array([1e9 if o["book"] is None else o["book"] - o["post"] for o in O], float)
    near = np.array([o["near"] for o in O], float)
    hours = np.array([(o["last"] - o["post"]) / 60 for o in O])
    f = dict(drivers=w["drivers"], orders=len(O), late=late.mean(), late_after_mon=late[day >= 1].mean(), late_after_tue=late[day >= 2].mean(),
             thin20=(near < 20).mean(), thin5=(near < 5).mean())
    # the same, over all requests of the week, known from the roster and the requests: no outcome in it
    Q = [q for q in w["quotes"] if q["legs"] == 1 and not q["private"]]
    f["req_thin20"] = np.mean([w["near"].get(q["pick"], 0) < 20 for q in Q]); f["req_thin5"] = np.mean([w["near"].get(q["pick"], 0) < 5 for q in Q])
    f["req_thin20_mon"] = np.mean([w["near"].get(q["pick"], 0) < 20 for q in Q if q["at"] < DAY])
    for name, upto in [("mon12", 12 * HOUR), ("mon", DAY), ("tue", 2 * DAY), ("wed", 3 * DAY)]:
        s = np.array([o["post"] < upto - 60 for o in O])
        f["h1_" + name] = (wait[s] <= 60).mean() if s.sum() >= 5 else np.nan
        f["m5_" + name] = (wait[s] <= 5).mean() if s.sum() >= 5 else np.nan
        f["n_" + name] = int(s.sum())
        # waiting cars: posted before `upto`, unbooked for 2 hours or more
        f["slow_" + name] = (wait[s] > 120).mean() if s.sum() >= 5 else np.nan
        f["late_sofar_" + name] = np.mean([o["late"] and (o["delivered"] or 10**9) <= upto or (o["late"] and o["deadline"] <= upto) for o in O if o["won"] < upto] or [0])
    f["late_fri"] = late[day == 4].mean() if (day == 4).any() else np.nan
    return f


F = [feats(w) for w in W]
A = {k: np.array([f[k] for f in F], float) for k in F[0]}
print(f"{n} weeks; late share mean {A['late'].mean():.4f} sd {A['late'].std():.4f}")
print("correlation with the week's final late share / with the late share of orders won after that point:")
for k in ["drivers", "req_thin20", "req_thin5", "req_thin20_mon", "orders"]:
    print(f"  {k:16s} {c(A[k], A['late']):+.2f}   after Monday {c(A[k], A['late_after_mon']):+.2f}   after Tuesday {c(A[k], A['late_after_tue']):+.2f}")
for name, after in [("mon12", "late"), ("mon", "late_after_mon"), ("tue", "late_after_tue"), ("wed", "late")]:
    ok = ~np.isnan(A["h1_" + name])
    print(f"  by {name:6s} (cars posted {np.nanmean(A['n_' + name]):.0f}): booked in an hour {c(A['h1_' + name][ok], A['late'][ok]):+.2f} / later orders {c(A['h1_' + name][ok], A[after][ok]):+.2f};"
          f" in 5 minutes {c(A['m5_' + name][ok], A['late'][ok]):+.2f} / {c(A['m5_' + name][ok], A[after][ok]):+.2f}; waiting 2 hours+ {c(A['slow_' + name][ok], A['late'][ok]):+.2f} / {c(A['slow_' + name][ok], A[after][ok]):+.2f}")


def fit(names, y, label):
    X = np.column_stack([np.ones(n)] + [(A[k] - np.nanmean(A[k])) / np.nanstd(A[k]) for k in names]); ok = ~np.isnan(X).any(axis=1) & ~np.isnan(y)
    w, *_ = np.linalg.lstsq(X[ok], y[ok], rcond=None); r = y[ok] - X[ok] @ w
    # leave-one-out R2
    H = X[ok] @ np.linalg.pinv(X[ok].T @ X[ok]) @ X[ok].T; loo = r / (1 - np.diag(H))
    print(f"  {label:44s} R2 {1 - r.var() / y[ok].var():.2f}  leave-one-out R2 {1 - (loo**2).mean() / y[ok].var():.2f}  weights (points of late share per sd) {(100 * w[1:]).round(2)}")
    return X, w, ok


print("predicting the late share of orders won after Monday (per sd of each signal):")
y = A["late_after_mon"]
fit(["drivers"], y, "roster size")
fit(["req_thin20"], y, "share of requests from thin towns")
fit(["drivers", "req_thin20"], y, "roster + thin towns")
fit(["h1_mon"], y, "Monday: booked within the hour")
fit(["slow_mon"], y, "Monday: waiting 2 hours or more")
fit(["drivers", "h1_mon"], y, "roster + Monday's hour")
fit(["drivers", "req_thin20", "h1_mon"], y, "roster + thin towns + Monday's hour")
fit(["drivers", "req_thin20", "slow_mon"], y, "roster + thin towns + Monday waiting")
y = A["late_after_tue"]
print("predicting the late share of orders won after Tuesday:")
fit(["drivers"], y, "roster size"); fit(["h1_tue"], y, "to Tuesday: booked within the hour"); fit(["slow_tue"], y, "to Tuesday: waiting 2 hours+"); fit(["drivers", "req_thin20", "h1_tue"], y, "roster + thin towns + hour to Tuesday")
fit(["drivers", "req_thin20", "slow_tue"], y, "roster + thin towns + waiting to Tuesday")

# the weeks nearest the rule: which signal would have flagged them, and how many others with them
low = A["late"] > 0.075
print(f"\nweeks over 7.5% late: {low.sum()} of {n}")
for k, sign in [("drivers", -1), ("req_thin20", 1), ("h1_mon", -1), ("slow_mon", 1), ("h1_tue", -1), ("slow_tue", 1)]:
    v = sign * A[k]; order = np.argsort(-v)
    for share in (0.1, 0.2, 0.33):
        top = order[: int(n * share)]
        print(f"  flag the {int(share * 100)}% of weeks with the worst {k:12s}: catches {low[top].sum()} of {low.sum()}; mean late in flagged {A['late'][top].mean():.3f} against {np.delete(A['late'], top).mean():.3f}")

# the flu: a day with far fewer bookings in the first hour than the week's other days
print("\nday by day: share of cars posted that day and booked within the hour; the week's lowest day against its others")
rows = []
for w in W:
    d = [(x["h1"] / x["posted"], x["posted"], x["viewers"], x["late"] / x["posted"]) for x in w["days"][:5] if x["posted"] >= 10]
    if len(d) == 5: rows.append(d)
R = np.array(rows)
print("  mean by weekday: booked in an hour", R[:, :, 0].mean(axis=0).round(3), "viewers", R[:, :, 2].mean(axis=0).round(0), "late", R[:, :, 3].mean(axis=0).round(3))
rel = R[:, :, 0] - R[:, :, 0].mean(axis=0)  # against the weekday's usual share
rel = rel - rel.mean(axis=1, keepdims=True)
lowest = rel.argmin(axis=1)
print(f"  lowest day's gap to the week's other days: mean {rel.min(axis=1).mean():+.3f}; quantiles {np.quantile(rel.min(axis=1), [.1, .5, .9]).round(3)}; which day {collections.Counter(lowest.tolist())}")
vrel = np.log(R[:, :, 2] / R[:, :, 2].mean(axis=0)); vrel = vrel - np.median(vrel, axis=1, keepdims=True)
print(f"  lowest day's viewers against the week's median day: mean {np.exp(vrel.min(axis=1)).mean():.2f}; quantiles {np.exp(np.quantile(vrel.min(axis=1), [.1, .5, .9])).round(2)}; second lowest {np.exp(np.sort(vrel, axis=1)[:, 1].mean()):.2f}")
vl = vrel.argmin(axis=1)
late_low = np.array([R[i, vl[i], 3] for i in range(len(R))]); late_other = np.array([np.delete(R[i, :, 3], vl[i]).mean() for i in range(len(R))])
h_low = np.array([rel[i, vl[i]] for i in range(len(R))])
print(f"  on the day with fewest viewers: late {late_low.mean():.3f} against {late_other.mean():.3f} on the other days; booked-in-an-hour gap {h_low.mean():+.3f}; that day is {collections.Counter(vl.tolist())}")
