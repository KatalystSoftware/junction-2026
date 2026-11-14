"""When waiting orders get booked: the chance of a first booking by clock hour for orders 2+ hours on the board, and looks in the first 5 minutes. Arguments: view rows JSON (views.py), the .npy that hazard.py wrote."""
import json, sys
import numpy as np
A = np.load(sys.argv[2]); k, clock, left, same, mult, lm, ev, late, near = A.T
s = k >= 2
print("orders 2+ hours on the board: chance of a first booking in the next hour, by clock hour (n)")
print(" ".join(f"{h:02d}:{ev[s & (np.floor(clock) == h)].mean():.3f}({int((s & (np.floor(clock) == h)).sum())})" for h in range(24)))
print("same, last pickup within 24 h:"); t = s & (left < 24) & (left > 0)
print(" ".join(f"{h:02d}:{ev[t & (np.floor(clock) == h)].mean():.3f}({int((t & (np.floor(clock) == h)).sum())})" for h in range(24)))
d = json.load(open(sys.argv[1])); C = d["cols"]; R = d["rows"]; i = {c: C.index(c) for c in C}
wave = {}
for r in R:
    if r[i["drops"]] == 0 and not r[i["had_book"]] and r[i["at"]] - r[i["first_post"]] <= 5: wave[(r[0], r[1], r[2])] = wave.get((r[0], r[1], r[2]), 0) + 1
O = [o for o in d["orders"] if o["posted"] is not None]; w = np.array([wave.get((o["variant"], o["seed"], o["id"]), 0) for o in O])
print("looks in the first 5 minutes (they stop at the booking): share with 0:", (w == 0).mean().round(3), "mean", w.mean().round(2), "quantiles 25/50/75/90", np.quantile(w, [.25, .5, .75, .9]))
opt = np.array([o["option"] for o in O]); near = np.array([o["near"] for o in O]); v = np.array([o["views"] for o in O])
print("orders with no look in 5 minutes by drivers notified:", " ".join(f"{a}-{b}:{(w[(near >= a) & (near < b)] == 0).mean():.2f}" for a, b in [(0, 5), (5, 10), (10, 20), (20, 40), (40, 160), (160, 999)]))
