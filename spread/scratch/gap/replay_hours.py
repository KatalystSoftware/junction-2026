"""The replay (replay.py) for a cost that follows the hours the desk has to find a driver.
PYTHONPATH=. uv run --with numpy python scratch/gap/replay_hours.py <data> <cache> <variant> [draws]"""
from replay import show, cls
BY_HOURS = {"<6": 1.55, "6-8": 1.35, "8-12": 1.3, "12-30": 1.2, "30+": 1.15}   # what such an order cost in the saved weeks, with 100 euros of lost trust a late order
MILD = {"<6": 1.45, "6-8": 1.35, "8-12": 1.3, "12-30": 1.25, "30+": 1.2}
due24 = lambda p: p[0] + p[1]
print("-- a cost by the hours to find a driver")
show("cost by hours + 0.04 a car", lambda p, r, t: BY_HOURS[cls(r["h"])] + 0.04 * sum(p))
show("cost by hours + 0.02 a car", lambda p, r, t: BY_HOURS[cls(r["h"])] + 0.02 * sum(p))
show("cost by hours + 0.01 a car", lambda p, r, t: BY_HOURS[cls(r["h"])] + 0.01 * sum(p))
show("cost by hours + 0.04 a car due within 24 h", lambda p, r, t: BY_HOURS[cls(r["h"])] + 0.04 * due24(p))
show("cost by hours + 0.04 a car due within 24 h, gate 25", lambda p, r, t: BY_HOURS[cls(r["h"])] + 0.04 * due24(p), gate=25)
show("milder cost by hours + 0.04 a car", lambda p, r, t: MILD[cls(r["h"])] + 0.04 * sum(p))
show("milder cost by hours + 0.02 a car", lambda p, r, t: MILD[cls(r["h"])] + 0.02 * sum(p))
show("milder cost by hours + 0.04 a car due within 24 h", lambda p, r, t: MILD[cls(r["h"])] + 0.04 * due24(p))
print("-- with the reference's flat cost, for comparison on the same draws")
show("cost 1.3 + 0.02 a car", lambda p, r, t: 1.3 + 0.02 * sum(p))
show("cost 1.3 + 0.01 a car", lambda p, r, t: 1.3 + 0.01 * sum(p))
show("cost 1.3 + 0.04 a car due within 24 h", lambda p, r, t: 1.3 + 0.04 * due24(p))
show("cost 1.2 + 0.04 a car", lambda p, r, t: 1.2 + 0.04 * sum(p))
show("cost 1.4 + 0.04 a car", lambda p, r, t: 1.4 + 0.04 * sum(p))
