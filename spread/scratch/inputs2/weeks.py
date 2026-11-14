"""Merge 1's played weeks (rows on trackb-rounds): which week-level inputs go with a low week."""
import sys, pandas as pd, numpy as np
R = sys.argv[1]
M1 = "fee16-80-q24-wide-pairs-0.6-return-0.75"
fr = []
for f in ("exam", "ladder1", "q1", "cand-nat", "cand-thin"):
    d = pd.read_csv(f"{R}/{f}.csv"); d["file"] = f; fr.append(d)
a = pd.concat(fr, ignore_index=True)
a["wave"] = a.drop_wave_days.fillna("")
a["late_share"] = a.late / a.orders
a["fri_share"] = a.friday_due / a.orders
a["num"] = a.seed.str.split("-").str[1].astype(int)
m = a[a.variant == M1].drop_duplicates("seed").copy()
print("merge 1 weeks", len(m), "by file", m.file.value_counts().to_dict())
def tab(d, by, name):
    g = d.groupby(by, observed=True).agg(weeks=("seed", "size"), orders=("orders", "mean"), late=("late", "mean"), on_time=("on_time", "mean"), low=("on_time", "min"),
                          u90=("on_time", lambda s: (s < .90).sum()), u92=("on_time", lambda s: (s < .92).sum()), margin=("margin", "mean"), fri=("friday_due", "mean"))
    print(f"\n== {name}\n", g.round(3).to_string())
m["band"] = pd.cut(m.drivers, [0, 660, 690, 720, 760, 800, 850, 900, 2000], right=False)
tab(m, "band", "merge 1 by drivers listed")
m["wv"] = np.where(m.wave.str.contains("F"), "Fri wave", np.where(m.wave != "", "wave Mon-Thu", "no wave"))
tab(m, "wv", "merge 1 by drop wave")
m["thin"] = m.drivers < 720
tab(m, ["thin", "wv"], "merge 1 thin x wave")
m["fb"] = pd.cut(m.friday_due / m.drivers * 100, [0, 9, 11, 13, 15, 100], right=False)
tab(m, "fb", "merge 1 by orders due Friday per 100 drivers")
tab(m, ["wv", "fb"], "wave x friday due per 100 drivers")
m["ob"] = pd.cut(m.orders / m.drivers * 100, [0, 36, 40, 44, 48, 100], right=False)
tab(m, "ob", "merge 1 by orders per 100 drivers")
print("\nlowest 14 merge 1 weeks\n", m.sort_values("on_time").head(14)[["seed", "drivers", "orders", "late", "on_time", "margin", "friday_due", "wave", "pair_gigs", "failed_visits"]].to_string())
# what is known when: correlation / AUC for a week under 92%
from sklearn.metrics import roc_auc_score
y = (m.on_time < .92).astype(int)
for name, x in (("drivers (Mon 08:00)", -m.drivers), ("orders per driver (Fri 18:00)", m.orders / m.drivers), ("Friday due per driver (Thu 20:00)", m.friday_due / m.drivers), ("Friday due", m.friday_due),
                ("Friday wave", m.wave.str.contains("F").astype(int)), ("any wave", (m.wave != "").astype(int))):
    print(f"AUC week under 92%: {name:36s} {roc_auc_score(y, x):.3f}   corr with late share {np.corrcoef(x, m.late_share)[0,1]:+.2f}")
import statsmodels.api as sm
X = pd.DataFrame({"drivers100": (m.drivers - 760) / 100, "fri_per100": m.friday_due / m.drivers * 100 - 11, "friwave": m.wave.str.contains("F").astype(float), "otherwave": ((m.wave != "") & ~m.wave.str.contains("F")).astype(float)})
X["friwave_x_fri"] = X.friwave * X.fri_per100
fit = sm.GLM(np.c_[m.late, m.orders - m.late], sm.add_constant(X), family=sm.families.Binomial()).fit(scale="X2")
print(fit.summary().tables[1])
# default paired where present: is merge 1's on-time gap to the default larger in thin worlds?
d = a[a.variant == "slow-friday-late-150-kinds-limits"].drop_duplicates("seed").set_index("seed")
j = m.set_index("seed").join(d[["orders", "late", "on_time", "margin"]], rsuffix="_d", how="inner")
j["band2"] = pd.cut(j.drivers, [0, 720, 800, 2000], right=False)
print("\npaired with the default, by drivers\n", j.groupby("band2", observed=True).agg(weeks=("orders", "size"), orders=("orders", "mean"), orders_d=("orders_d", "mean"), late=("late", "mean"), late_d=("late_d", "mean"),
      on=("on_time", "mean"), on_d=("on_time_d", "mean"), low=("on_time", "min"), low_d=("on_time_d", "min"), margin=("margin", "mean"), margin_d=("margin_d", "mean")).round(3).to_string())
