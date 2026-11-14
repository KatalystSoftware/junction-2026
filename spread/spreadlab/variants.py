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
# `cost_hours`: what an order costs by the hours from the answer to the last minute to collect the car. Over the reference's
# weeks an order with under 6 hours costs 1.27 x its typical fee with refunds and 15% are late; with 12 or more, 1.11 x and 2 to 4%.
HOURS = [[6, 1.55], [8, 1.35], [12, 1.3], [30, 1.2]]

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
    # Requests with a private address, which the desk has declined so far, at a cost of their own.
    "private-1.5": {**REFERENCE, "private": True, "private_cost": 1.5},
    "private-1.7": {**REFERENCE, "private": True, "private_cost": 1.7},
    # Not a candidate: random prices for the requests with a private address and with two cars, which no curve has answers for.
    "learn-kinds": {**REFERENCE, "explore_private": [1.1, 2.4], "explore_trade_in": [1.0, 2.0]},
    # The same with what the first batch showed: a trade-in's new car is due in the customer's slot, and drivers ask more for
    # a private pickup (paid 1.35 x) and for a trade-in (paid 1.6 x) than their typical fee.
    "learn-kinds-2": {**REFERENCE, "explore_private": [1.1, 2.0], "explore_trade_in": [1.0, 1.8],
                      "kinds": {"private_pickup": {"fee": 1.2}, "trade_in": {"fee": 1.4}}},
    # One-car requests with a private delivery, by the learning weeks: drivers are paid 1.15 x the typical fee and 9.5% are
    # late, so the cost is 1.3 x or 1.4 x; dealers buy a little more readily than the curve says.
    "delivery-1.3": {**REFERENCE, "kinds": {"private_delivery": {"cost": 1.3, "odds": 0.37}}},
    "delivery-1.4": {**REFERENCE, "kinds": {"private_delivery": {"cost": 1.4, "odds": 0.37}}},
    # The time to find a driver. Under the reference 13% of the orders won with 5 to 6 hours of it are late, 7.6% of
    # those with 6 to 8 hours and 3% of the rest; `min_slack` is 5 hours there.
    "slack-6": {**REFERENCE, "min_slack": 360},
    "slack-7": {**REFERENCE, "min_slack": 420},
    "slack-8": {**REFERENCE, "min_slack": 480},
    # The menu. At one multiple of the list price dealers take `same_day` 6 times in 7, and those orders are late most
    # often (5.6% against 3.3% for `next_day`). A dearer `same_day` leaves the choice to the dealer.
    "same-day-5": {**REFERENCE, "same_day_extra": 0.05},
    "same-day-10": {**REFERENCE, "same_day_extra": 0.10},
    # The backlog surcharge and gate were set when gigs opened at 1.2 x. Over the reference's weeks the surcharge
    # averages 0.20 x the typical fee, so orders are priced as if they cost 1.5 x.
    "step-2": {**REFERENCE, "backlog_step": 0.02},
    "step-2-gate-25": {**REFERENCE, "backlog_step": 0.02, "max_unbooked": 25},
    # The surcharge counts only the cars to collect within 24 hours: the others do not predict a late order.
    "due-24-gate-25": {**REFERENCE, "backlog_hours": 24, "max_unbooked": 25},
    # The same surcharge with the reference's gate, or a gate of 20: in a hard week the gate of 15 declines over 100
    # requests, and with 25 that week ends under 90% on time.
    "due-24": {**REFERENCE, "backlog_hours": 24},
    "due-24-gate-20": {**REFERENCE, "backlog_hours": 24, "max_unbooked": 20},
    # Insurance for the weeks with a short driver list, where the reference's lowest weeks are (90.1% on 100 weeks):
    # a dearer cost in the quote, an hour more to find a driver, or both, in those weeks only.
    "thin-cost-1.4": {**REFERENCE, "tight_drivers": 720, "when_tight": {"cost": 1.4}},
    "thin-slack-6": {**REFERENCE, "tight_drivers": 720, "when_tight": {"min_slack": 360}},
    "thin-cost-1.4-slack-6": {**REFERENCE, "tight_drivers": 720, "when_tight": {"cost": 1.4, "min_slack": 360}},
    # The same, except in a week with a short driver list, which keeps the reference's surcharge and gate: with the wider
    # gate every week under 92.2% on time on the tune and holdout seeds had 733 drivers or fewer.
    "due-24-gate-25-tight-750": {**REFERENCE, "backlog_hours": 24, "max_unbooked": 25, "tight_drivers": 750, "when_tight": {"backlog_hours": 0, "max_unbooked": 15}},
    "step-2-gate-25-tight-750": {**REFERENCE, "backlog_step": 0.02, "max_unbooked": 25, "tight_drivers": 750, "when_tight": {"backlog_step": 0.04, "max_unbooked": 15}},
    # The cost follows the hours to find a driver, and `cost` 1.15 is for the orders with 30 or more.
    "hours": {**REFERENCE, "cost_hours": HOURS, "cost": 1.15},
    "hours-step-2-gate-25": {**REFERENCE, "cost_hours": HOURS, "cost": 1.15, "backlog_step": 0.02, "max_unbooked": 25},
    "hours-due-24-gate-25": {**REFERENCE, "cost_hours": HOURS, "cost": 1.15, "backlog_hours": 24, "max_unbooked": 25},
    "hours-due-24-gate-25-premium": {**REFERENCE, "cost_hours": HOURS, "cost": 1.15, "backlog_hours": 24, "max_unbooked": 25, "premium_cost": 0.15},
    # The day's correction of the curve, and on top of it one for the pickup town that starts again each morning.
    "pickup-0.10": {**REFERENCE, "learn_pickup": 0.10},
    # A week with a short driver list has more late orders: under 720 drivers, gigs open at 1.2 x and an order is taken to cost 1.5 x.
    "tight-720": {**CAPPED, "tight_drivers": 720, "when_tight": {"fee": 1.2, "cost": 1.5}},
    "tight-720-mild": {**CAPPED, "tight_drivers": 720, "when_tight": {"fee": 1.1, "cost": 1.4}},
    # While the projected on-time share is under 94% or 95%, once 30 orders are won: gigs open at 1.2 x and an order is taken to cost 1.5 x.
    "guard-94": {**CAPPED, "min_on_time": 0.94, "behind_from": 30, "when_behind": {"fee": 1.2, "cost": 1.5}},
    "guard-95": {**CAPPED, "min_on_time": 0.95, "behind_from": 30, "when_behind": {"fee": 1.2, "cost": 1.5}},
    # Not a candidate: random multiples of the list price, never under 1.3 x the typical fee, to fit the win curve from.
    "explore": {**GATE_10, "floor": 1.3, "explore": [1.1, 2.4]},
}
