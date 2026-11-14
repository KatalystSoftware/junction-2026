"""The replay (replay.py) for the variants proposed for play (README.md), under their variant names.
PYTHONPATH=. uv run --with numpy python scratch/gap/replay_sent.py <data> <cache> <variant> [draws]"""
from replay import show, cls
BY_HOURS = {"<6": 1.55, "6-8": 1.35, "8-12": 1.3, "12-30": 1.2, "30+": 1.15}
due24 = lambda p: p[0] + p[1]
risky = lambda r: 0.15 * r["premium"] + 0.15 * (r["day"] == 4 and r["h"] < 12)
show("step-2: cost 1.3 + 0.02 a car", lambda p, r, t: 1.3 + 0.02 * sum(p))
show("step-2-gate-25", lambda p, r, t: 1.3 + 0.02 * sum(p), gate=25)
show("due-24-gate-25: 0.04 a car due within 24 h", lambda p, r, t: 1.3 + 0.04 * due24(p), gate=25)
show("hours: cost by hours + 0.04 a car", lambda p, r, t: BY_HOURS[cls(r["h"])] + 0.04 * sum(p))
show("hours-step-2-gate-25", lambda p, r, t: BY_HOURS[cls(r["h"])] + 0.02 * sum(p), gate=25)
show("hours-due-24-gate-25", lambda p, r, t: BY_HOURS[cls(r["h"])] + 0.04 * due24(p), gate=25)
show("hours-due-24-gate-25, premium and Friday same-day + 0.15", lambda p, r, t: BY_HOURS[cls(r["h"])] + risky(r) + 0.04 * due24(p), gate=25)
show("hours-due-24-gate-25 with 0.06 a car", lambda p, r, t: BY_HOURS[cls(r["h"])] + 0.06 * due24(p), gate=25)
