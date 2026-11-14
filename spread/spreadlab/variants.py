"""Named variants: each changes some of the policy's parameters (policy.DEFAULTS). Add one here to
compare it with the others on the same seeds."""
from __future__ import annotations

GATE_10 = {"same_day": True, "floor": 1.7, "quote_share": 1, "max_unbooked": 10}  # `gate-10`
# `curve-live-surcharge`: the win curve sets the price, the day's answers correct it, and the backlog raises the cost
CURVE = {"same_day": True, "quote_share": 1, "floor": 0, "curve": True, "learn": 0.16, "max_unbooked": 15, "backlog_step": 0.04}
FEE = {**CURVE, "fee": 1.0, "cost": 1.2}  # `curve-fee-1.0-cost-1.2`: gigs open at the typical fee, and an order is taken to cost 1.2 x it
# `fee-cap-1.2-drop-cost-1.3`: the fee rises a tenth of the typical fee an hour to 1.2 x it and holds, starts again after a drop, and an order is taken to cost 1.3 x it
CAPPED = {**FEE, "fee_cap": 1.2, "drop_fee": 1.1, "cost": 1.3}
# The reference, `steep-notes-offers-8`: the curve fitted with a level for each day, the note read before the first posting,
# and direct offers for the open gigs whose order must be collected within 8 hours
REFERENCE = {**CAPPED, "model": "day", "read_notes": True, "offer_hours": 8}

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
    # The cost follows the order, and the dealer's later prices count in it.
    "curve-order-cost": {**CURVE, "cost_by_order": True},
    "curve-trust-0.3": {**CURVE, "trust_value": 0.3},
    "curve-trust-1": {**CURVE, "trust_value": 1},
    "curve-order-cost-trust-0.3": {**CURVE, "cost_by_order": True, "trust_value": 0.3},
    "curve-order-cost-trust-1": {**CURVE, "cost_by_order": True, "trust_value": 1},
    # The opening driver fee (the schedule still rises 10% of it an hour), and the requests that the desk has never quoted.
    "curve-fee-0.9": {**CURVE, "fee": 0.9},
    "curve-fee-1.0": {**CURVE, "fee": 1.0},
    "curve-fee-1.1": {**CURVE, "fee": 1.1},
    "curve-fee-1.3": {**CURVE, "fee": 1.3},
    "curve-private": {**CURVE, "private": True},
    "curve-trade-in": {**CURVE, "trade_in": True},
    # Around the opening fee of 1.0: what an order is then taken to cost, the backlog rules, and private addresses.
    "curve-fee-0.8": {**CURVE, "fee": 0.8},
    "curve-fee-0.9-cost-1.2": {**CURVE, "fee": 0.9, "cost": 1.2},
    "curve-fee-1.0-cost-1.2": {**CURVE, "fee": 1.0, "cost": 1.2},
    "curve-fee-1.0-cost-1.3": {**CURVE, "fee": 1.0, "cost": 1.3},
    "curve-fee-1.0-gate-25": {**CURVE, "fee": 1.0, "max_unbooked": 25},
    "curve-fee-1.0-step-2": {**CURVE, "fee": 1.0, "backlog_step": 0.02},
    "curve-fee-1.0-private": {**CURVE, "fee": 1.0, "private": True},
    # The fees after the opening, from the opening fee of 1.0 and the cost of 1.2. After a drop the fees start again;
    # the rises stop at 1.2 x the typical fee, or there are none; one early step to 1.5 when drivers plan the day.
    "fee-drop": {**FEE, "drop_fee": 1.1},
    "fee-cap-1.2": {**FEE, "fee_cap": 1.2},
    "fee-flat": {**FEE, "fee_cap": 1.0},
    "fee-cap-1.2-jump": {**FEE, "fee_cap": 1.2, "jump": 1.5},
    "fee-flat-jump": {**FEE, "fee_cap": 1.0, "jump": 1.5},
    "fee-cap-1.2-drop": {**FEE, "fee_cap": 1.2, "drop_fee": 1.1},
    "fee-cap-1.2-drop-jump": {**FEE, "fee_cap": 1.2, "drop_fee": 1.1, "jump": 1.5},
    "fee-cap-1.2-drop-cost-1.3": CAPPED,
    # The fees and the cost follow the lane's usual fee in place of the request's typical fee.
    "fee-lane": {**FEE, "lane_fee": True},
    "fee-lane-1.05": {**FEE, "lane_fee": True, "fee": 1.05},
    # On `fee-cap-1.2-drop-cost-1.3`. The curve fitted with a level for each day, which is steeper.
    "steep": {**CAPPED, "model": "day"},
    "steep-cost-1.2": {**CAPPED, "model": "day", "cost": 1.2},
    "steep-learn-0.14": {**CAPPED, "model": "day", "learn": 0.14},
    # The note is read before the first posting.
    "notes": {**CAPPED, "read_notes": True},
    # Drives of over 400 minutes are 4% of the orders and a fifth of the late ones: decline them, or open them at 1.5 x and count 1.7 x as their cost.
    "long-decline": {**CAPPED, "max_drive": 400},
    "long-1.5": {**CAPPED, "long_drive": 400, "long_fee": 1.5, "long_cost": 1.7},
    # A lower opening fee where 100 or more drivers are notified of the pickup, and a higher one elsewhere.
    "deep-0.9": {**CAPPED, "deep_drivers": 100, "deep_fee": 0.9},
    "deep-0.9-thin-1.05": {**CAPPED, "deep_drivers": 100, "deep_fee": 0.9, "fee": 1.05},
    "steep-notes": {**CAPPED, "model": "day", "read_notes": True},
    # Direct offers at 1.3 x the typical fee for the open gigs whose order must be collected within 8 hours, or 24.
    "offers-8": {**CAPPED, "offer_hours": 8},
    "offers-24": {**CAPPED, "offer_hours": 24},
    "offers-8-1.5": {**CAPPED, "offer_hours": 8, "offer_fee": 1.5},
    "notes-offers-8": {**CAPPED, "read_notes": True, "offer_hours": 8},
    "notes-offers-24": {**CAPPED, "read_notes": True, "offer_hours": 24},
    "steep-notes-offers-8": REFERENCE,
    "steep-notes-offers-24": {**CAPPED, "model": "day", "read_notes": True, "offer_hours": 24},
    # The steeper curve wins about 20 orders a week more: a higher cost in the quote gives some of them back for on-time share.
    "steep-notes-offers-8-cost-1.4": {**CAPPED, "model": "day", "read_notes": True, "offer_hours": 8, "cost": 1.4},
    # Insurance for the 90% rule: while the projected on-time share is under 92% or 93%, once 40 orders are won, the desk
    # quotes no `same_day`, opens gigs at 1.2 x and takes an order to cost 1.6 x. A week where it never applies is unchanged.
    "steep-notes-offers-8-guard-92": {**CAPPED, "model": "day", "read_notes": True, "offer_hours": 8, "min_on_time": 0.92, "behind_from": 40,
                                      "when_behind": {"same_day": False, "fee": 1.2, "cost": 1.6}},
    "steep-notes-offers-8-guard-93": {**CAPPED, "model": "day", "read_notes": True, "offer_hours": 8, "min_on_time": 0.93, "behind_from": 40,
                                      "when_behind": {"same_day": False, "fee": 1.2, "cost": 1.6}},
    # A week with a short driver list has more late orders: under 720 drivers, gigs open at 1.2 x and an order is taken to cost 1.5 x.
    "tight-720": {**CAPPED, "tight_drivers": 720, "when_tight": {"fee": 1.2, "cost": 1.5}},
    "tight-720-mild": {**CAPPED, "tight_drivers": 720, "when_tight": {"fee": 1.1, "cost": 1.4}},
    # While the projected on-time share is under 94% or 95%, once 30 orders are won: gigs open at 1.2 x and an order is taken to cost 1.5 x.
    "guard-94": {**CAPPED, "min_on_time": 0.94, "behind_from": 30, "when_behind": {"fee": 1.2, "cost": 1.5}},
    "guard-95": {**CAPPED, "min_on_time": 0.95, "behind_from": 30, "when_behind": {"fee": 1.2, "cost": 1.5}},
    # Not a candidate: random multiples of the list price, never under 1.3 x the typical fee, to fit the win curve from.
    "explore": {**GATE_10, "floor": 1.3, "explore": [1.1, 2.4]},
}
