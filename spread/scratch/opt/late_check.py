"""The late model on weeks it was not fitted on: fitted on every other week, scored on the won orders of the rest.
PYTHONPATH=. uv run --with numpy python scratch/opt/late_check.py <data> <cache>"""
import sys
import numpy as np
from sim import Weeks, sig
data, cache = sys.argv[1:3]
weeks = Weeks(data, cache)
everything = list(range(len(weeks.W)))
weeks.fit(everything[0::2])
rows = [r for wi in everything[1::2] for r in weeks.W[wi] if r["life"]]
p = np.array([sig(weeks.logit(r, r["life"]["u"])) for r in rows]); y = np.array([float(r["life"]["late"]) for r in rows])
order = np.argsort(p); ranks = np.empty(len(p)); ranks[order] = np.arange(1, len(p) + 1)
auc = (ranks[y == 1].sum() - y.sum() * (y.sum() + 1) / 2) / (y.sum() * (len(y) - y.sum()))
print(f"{len(rows)} won orders of {len(everything[1::2])} unseen weeks, {100 * y.mean():.1f}% late; AUC {auc:.3f}")
print("fifth of the orders by predicted late chance | predicted | late | share of all late orders")
for k, idx in enumerate(np.array_split(order, 5)):
    print(f"  {k + 1} | {100 * p[idx].mean():5.1f}% | {100 * y[idx].mean():5.1f}% | {100 * y[idx].sum() / y.sum():5.1f}%")
top = order[-len(order) // 10:]
print(f"the riskiest tenth: predicted {100 * p[top].mean():.1f}%, late {100 * y[top].mean():.1f}%, {100 * y[top].sum() / y.sum():.0f}% of all late orders")
