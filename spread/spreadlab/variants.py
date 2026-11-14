"""Named variants: each changes some of the policy's parameters (policy.DEFAULTS). Add one here to
compare it with the others on the same seeds."""
from __future__ import annotations

GATE_10 = {"same_day": True, "floor": 1.7, "quote_share": 1, "max_unbooked": 10}  # the reference, `gate-10`
# `curve-live-surcharge`: the win curve sets the price, the day's answers correct it, and the backlog raises the cost
CURVE = {"same_day": True, "quote_share": 1, "floor": 0, "curve": True, "learn": 0.16, "max_unbooked": 15, "backlog_step": 0.04}

VARIANTS: dict[str, dict] = {
    "baseline": {},
    # The anchor that does nothing: declines every request. Any variant must beat it in the same week.
    "decline-all": {"quote_share": 0},
    # One rule changed at a time, to show what each is worth.
    "price-1.4": {"price": 1.4},
    "price-1.6": {"price": 1.6},
    "share-0.4": {"quote_share": 0.4},
    "share-0.8": {"quote_share": 0.8},
    "fee-1.0": {"fee": 1.0},
    "with-same-day": {"same_day": True},
    "with-private": {"private": True},
    "with-trade-in": {"trade_in": True},
    "notified-10": {"min_notified": 10},
    # A driver's fee is a multiple of the typical fee, not of the list price: never quote under this multiple of it.
    "floor-1.5": {"same_day": True, "floor": 1.5},
    "floor-1.7": {"same_day": True, "floor": 1.7},
    "floor-1.9": {"same_day": True, "floor": 1.9},
    # With the floor, fewer cars are won: quote every acceptable request instead of 60% of them.
    "floor-1.7-all": {"same_day": True, "floor": 1.7, "quote_share": 1},
    # Quote every acceptable request, but none while this many won cars wait for a driver.
    "gate-5": {"same_day": True, "floor": 1.7, "quote_share": 1, "max_unbooked": 5},
    "gate-10": {"same_day": True, "floor": 1.7, "quote_share": 1, "max_unbooked": 10},
    "gate-15": {"same_day": True, "floor": 1.7, "quote_share": 1, "max_unbooked": 15},
    "floor-1.5-gate-10": {"same_day": True, "floor": 1.5, "quote_share": 1, "max_unbooked": 10},
    # The floor or the backlog limit follows the driver list, which is known before the first quote.
    # Every week asks for about 1,055 cars, so 900 drivers is 1.17 cars a driver and 800 is 1.32.
    "tight-floor": {**GATE_10, "floor": 1.5, "tight_drivers": 900, "when_tight": {"floor": 1.7}},
    "tight-gate": {**GATE_10, "max_unbooked": 15, "tight_drivers": 800, "when_tight": {"max_unbooked": 10}},
    # While the projected on-time share is under 93%: stop quoting, or quote only next-day cars while no won car waits.
    "gate-10-stop-93": {**GATE_10, "min_on_time": 0.93, "when_behind": {"quote_share": 0}},
    "gate-10-careful-93": {**GATE_10, "min_on_time": 0.93, "when_behind": {"same_day": False, "max_unbooked": 1}},
    "gate-10-pricey-93": {**GATE_10, "min_on_time": 0.93, "when_behind": {"floor": 2.1}},
    # The floor follows the dealer's answers in the week: 1.5 to start and on Monday, 1.7 and 1.9 once the desk wins 15% and 35% there.
    "dealer-ladder": {**GATE_10, "floor": 1.5, "dealer_steps": [[0.15, 1.7], [0.35, 1.9]]},
    "monday-1.5": {**GATE_10, "day_floor": {"0": 1.5}},
    "ladder": {**GATE_10, "floor": 1.5, "dealer_steps": [[0.15, 1.7], [0.35, 1.9]], "day_floor": {"0": 1.5}},
    # A dealer accepts 1% more for each order it had on time, up to 25: ask for all of it, or for half.
    "trust-1.0": {**GATE_10, "trust": 0.01},
    "trust-0.5": {**GATE_10, "trust": 0.005},
    # The backlog raises the price instead of stopping the quotes: by 0.04 or 0.08 of the typical fee for each won car without a driver.
    "surcharge-4": {**GATE_10, "max_unbooked": 0, "backlog_step": 0.04},
    "surcharge-8": {**GATE_10, "max_unbooked": 0, "backlog_step": 0.08},
    "surcharge-4-gate-15": {**GATE_10, "max_unbooked": 15, "backlog_step": 0.04},
    # The win curve sets the price: alone, corrected by the day's answers, and with the backlog in the cost.
    "curve": {**GATE_10, "floor": 0, "curve": True},
    "curve-live": {**GATE_10, "floor": 0, "curve": True, "learn": 0.16},
    "curve-live-surcharge": CURVE,
    # Around curve-live-surcharge, one parameter at a time: the cost of an order, the size of a day's correction, the backlog.
    "curve-cost-1.3": {**CURVE, "cost": 1.3},
    "curve-cost-1.5": {**CURVE, "cost": 1.5},
    "curve-learn-0.10": {**CURVE, "learn": 0.10},
    "curve-learn-0.25": {**CURVE, "learn": 0.25},
    "curve-step-8": {**CURVE, "backlog_step": 0.08},
    "curve-gate-10": {**CURVE, "max_unbooked": 10},
    "curve-no-gate": {**CURVE, "max_unbooked": 0},
    # Not a candidate: random multiples of the list price, never under 1.3 x the typical fee, to fit the win curve from.
    "explore": {**GATE_10, "floor": 1.3, "explore": [1.1, 2.4]},
}
