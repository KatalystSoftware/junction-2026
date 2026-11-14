"""A grid over the prior sds of the live shifts of filt.py (day, pickup place, delivery place, pickup-today, dealer). Arguments: curve rows JSON, the .npy that filt.py wrote."""
import sys
import numpy as np
sys.path.insert(0, __import__("os").path.dirname(__file__))
from lib import *
from filt import replay
d = load(sys.argv[1]); y = d["y"]; zs = np.load(sys.argv[2]); z, slope = zs[:, 0], zs[:, 1]
def score(label, sds, mult=1.0, **kw):
    sh = replay(d, z, slope * mult, sds, **kw); p = sigmoid(z - slope * mult * (d["x"] - sh))
    print(f"{label:64s} {logloss(p, y):.4f} | by weekday " + " ".join(f"{logloss(p[d['day'] == k], y[d['day'] == k]):.4f}" for k in range(5)), flush=True)
for day in (0.10, 0.13, 0.16, 0.20, 0.25):
    score(f"day {day} + from 0.06 + to 0.06", {"day": day, "from": 0.06, "to": 0.06})
for s in (0.03, 0.045, 0.08, 0.10, 0.14):
    score(f"day 0.16 + from {s} + to {s}", {"day": 0.16, "from": s, "to": s})
score("day 0.16 + from 0.08", {"day": 0.16, "from": 0.08})
score("day 0.16 + to 0.08", {"day": 0.16, "to": 0.08})
for q in (0.02, 0.04):
    score(f"day 0.16 + from 0.06 + to 0.06, moving {q} a morning", {"day": 0.16, "from": 0.06, "to": 0.06}, q=q)
for s in (0.05, 0.10, 0.15):
    score(f"day 0.16 + from 0.06 + to 0.06 + from-today {s}", {"day": 0.16, "from": 0.06, "to": 0.06, "from_day": s})
for s in (0.03, 0.06):
    score(f"day 0.16 + from 0.06 + to 0.06 + dealer-today {s}", {"day": 0.16, "from": 0.06, "to": 0.06, "dealer_day": s})
for s, q in ((0.02, 0.02), (0.0001, 0.03)):
    score(f"day 0.16 + from + to + dealer {s} moving {q}", {"day": 0.16, "from": 0.06, "to": 0.06, "dealer": s}, q=q)
for mult in (0.9, 1.05):
    score(f"day 0.16 + from 0.06 + to 0.06, slope x {mult}", {"day": 0.16, "from": 0.06, "to": 0.06}, mult=mult)
