"""Is there a day a week on which far fewer drivers look at a new gig (the flu: 30% of the drivers who meant to work
stay at home for a day)? How early does it show, and what does it cost? And: when in the week are the late orders of
the worst weeks won, so what could a controller on the projected late share still stop?

    python scratch/scenarios/flu.py <rows.json from extract.py>
"""
import collections, json, math, sys
import numpy as np

DAY, HOUR = 1440, 60
W = json.load(open(sys.argv[1])); n = len(W)
# expected lookers in a gig's first 15 minutes, from how many drivers the app notifies, by weekday and hour band
O = [dict(o, seed=w["seed"]) for w in W for o in w["orders"] if not o["cancelled"] and o["post"] is not None and o["post"] == o["won"] and o["post"] % DAY < 18 * HOUR and o["post"] // DAY < 5]
near = np.array([o["near"] for o in O], float); v = np.array([o["v15"] for o in O], float); day = np.array([o["post"] // DAY for o in O]); hour = np.array([o["post"] % DAY // 60 for o in O])
band = np.digitize(near, [5, 20, 50, 100, 200, 400])
exp = np.zeros(len(O))
for b in range(7):
    for d in range(5):
        s = (band == b) & (day == d)
        if s.sum(): exp[s] = v[s].mean()
print(f"{len(O)} cars posted at the win, {len(O) / n:.0f} a week; lookers in the first 15 minutes by drivers notified:",
      {f"{lo}+": round(float(v[band == b].mean()), 2) for b, lo in enumerate([0, 5, 20, 50, 100, 200, 400]) if (band == b).any()})
print("  by weekday:", [round(float(v[day == d].mean()), 2) for d in range(5)], "booked in an hour:", [round(float(np.mean([(o['book'] or 1e9) - o['post'] <= 60 for o in O if o['post'] // DAY == d])), 3) for d in range(5)])
seeds = sorted({o["seed"] for o in O}); si = np.array([seeds.index(o["seed"]) for o in O])
ratio = np.full((len(seeds), 5), np.nan); cnt = np.zeros((len(seeds), 5)); late = np.full((len(seeds), 5), np.nan); h1 = np.full((len(seeds), 5), np.nan)
lt = np.array([o["late"] for o in O], float); b1 = np.array([(o["book"] or 1e9) - o["post"] <= 60 for o in O], float)
for i in range(len(seeds)):
    for d in range(5):
        s = (si == i) & (day == d)
        cnt[i, d] = s.sum()
        if s.sum() >= 8: ratio[i, d] = v[s].sum() / exp[s].sum(); late[i, d] = lt[s].mean(); h1[i, d] = b1[s].mean()
ok = ~np.isnan(ratio).any(axis=1)
R = ratio[ok] / np.nanmedian(ratio[ok], axis=1, keepdims=True)
srt = np.sort(R, axis=1)
print(f"\n{ok.sum()} weeks with 8+ cars posted on each day. lookers against expected, each day over the week's median day: lowest day {srt[:, 0].mean():.2f} (quantiles {np.quantile(srt[:, 0], [.1, .5, .9]).round(2)}), second lowest {srt[:, 1].mean():.2f}, highest {srt[:, -1].mean():.2f}")
print(f"  lowest day under 0.80 of the median day in {np.mean(srt[:, 0] < .8):.2f} of weeks, under 0.70 in {np.mean(srt[:, 0] < .7):.2f}; the gap between the lowest and second lowest day: {np.mean(srt[:, 1] - srt[:, 0]):.2f}")
low = R.argmin(axis=1)
print("  which day:", sorted(collections.Counter(low.tolist()).items()))
L, H = late[ok], h1[ok]
l_low = np.array([L[i, low[i]] for i in range(len(L))]); l_oth = np.array([np.delete(L[i], low[i]).mean() for i in range(len(L))])
h_low = np.array([H[i, low[i]] - np.nanmean(h1[:, low[i]]) for i in range(len(H))]); h_oth = np.array([np.mean(np.delete(H[i] - np.nanmean(h1, axis=0), low[i])) for i in range(len(H))])
c_low = np.array([cnt[ok][i, low[i]] for i in range(len(L))])
print(f"  on that day: late {l_low.mean():.3f} against {l_oth.mean():.3f} on the week's other days (difference {np.mean(l_low - l_oth):+.3f}, se {np.std(l_low - l_oth) / math.sqrt(len(L)):.3f}); booked within the hour {h_low.mean():+.3f} against {h_oth.mean():+.3f} (weekday means removed); cars posted {c_low.mean():.0f}")
# same comparison, but only for weeks where the lowest day is clear (under 0.75)
clear = srt[:, 0] < 0.75
print(f"  weeks where it is under 0.75 ({clear.sum()}): late {l_low[clear].mean():.3f} against {l_oth[clear].mean():.3f}; booked within the hour {h_low[clear].mean():+.3f} against {h_oth[clear].mean():+.3f}; so about {(l_low[clear].mean() - l_oth[clear].mean()) * c_low[clear].mean():.1f} more late orders in such a week")
# how early: the day's ratio from its first k cars
for k in (5, 10, 15, 20):
    hit, false, at = 0, 0, []
    for i, seed in enumerate(np.array(seeds)[ok]):
        base = None
        for d in range(5):
            idx = np.nonzero((si == seeds.index(seed)) & (day == d))[0]
            idx = idx[np.argsort([O[j]["post"] for j in idx])][:k]
            if len(idx) < k: continue
            r_ = v[idx].sum() / exp[idx].sum() / np.nanmedian(ratio[seeds.index(seed)])
            flagged = r_ < 0.75
            if flagged and d == low[i] and clear[i]: hit += 1; at.append(O[idx[-1]]["post"] % DAY / 60)
            elif flagged and not (d == low[i] and clear[i]): false += 1
    print(f"  flag a day when its first {k} cars draw under 0.75 of the week's usual lookers: catches {hit} of {clear.sum()} clear days, at {np.median(at) if at else float('nan'):.1f} o'clock (median); flags {false} other days of {5 * ok.sum() - clear.sum()}")

# the worst weeks: when were their late orders won, and with how much time to find a driver
print("\nlate orders by the day they were won, in the weeks over 7.5% late and in the others:")
for name, sel in [("over 7.5% late", lambda w: 1 - w["score"]["onTimeShare"] > .075), ("others", lambda w: 1 - w["score"]["onTimeShare"] <= .075)]:
    WW = [w for w in W if sel(w)]
    byday = np.zeros(5); wonday = np.zeros(5); short = 0; total = 0
    for w in WW:
        for o in w["orders"]:
            if o["cancelled"]: continue
            wonday[o["day"]] += 1
            if o["late"]:
                byday[o["day"]] += 1; total += 1; short += (o["last"] - o["won"]) < 12 * 60
    print(f"  {name:15s} weeks {len(WW):3d}: late a week {total / len(WW):5.1f}; won on Mon..Fri {(byday / len(WW)).round(1)}; late share by day won {(byday / wonday).round(3)}; with under 12 hours to the last pickup at the win: {short / total:.2f}")
# the projected late share at the end of each day: resolved late orders plus the policy's chances for open ones (0.03 held, 0.15 waiting, 0.40 waiting two hours)
print("\nthe week's final late share against what is already late or waiting at the end of each day:")
proj = np.zeros((n, 5)); final = np.array([1 - w["score"]["onTimeShare"] for w in W]); remaining = np.zeros((n, 5))
for i, w in enumerate(W):
    Ow = [o for o in w["orders"] if not o["cancelled"]]
    for d in range(5):
        t = d * DAY + 18 * HOUR; late_ = 0.0; won = [o for o in Ow if o["won"] <= t]
        for o in won:
            done = o["delivered"] is not None and o["delivered"] <= t
            if done: late_ += o["late"]
            elif o["deadline"] < t: late_ += 1
            else:
                held = o["book"] is not None and o["book"] <= t and (o["lastbook"] or 0) <= t  # a driver holds it (ignores a later drop)
                late_ += 0.03 if held else 0.40 if t - o["won"] >= 120 else 0.15
        proj[i, d] = late_ / max(1, len(won)); remaining[i, d] = sum(1 for o in Ow if o["won"] > t and o["late"])
for d in range(5):
    worst = final > .075
    print(f"  {'Mon Tue Wed Thu Fri'.split()[d]} 18:00: correlation {np.corrcoef(proj[:, d], final)[0, 1]:+.2f}; projection in the worst weeks {proj[worst, d].mean():.3f} against {proj[~worst, d].mean():.3f}; late orders still to be won after it, worst weeks {remaining[worst, d].mean():.1f} of {np.mean([sum(o['late'] for o in w['orders'] if not o['cancelled']) for w, x in zip(W, worst) if x]):.1f}")
