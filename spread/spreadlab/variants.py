"""Named variants: each changes some of the policy's parameters (policy.DEFAULTS). Add one here to
compare it with the others on the same seeds."""
from __future__ import annotations

from . import exposure, late_wide, pairs, thin_play

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

# `slow_bar`: the highest chance of a late order that the desk still quotes, by the won cars without a driver.
BAR_15 = [[4, 0.15], [7, 0.10], [10, 0.06], [12, 0.04]]
BAR_25 = [[5, 0.15], [9, 0.10], [13, 0.06], [17, 0.04], [21, 0.03]]
# Once 8 won cars have no driver, the open gigs whose order must be collected within 24 hours show 1.4 x the typical fee at once.
PUSH = {"push_from": 8, "push_hours": 24, "push_fee": 1.4}
KINDS = {"private_pickup": {"cost": 1.6, "odds": 0.06}, "private_delivery": {"cost": 1.3, "odds": 0.37}, "trade_in": {"cost": 2.3, "fee": 1.4, "odds": 0.27}}
# `fee_rules`: [drivers from, under, hours from, under, opening fee, rise an hour, top fee]. Few drivers and little time: open higher
# and rise faster. Many drivers and over a day: open lower and rise slower. The others keep 1.0, 0.1 an hour, 1.2.
SEARCH_16 = {"cost": 1.2210258222821198, "late_cost": 25.623005665608154, "backlog_step": 0.02226666084178632, "slow_step": 0.8001968330379229, "backlog_hours": 24,
             "max_unbooked": 40, "fee": 0.9773051520962659, "fee_cap": 1.2852313870434833, "fee_rules": [[0, 10 ** 6, 0, 8, 1.0465927457594313, 0.1, 1.4852313870434832]]}
FEES_THIN = [[0, 40, 0, 8, 1.2, 0.2, 1.6], [0, 40, 8, 24, 1.1, 0.1, 1.4]]
FEES_DEEP = [[100, 10 ** 6, 24, 10 ** 6, 0.9, 0.05, 1.2]]

# Merge 1 of the lanes, `fee16-80-q24-wide-pairs-0.6-return-0.75`: the base that lane 2's knobs change one at a time.
VARIANTS_MERGE1 = {**REFERENCE, "backlog_step": 0, "slow_step": 0.8, "max_unbooked": 25, "slow_model": "friday", "cost": 1.2, "late_cost": 150,
                   "kinds": KINDS, "note_limits": True, "fee_rules": [[0, 10 ** 6, 16, 10 ** 6, 0.8, 0.1, 1.2]], "queue_hours": 24, "late_wide": True,
                   "late_wide_version": late_wide.VERSION, "pair_hold": 4, "pair_fee": 0.6, "pair_cost": 0.75, "pair_version": pairs.VERSION}

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
    # The gate is what protects a hard week: a tighter one in the weeks with a short driver list, alone and with the dearer quote.
    "thin-gate-10": {**REFERENCE, "tight_drivers": 720, "when_tight": {"max_unbooked": 10}},
    "thin-cost-1.4-gate-10": {**REFERENCE, "tight_drivers": 720, "when_tight": {"cost": 1.4, "max_unbooked": 10}},
    # Where the late orders of those weeks are: premium cars (12 a week, 17% late, only experienced drivers may take
    # them) and orders with under 6 hours to find a driver. A dearer premium car there, alone and with the extra hour.
    "thin-premium-0.4": {**REFERENCE, "tight_drivers": 720, "when_tight": {"premium_cost": 0.4}},
    "thin-premium-0.4-slack-6": {**REFERENCE, "tight_drivers": 720, "when_tight": {"premium_cost": 0.4, "min_slack": 360}},
    # The same dearer quote in the weeks with under 680 drivers only: on 197 weeks with under 720 it removes weeks near
    # the 90% rule under 680 for about 100 a week, and costs 400 a week for nothing at 680 to 719.
    "thin-680-cost-1.4": {**REFERENCE, "tight_drivers": 680, "when_tight": {"cost": 1.4}},
    # The dearer premium car in every week.
    "premium-0.4": {**REFERENCE, "premium_cost": 0.4},
    # Both: the dearer premium car in every week, and the extra hour in a week with under 720 drivers. In such a week it
    # plays as `thin-premium-0.4-slack-6`, in the others as `premium-0.4`.
    "premium-0.4-thin-slack-6": {**REFERENCE, "premium_cost": 0.4, "tight_drivers": 720, "when_tight": {"min_slack": 360}},
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
    # The declined kinds priced by the curve at their own cost, at or above what the learning weeks measured, so that a win
    # is expected to pay: a private pickup paid drivers 1.35 x the typical fee at the reference's opening and 9% were
    # late; a trade-in opened at 1.4 x paid 1.84 x and 26% were late. `odds` is what the curve was off by for the kind.
    "pickup-1.6": {**REFERENCE, "kinds": {"private_pickup": {"cost": 1.6, "odds": 0.06}}},
    "pickup-1.8": {**REFERENCE, "kinds": {"private_pickup": {"cost": 1.8, "odds": 0.06}}},
    "trade-in-1.9": {**REFERENCE, "kinds": {"trade_in": {"cost": 1.9, "fee": 1.4, "odds": 0.27}}},
    "trade-in-2.1": {**REFERENCE, "kinds": {"trade_in": {"cost": 2.1, "fee": 1.4, "odds": 0.27}}},
    "trade-in-2.3": {**REFERENCE, "kinds": {"trade_in": {"cost": 2.3, "fee": 1.4, "odds": 0.27}}},
    # Keeping slow cars out of the backlog. `slow.py` gives the chance that a request's order arrives late; 46% of won orders are
    # at or under 3%, 75% under 6%, 88% under 10% and 94% under 15%. The bar for a new car falls as the backlog fills, so the gate
    # at the end of it is rarely reached.
    "bar": {**REFERENCE, "slow_bar": BAR_15},
    "bar-gate-25": {**REFERENCE, "slow_bar": BAR_25, "max_unbooked": 25},
    "bar-push": {**REFERENCE, "slow_bar": BAR_15, **PUSH},
    "bar-gate-25-push": {**REFERENCE, "slow_bar": BAR_25, "max_unbooked": 25, **PUSH},
    # The backlog's surcharge by the car: 0.8 x its chance of a late order for each waiting car, which is the reference's 0.04 at the mean chance of 5%.
    "slow-step": {**REFERENCE, "backlog_step": 0, "slow_step": 0.8},
    "slow-step-gate-25": {**REFERENCE, "backlog_step": 0, "slow_step": 0.8, "max_unbooked": 25},
    "slow-step-gate-40": {**REFERENCE, "backlog_step": 0, "slow_step": 0.8, "max_unbooked": 40},
    "slow-step-1.2-gate-25": {**REFERENCE, "backlog_step": 0, "slow_step": 1.2, "max_unbooked": 25},
    # ... with the late chance that knows Friday's deadlines: `slow-step-gate-25` ended one week at 90.9% with 9 of 20 Friday orders late.
    "slow-step-gate-25-friday": {**REFERENCE, "backlog_step": 0, "slow_step": 0.8, "max_unbooked": 25, "slow_model": "friday"},
    # ... and with lateness in every quote's cost, not only while cars wait: 150 euros x the late chance, and 1.2 x the typical fee for the rest.
    "slow-step-gate-25-late-150": {**REFERENCE, "backlog_step": 0, "slow_step": 0.8, "max_unbooked": 25, "cost": 1.2, "late_cost": 150},
    "slow-step-gate-25-friday-late-150": {**REFERENCE, "backlog_step": 0, "slow_step": 0.8, "max_unbooked": 25, "slow_model": "friday", "cost": 1.2, "late_cost": 150},
    # ... with the kinds the desk declines, each at a cost of its own: their wins paid, and the dealer orders that the gate then declined took it back.
    "slow-step-gate-25-kinds": {**REFERENCE, "backlog_step": 0, "slow_step": 0.8, "max_unbooked": 25, "kinds": KINDS},
    # Direct offers at the posting to 3 drivers who live within 30 km of where the car is going, then to the next 3: of the drivers who
    # look at a gig, those book 30% of the time against 4 to 10% for the others, and the app does not notify them.
    "home-0.8": {**REFERENCE, "home_offers": 3, "home_km": 30, "home_rounds": 2, "home_fee": 0.8},
    "home-0.9": {**REFERENCE, "home_offers": 3, "home_km": 30, "home_rounds": 2, "home_fee": 0.9},
    "home-1.0": {**REFERENCE, "home_offers": 3, "home_km": 30, "home_rounds": 2, "home_fee": 1.0},
    # The late chance in the cost from a fixed point of the week on: from the Nth won order, 400 euros (or 200, 800) x the chance.
    # Nothing the desk sees on Monday marks a hard week, so this is what an insurance that starts on Tuesday or Wednesday still recovers.
    **{f"rescue-{n}-{euros}": {**REFERENCE, "min_on_time": 0.999, "behind_from": n, "when_behind": {"late_cost": euros}}
       for n, euros in ((1, 400), (100, 400), (150, 400), (150, 200), (150, 800))},
    # ... and the row they are read against: the late chance in every quote in place of part of the flat cost.
    "late-225-cost-1.19": {**REFERENCE, "cost": 1.19, "late_cost": 225},
    # The note's own deadline and the site hours it gives, at the quote and in the posting (notes.limits): closed pickups, waits at a
    # delivery site and orders late only by the note's deadline cost the reference about 126 euros and 0.8 late orders a week.
    "notes-limits": {**REFERENCE, "note_limits": True},
    # The risk-priced backlog with the declined kinds and the note's limits: the three changes that each held alone.
    "slow-step-gate-25-kinds-limits": {**REFERENCE, "backlog_step": 0, "slow_step": 0.8, "max_unbooked": 25, "kinds": KINDS, "note_limits": True},
    # ... and with lateness in every quote and the late chance that knows Friday's deadlines (`slow-step-gate-25-friday-late-150`).
    "slow-friday-late-150-kinds-limits": {**REFERENCE, "backlog_step": 0, "slow_step": 0.8, "max_unbooked": 25, "slow_model": "friday", "cost": 1.2, "late_cost": 150,
                                          "kinds": KINDS, "note_limits": True},
    # ... with the note fallback (fallback.py, played by fallback.ActionDesk): on a won note that the rules are unsure of, a model
    # picks cited posting actions. "note_actions" is fallback.VERSION: raise both on each change of the prompt, the checks or the
    # model, so the fingerprint follows. The second also acts on an earlier deadline and on haste, which cost margin when wrong.
    **{name: {**REFERENCE, "backlog_step": 0, "slow_step": 0.8, "max_unbooked": 25, "slow_model": "friday", "cost": 1.2, "late_cost": 150,
              "kinds": KINDS, "note_limits": True, "note_actions": 4, **extra}
       for name, extra in (("slow-friday-late-150-kinds-limits-actions", {}),
                           ("slow-friday-late-150-kinds-limits-actions-risky", {"note_actions_risky": ["deadline", "urgent"]}))},
    # An internal on-time target in place of the fixed buffer. Lateness is priced at what a late order costs (refund 46 and
    # dealer trust 36, scratch/opt/calibrate.py), the waiting-car surcharge is halved and the gate is 40, so the desk quotes
    # lower than the candidate. While the projected on-time share is under the target, once 40 orders are won, it quotes as
    # the candidate with the 90% rule's price on and a gate of 12. Only new quotes change: won orders are posted as always.
    **{f"target-{t}": {**REFERENCE, "backlog_step": 0, "slow_step": 0.4, "max_unbooked": 40, "slow_model": "friday", "cost": 1.2, "late_cost": 85,
                       "kinds": KINDS, "note_limits": True, "min_on_time": t / 100, "behind_from": 40,
                       "when_behind": {"late_cost": 150, "slow_step": 0.8, "max_unbooked": 12, "rule_cost": 800}}
       for t in (85, 87, 89, 91, 93)},
    # ... with the day-ahead snow forecast. An order with snow forecast at its pickup or delivery place, for hours between its first
    # pickup minute and its deadline, is late about twice as often as the late chance says (0.64 to 0.92 more log odds by variant,
    # scratch/snow_report.py): 14 such orders a week, 0.6 more late. Its late chance takes 0.7 more log odds, which `late_cost`
    # and `slow_step` then price; with `snow_fee` its gigs also pay 1.2 x the usual schedule, since 60% of the late ones are booked
    # only after the snow has started.
    "slow-friday-late-150-kinds-limits-snow": {**REFERENCE, "backlog_step": 0, "slow_step": 0.8, "max_unbooked": 25, "slow_model": "friday", "cost": 1.2,
                                               "late_cost": 150, "kinds": KINDS, "note_limits": True, "snow_odds": 0.7},
    "slow-friday-late-150-kinds-limits-snow-fee-1.2": {**REFERENCE, "backlog_step": 0, "slow_step": 0.8, "max_unbooked": 25, "slow_model": "friday", "cost": 1.2,
                                                       "late_cost": 150, "kinds": KINDS, "note_limits": True, "snow_odds": 0.7, "snow_fee": 1.2},
    # The live default with an offset for each dealer in the day's correction of the curve (dealer.py): Monday's prior sd 0.015 and a drift of 0.02 a day,
    # among the best on the tune weeks' log loss (scratch/dealer_filter.py). Worth 12 to 26 a week in the closed-loop replay (scratch/dealer_sim.py); see the README.
    "slow-friday-late-150-kinds-limits-dealer": {**REFERENCE, "backlog_step": 0, "slow_step": 0.8, "max_unbooked": 25, "slow_model": "friday", "cost": 1.2,
                                                 "late_cost": 150, "kinds": KINDS, "note_limits": True, "dealer_sd": 0.015, "dealer_drift": 0.02, "dealer_version": 1},
    # The live default with out-and-back pairs (pairs.py): a won car with 16 hours or more to its last pickup, on a lane with 8 or more
    # return requests a week, waits up to 4 hours for a return, and the two cars go as one gig that opens at 0.6, 0.7 or 0.8 x their two
    # typical fees and rises to 1.0 x. `-return-0.75` also quotes a request that can go back with a held car at a cost of 0.75 in place of 1.2.
    **{f"slow-friday-late-150-kinds-limits-pairs-{fee}{tail}": {
        **REFERENCE, "backlog_step": 0, "slow_step": 0.8, "max_unbooked": 25, "slow_model": "friday", "cost": 1.2, "late_cost": 150, "kinds": KINDS,
        "note_limits": True, "pair_hold": 4, "pair_fee": fee, "pair_cost": cost, "pair_version": pairs.VERSION}
       for fee in (0.6, 0.7, 0.8) for tail, cost in (("", 0), ("-return-0.75", 0.75))},
    # Track B's first distillation of the qualifying track's candidate: the live default with the fee ladder for cars with 16 hours
    # or more to their last pickup (0.9 x, rising 0.1 an hour to 1.2 x), the wide late chance (late_wide.py), pairs at 0.6 and the
    # return quote at 0.75. Not the track's 0.8 opening, its 24-hour waiting-car count or its outage split.
    "fee16-wide-pairs-0.6-return-0.75": {
        **REFERENCE, "backlog_step": 0, "slow_step": 0.8, "max_unbooked": 25, "slow_model": "friday", "cost": 1.2, "late_cost": 150, "kinds": KINDS,
        "note_limits": True, "fee_rules": [[0, 10 ** 6, 16, 10 ** 6, 0.9, 0.1, 1.2]], "late_wide": True, "late_wide_version": late_wide.VERSION,
        "pair_hold": 4, "pair_fee": 0.6, "pair_cost": 0.75, "pair_version": pairs.VERSION},
    # ... with `queue_hours`: the waiting-car surcharge and the gate of 25 count only the cars due within that many hours. A car
    # that opens cheap and waits a day for its driver is no risk to the week. A ladder on the first distillation's 0.9 opening,
    # from the full count (the first distillation itself) through 48, 36 and 24 hours to 12, past the qualifying track's 24; and
    # 24 hours with the track's 0.8 opening (Track B's second distillation: its candidate without the outage split). On the ladder's
    # 40 weeks 12 hours won about 10 more orders a week than 24 at the 0.9 opening, for +207 a week; `fee16-80-q12-...` tries
    # that window on merge 1's 0.8 opening.
    **{f"fee16{tail}-q{hours}-wide-pairs-0.6-return-0.75": {
        **REFERENCE, "backlog_step": 0, "slow_step": 0.8, "max_unbooked": 25, "slow_model": "friday", "cost": 1.2, "late_cost": 150, "kinds": KINDS,
        "note_limits": True, "fee_rules": [[0, 10 ** 6, 16, 10 ** 6, opening, 0.1, 1.2]], "queue_hours": hours, "late_wide": True,
        "late_wide_version": late_wide.VERSION, "pair_hold": 4, "pair_fee": 0.6, "pair_cost": 0.75, "pair_version": pairs.VERSION}
       for tail, opening, hours in (("", 0.9, 12), ("", 0.9, 24), ("", 0.9, 36), ("", 0.9, 48), ("-80", 0.8, 24), ("-80", 0.8, 12))},
    # Lane 2, pairing and combining cars: one knob at a time on merge 1, `fee16-80-q24-wide-pairs-0.6-return-0.75`. Pair ends within
    # 45 km, not 30 (`pair_km`); a won return also pairs with a car whose own gig is still open and unbooked, which is withdrawn first
    # (`pair_open`); a held car also goes with a car collected near its delivery place, wherever that one goes, at 0.8 x the two
    # typical fees (`pair_onward`); holds on lanes with 4 or more return requests a week, not 8; holds for cars with 12 hours or
    # more, not 16; the return quoted at a cost of 0.6, not 0.75.
    **{f"l2-{tail}": {**VARIANTS_MERGE1, **extra}
       for tail, extra in (("km45", {"pair_km": 45}), ("open", {"pair_open": True}), ("onward", {"pair_onward": 0.8}),
                           ("traffic4", {"pair_traffic": 4}), ("slack12", {"pair_slack": 12}), ("cost06", {"pair_cost": 0.6}),
                           ("open-onward", {"pair_open": True, "pair_onward": 0.8}),
                           # ... and onward pairs only at a held car's release, so a return that comes later still takes it (`pair_late`)
                           ("onward-late", {"pair_onward": 0.8, "pair_late": True}),
                           ("open-onward-late", {"pair_open": True, "pair_onward": 0.8, "pair_late": True}),
                           # ... and a request whose car can go onward with a held car quoted at 0.9 or 1.0 of its typical fee, not
                           # 1.2; once won its car waits for that held car's release (`pair_onward_cost`): more orders won
                           ("open-onward-late-q09", {"pair_open": True, "pair_onward": 0.8, "pair_late": True, "pair_onward_cost": 0.9}),
                           ("open-onward-late-q10", {"pair_open": True, "pair_onward": 0.8, "pair_late": True, "pair_onward_cost": 1.0}),
                           # ... only in weeks with 760 or more drivers listed, where merge 1's exam had no week under 92%
                           ("open-onward-late-q10-d760", {"pair_open": True, "pair_onward": 0.8, "pair_late": True, "pair_onward_cost": 1.0,
                                                          "pair_onward_drivers": 760}))},
    # ... the same without the note's limits, whose posting changed after its weeks were played.
    "slow-friday-late-150-kinds": {**REFERENCE, "backlog_step": 0, "slow_step": 0.8, "max_unbooked": 25, "slow_model": "friday", "cost": 1.2, "late_cost": 150, "kinds": KINDS},
    # The best point of the search over these parameters together (scratch/search.py, trial 16 of 20, on 30 tune seeds), and with the kinds.
    "search-16": {**REFERENCE, **SEARCH_16},
    "search-16-kinds": {**REFERENCE, **SEARCH_16, "kinds": KINDS},
    # The fees by the drivers notified of the pickup and the hours left to collect the car.
    "fees-thin": {**REFERENCE, "fee_rules": FEES_THIN},
    "fees-deep": {**REFERENCE, "fee_rules": FEES_DEEP},
    "fees-supply": {**REFERENCE, "fee_rules": FEES_THIN + FEES_DEEP},
    "bar-gate-25-push-fees": {**REFERENCE, "slow_bar": BAR_25, "max_unbooked": 25, **PUSH, "fee_rules": FEES_THIN + FEES_DEEP},
    # The day's correction of the curve, and on top of it one for the pickup town that starts again each morning.
    "pickup-0.10": {**REFERENCE, "learn_pickup": 0.10},
    # A week with a short driver list has more late orders: under 720 drivers, gigs open at 1.2 x and an order is taken to cost 1.5 x.
    "tight-720": {**CAPPED, "tight_drivers": 720, "when_tight": {"fee": 1.2, "cost": 1.5}},
    "tight-720-mild": {**CAPPED, "tight_drivers": 720, "when_tight": {"fee": 1.1, "cost": 1.4}},
    # While the projected on-time share is under 94% or 95%, once 30 orders are won: gigs open at 1.2 x and an order is taken to cost 1.5 x.
    "guard-94": {**CAPPED, "min_on_time": 0.94, "behind_from": 30, "when_behind": {"fee": 1.2, "cost": 1.5}},
    "guard-95": {**CAPPED, "min_on_time": 0.95, "behind_from": 30, "when_behind": {"fee": 1.2, "cost": 1.5}},
    # The quote as an optimisation (optquote.py), with the reference's fees, notes and offers, no backlog surcharge and a
    # gate of 25. `opt_mu` prices a driver's time in typical fees for each order won, and `opt_lambda` the 90% rule in euros.
    "opt-mu-0": {**REFERENCE, "opt": True, "backlog_step": 0, "max_unbooked": 25},
    "opt-mu-0.1": {**REFERENCE, "opt": True, "opt_mu": 0.1, "backlog_step": 0, "max_unbooked": 25},
    "opt-mu-0.2": {**REFERENCE, "opt": True, "opt_mu": 0.2, "backlog_step": 0, "max_unbooked": 25},
    "opt-mu-0.3": {**REFERENCE, "opt": True, "opt_mu": 0.3, "backlog_step": 0, "max_unbooked": 25},
    "opt-mu-0.4": {**REFERENCE, "opt": True, "opt_mu": 0.4, "backlog_step": 0, "max_unbooked": 25},
    "opt-mu-0.3-lambda-100": {**REFERENCE, "opt": True, "opt_mu": 0.3, "opt_lambda": 100, "backlog_step": 0, "max_unbooked": 25},
    # A driver's time that rises with the backlog. With a constant `opt_mu`, `opt-mu-0.3-lambda-100` wins 60 orders a week
    # while 16 or more cars wait, 7.4% of them late, and ends one week in 30 under 90%. `slow_step` adds to `opt_mu`.
    "opt-mu-0.2-lambda-100-slow-step": {**REFERENCE, "opt": True, "opt_mu": 0.2, "opt_lambda": 100, "backlog_step": 0, "slow_step": 0.8, "max_unbooked": 25},
    # Not a candidate: random multiples of the list price, never under 1.3 x the typical fee, to fit the win curve from.
    "explore": {**GATE_10, "floor": 1.3, "explore": [1.1, 2.4]},
}

# Driver fees by each car's risk of ending late (riskfee.py), on the live default. A car with 16 hours or more to its last
# pickup and a late chance under 6% opens at 0.9 x the typical fee; a gig holds its opening fee until the car's late chance,
# with the hours left then, reaches 4%, and then rises a tenth of the typical fee an hour to 1.2 x. Each part alone, and the
# waiting cars counted only when due within 24 hours (strategy proposal 3).
_DEFAULT = VARIANTS["slow-friday-late-150-kinds-limits"]
VARIANTS.update({
    "risk-fees": {**_DEFAULT, "risk_fees": True},
    "risk-fees-due-24": {**_DEFAULT, "risk_fees": True, "risk_queue_hours": 24},
    "risk-fees-raise-0.06": {**_DEFAULT, "risk_fees": True, "risk_raise_late": 0.06},
    "risk-hold": {**_DEFAULT, "risk_fees": True, "risk_open": 1.0},
    # The same as `risk-fees` with safe cars opening at 0.95 x: in the offline screen (scratch/risk_screen.py) about half the
    # added late orders for two thirds of the fees saved.
    "risk-fees-open-0.95": {**_DEFAULT, "risk_fees": True, "risk_open": 0.95},
    "risk-open": {**_DEFAULT, "risk_fees": True, "risk_raise_late": 0},
    "risk-open-due-24": {**_DEFAULT, "risk_fees": True, "risk_raise_late": 0, "risk_queue_hours": 24},
})

# Merge 1 with every waiting car counted in a week whose driver list is short (`tight_drivers`, known before the first quote).
# Its 24-hour count lets the desk take orders while cars due later wait, and with few drivers those cars end late: all 7
# weeks of merge 1's first exam under 92% had 648 to 723 drivers, and counting all hours lifted its three thin weeks under
# 90% to 93 to 95%. 760 is slow.py's own reference for a full driver list. `-q48` counts the cars due within 48 hours.
_MERGE_1_BASE = VARIANTS["fee16-80-q24-wide-pairs-0.6-return-0.75"]
VARIANTS.update({
    "fee16-80-q24-wide-pairs-0.6-return-0.75-thin760-all": {**_MERGE_1_BASE, "tight_drivers": 760, "when_tight": {"queue_hours": 0}},
    "fee16-80-q24-wide-pairs-0.6-return-0.75-thin760-q48": {**_MERGE_1_BASE, "tight_drivers": 760, "when_tight": {"queue_hours": 48}},
})

# Lane 2 on the base `-thin760-all`: onward pairs at a held car's release, with open gigs, and the onward quote at 1.0, all only
# in weeks with 760 or more drivers (`pair_more_drivers`). A thinner week plays as the base to the cent.
VARIANTS["fee16-80-q24-wide-pairs-0.6-return-0.75-thin760-all-onward-q10-d760"] = {
    **VARIANTS["fee16-80-q24-wide-pairs-0.6-return-0.75-thin760-all"], "pair_open": True, "pair_onward": 0.8, "pair_late": True,
    "pair_onward_cost": 1.0, "pair_more_drivers": 760}

# ... with the waiting-car count of a week under 760 drivers over the cars due within 48 hours instead of all of them (the
# 48-hour arm of the thin seeds kept every week at 90% or more and made about 1,000 a week more there than all hours).
_MERGE_3 = VARIANTS["fee16-80-q24-wide-pairs-0.6-return-0.75-thin760-all-onward-q10-d760"]
VARIANTS["fee16-80-q24-wide-pairs-0.6-return-0.75-thin760-q48-onward-q10-d760"] = {
    **_MERGE_3, "when_tight": {**_MERGE_3["when_tight"], "queue_hours": 48}}

# The live default with a cap on the won orders to collect on one day (`due_cap`): a night's wave of dropped gigs then takes
# down at most that day's cap. An option due on a full day is not quoted; a slower one of the same request still is. The cap
# lifts for the rest of the week after the first night with 10 drops in its first hour (`due_cap_wave`).
VARIANTS.update({f"day-cap-{cap}": {**_DEFAULT, "due_cap": cap, "due_cap_wave": 10} for cap in (70, 80)})
# The live default with the quote's cost by the book's exposure to drops (exposure.py) in place of the waiting-car surcharge, the
# late cost, the Friday terms of the late chance and the day cap: €82 a late order that the order adds to the book, and kappa x
# the week's value x its change to the chance of a week under 90%. No quote while 40 cars wait (`-g25`: 25, as the default).
VARIANTS.update({f"exposure-k{k}{gate}": {**_DEFAULT, **exposure.REPLACES, "exposure": True, "exposure_kappa": k, "exposure_version": exposure.VERSION,
                                          "max_unbooked": 25 if gate else 40} for k in (1, 2, 4, 8) for gate in ("", "-g25")})
# ... and the charging stop of a low-charge electric car only where RULES.md needs it, on a route over 200 km.
VARIANTS["charge-200"] = {**_DEFAULT, "charge_km": 200}

# The late chance's surcharge for each waiting car at 0.4, not 0.8, only in a week with 760 drivers or more: there merge 1's
# exam had no week under 92%, and the stand-in climb (spread-climb) found it the one knob that gained beyond a tie, +622 and
# +897 a week on the natural worlds of its two halves with 16 to 18 more orders and 1.3 to 1.4 more late. A thinner week
# restores the base's value (`when_tight`), so it plays as the base to the cent. On `-thin760-all`, on `-thin760-q48` and on merge 3.
def _full_weeks(base: dict, **knobs) -> dict:
    from .policy import DEFAULTS
    return {**base, **knobs, "when_tight": {**{k: base.get(k, DEFAULTS[k]) for k in knobs}, **base["when_tight"]}}


VARIANTS["t760all-step04"] = _full_weeks(VARIANTS["fee16-80-q24-wide-pairs-0.6-return-0.75-thin760-all"], slow_step=0.4)
VARIANTS["t760-q48-step04"] = _full_weeks(VARIANTS["fee16-80-q24-wide-pairs-0.6-return-0.75-thin760-q48"], slow_step=0.4)
VARIANTS["t760all-onward-step04"] = _full_weeks(VARIANTS["fee16-80-q24-wide-pairs-0.6-return-0.75-thin760-all-onward-q10-d760"], slow_step=0.4)
# Lane A1: the two steps beyond merge 3 plus step04, each alone and only in a week of 760 or more drivers: `slow_step` 0.4 to
# 0.2, and `late_cost` 150 to 100 (with step04's 0.4). A thinner week plays t760all-onward-step04 exactly.
VARIANTS["s04-rich-ss02"] = _full_weeks(VARIANTS["t760all-onward-step04"], slow_step=0.2)
VARIANTS["s04-rich-late100"] = _full_weeks(VARIANTS["t760all-onward-step04"], late_cost=100)
# Track B's row 5 on `trackb-merged`: the climb's step04 on the 48-hour count under 760 drivers (row 4), only in a week of
# 760 or more drivers. A thinner week plays row 4 exactly; at 760 or more it is `t760all-onward-step04`.
_ROW_4 = VARIANTS["fee16-80-q24-wide-pairs-0.6-return-0.75-thin760-q48-onward-q10-d760"]
VARIANTS["fee16-80-q24-wide-pairs-0.6-return-0.75-thin760-q48-onward-q10-d760-ss04"] = _full_weeks(_ROW_4, slow_step=0.4)
# Track B's row 6: lane A1's `slow_step` 0.2 on row 5, in a week of 760 drivers or more; at 760 or more it equals
# `s04-rich-ss02` (f38b6eb3da93), under 760 row 4 exactly.
VARIANTS["fee16-80-q24-wide-pairs-0.6-return-0.75-thin760-q48-onward-q10-d760-ss02"] = _full_weeks(
    VARIANTS["fee16-80-q24-wide-pairs-0.6-return-0.75-thin760-q48-onward-q10-d760-ss04"], slow_step=0.2)
# Track B's aggressive line (`trackb-aggressive`), each row the newest safe row plus parts the safe line refuses for their
# on-time tail. Row A1: lane A1's `late_cost` 100 at 760 drivers or more on row 6, the rest of its held part.
VARIANTS["fee16-80-q24-wide-pairs-0.6-return-0.75-thin760-q48-onward-q10-d760-ss02-late100"] = _full_weeks(
    VARIANTS["fee16-80-q24-wide-pairs-0.6-return-0.75-thin760-q48-onward-q10-d760-ss02"], late_cost=100)
# Lane 4's day cap on row 6, only in a week under 760 drivers: no option is quoted whose last pickup falls on a day that already
# has 62 won orders still to deliver, and the cap never lifts after a drop wave (`due_cap_wave` 0). At 760 drivers or more it is
# row 6 exactly. Played as `-thin760-q48-cap62` (737e31c2ca1e, lane4-q48-cap bda78d1) on the 48-hour count's low thin weeks:
# fresh-8306 88.6% -> 95.2%, 36 -> 16 late orders, 13 more orders; no week pushed under 90%.
VARIANTS["fee16-80-q24-wide-pairs-0.6-return-0.75-thin760-q48-onward-q10-d760-ss02-cap62"] = {
    **VARIANTS["fee16-80-q24-wide-pairs-0.6-return-0.75-thin760-q48-onward-q10-d760-ss02"],
    "when_tight": {**VARIANTS["fee16-80-q24-wide-pairs-0.6-return-0.75-thin760-q48-onward-q10-d760-ss02"]["when_tight"],
                   "due_cap": 62, "due_cap_wave": 0}}
# The aggressive row A1 on safe row 7: the day cap under 760 drivers and `late_cost` 100 at 760 or more.
VARIANTS["fee16-80-q24-wide-pairs-0.6-return-0.75-thin760-q48-onward-q10-d760-ss02-cap62-late100"] = _full_weeks(
    VARIANTS["fee16-80-q24-wide-pairs-0.6-return-0.75-thin760-q48-onward-q10-d760-ss02-cap62"], late_cost=100)
# More rungs on the aggressive row A1.7 (`…-cap62-late100`), each only in a week of 760 drivers or more and row 7 below that:
# the climb's `agg-r-mild` (cost 1.15, the 12-hour count, the kinds quoted cheaper: trade-in 2.0, private pickup 1.4, private
# delivery 1.2) and lane 1 A's `agg-late100-cost10` (cost 1.0).
_A1_7 = VARIANTS["fee16-80-q24-wide-pairs-0.6-return-0.75-thin760-q48-onward-q10-d760-ss02-cap62-late100"]
_CHEAP_KINDS_760 = {"private_pickup": {**KINDS["private_pickup"], "cost": 1.4}, "private_delivery": {**KINDS["private_delivery"], "cost": 1.2},
                    "trade_in": {**KINDS["trade_in"], "cost": 2.0}}
VARIANTS["fee16-80-q24-wide-pairs-0.6-return-0.75-thin760-q48-onward-q10-d760-ss02-cap62-late100-mild"] = _full_weeks(
    _A1_7, kinds=_CHEAP_KINDS_760, cost=1.15, queue_hours=12)
VARIANTS["fee16-80-q24-wide-pairs-0.6-return-0.75-thin760-q48-onward-q10-d760-ss02-cap62-late100-cost10"] = _full_weeks(_A1_7, cost=1.0)
# The joint search's volume parts on the aggressive row A1.7, only in a week of 760 drivers or more; a thinner week plays A1.7
# exactly. Every knob here wins orders in the stand-in climb on its own: the quote's flat cost 1.1 (+561 a week on the old base,
# +273 at 1.15 on step04), the waiting cars counted only when due within 12 hours (+320 on row 6), and the declined kinds at a
# cheaper cost (trade-in 2.0, private pickup 1.4, private delivery 1.2: +170 on row 6). `-vol105` goes further: cost 1.05, and a
# request that can go onward with a held car quoted at 0.9 of its typical fee, not 1.0 (pairs.py switches that off under 760).
_A1_7 = VARIANTS["fee16-80-q24-wide-pairs-0.6-return-0.75-thin760-q48-onward-q10-d760-ss02-cap62-late100"]
_KINDS_CHEAP = {"private_pickup": {"cost": 1.4, "odds": 0.06}, "private_delivery": {"cost": 1.2, "odds": 0.37}, "trade_in": {"cost": 2.0, "fee": 1.4, "odds": 0.27}}
VARIANTS["fee16-80-q24-wide-pairs-0.6-return-0.75-thin760-q48-onward-q10-d760-ss02-cap62-late100-vol110"] = _full_weeks(
    _A1_7, cost=1.1, queue_hours=12, kinds=_KINDS_CHEAP)
VARIANTS["fee16-80-q24-wide-pairs-0.6-return-0.75-thin760-q48-onward-q10-d760-ss02-cap62-late100-vol105"] = {
    **_full_weeks(_A1_7, cost=1.05, queue_hours=12, kinds=_KINDS_CHEAP), "pair_onward_cost": 0.9}
# Lane 2's aggressive candidate on safe row 7 and on the aggressive row A1: the onward pairs at a held car's release, open gigs
# and the onward quote at 1.0 in every week, not only with 760 drivers or more (`pair_more_drivers` 0). Row 7's day cap (62
# under 760 drivers) bounds the extra won orders a thin week can collect on one day. At 760 drivers or more each is its row exactly.
for _row in ("fee16-80-q24-wide-pairs-0.6-return-0.75-thin760-q48-onward-q10-d760-ss02-cap62",
             "fee16-80-q24-wide-pairs-0.6-return-0.75-thin760-q48-onward-q10-d760-ss02-cap62-late100"):
    VARIANTS[f"{_row}-onward-all"] = {**VARIANTS[_row], "pair_more_drivers": 0}

# Aggressive: the heaviest volume rung on row A1, all at 760 drivers or more. No waiting-car surcharge (`slow_step` 0, not 0.2),
# the cost at 1.05, the waiting cars counted within 6 hours with a gate of 40, 4 hours to find a driver, not 5, and the kinds
# quoted cheaper (trade-in 2.0, private pickup 1.4, private delivery 1.2). A1's `late_cost` 100 stays. Under 760 drivers it plays A1.
_A1 = VARIANTS["fee16-80-q24-wide-pairs-0.6-return-0.75-thin760-q48-onward-q10-d760-ss02-cap62-late100"]
VARIANTS["fee16-80-q24-wide-pairs-0.6-return-0.75-thin760-q48-onward-q10-d760-ss02-cap62-late100-agg-max"] = _full_weeks(
    _A1, slow_step=0.0, cost=1.05, queue_hours=6, max_unbooked=40, min_slack=240,
    kinds={**_A1["kinds"], "private_pickup": {**_A1["kinds"]["private_pickup"], "cost": 1.4},
           "private_delivery": {**_A1["kinds"]["private_delivery"], "cost": 1.2}, "trade_in": {**_A1["kinds"]["trade_in"], "cost": 2.0}})
# Lane 3, aggressive: a shorter time to find a driver (`min_slack`, 300 minutes) on the aggressive row A1.7, only in a week of
# 760 drivers or more. There merge 1 drops the same_day option of 116 requests a week and declines 33 more for slack under 5
# hours, yet its won orders with 5 to 6 hours of slack are 4.6% late, and a dealer offered same_day beside next_day takes it 84%
# of the time. These orders come at the curve's full price, with the late chance in the cost. A thinner week plays A1.7 exactly.
_A17 = VARIANTS["fee16-80-q24-wide-pairs-0.6-return-0.75-thin760-q48-onward-q10-d760-ss02-cap62-late100"]
VARIANTS.update({f"a17-rich-slack{minutes}": _full_weeks(_A17, min_slack=minutes) for minutes in (240, 180, 120)})
# Lane 4 B: the quote's cost by the groups where merge 1's late orders cluster, only in a week of 760 drivers or more (a
# thinner week plays the row it is built on exactly). On merge 1's played weeks, orders with 16 to 30 hours from the win to the
# last pickup are 5.5% late, orders with more time 0.8% (`within_3_days`), and cars over 120 euros typical (drives of about
# 300 minutes or more) 7.2%. `-h30-c11`: an order with 30 hours or more costs 1.1 at the quote, the others 1.2. `-h16-30-c13`:
# 16 to 30 hours costs 1.3. `-long300-c<cost>`: a drive over 300 minutes costs that. Quote levels only; no fee changes.
# `r7-` is on safe row 7 (`-cap62`), `a17-` on the aggressive row A1 (`-cap62-late100`).
_GROUP_COSTS = (
    ("h30-c11", {"cost": 1.1, "cost_hours": [[30, 1.2]]}),
    ("h16-30-c13", {"cost_hours": [[16, 1.2], [30, 1.3]]}),
    ("h30-c11-h16-30-c13", {"cost": 1.1, "cost_hours": [[16, 1.2], [30, 1.3]]}),
    ("long300-c13", {"long_drive": 300, "long_cost": 1.3}),
    ("long300-c11", {"long_drive": 300, "long_cost": 1.1}))
for _prefix, _row in (("r7", "fee16-80-q24-wide-pairs-0.6-return-0.75-thin760-q48-onward-q10-d760-ss02-cap62"),
                      ("a17", "fee16-80-q24-wide-pairs-0.6-return-0.75-thin760-q48-onward-q10-d760-ss02-cap62-late100")):
    VARIANTS.update({f"{_prefix}-{name}": _full_weeks(VARIANTS[_row], **knobs) for name, knobs in _GROUP_COSTS})
# Track B's fallbacks for the thin side, held for a later thin week that fails: row 7 at 760 drivers or more, and under 760
# either every waiting car counted (all hours, in place of 48), or the default's play with the wide late chance and pairs
# off as well (thin_play.py).
_ROW_7_F = VARIANTS["fee16-80-q24-wide-pairs-0.6-return-0.75-thin760-q48-onward-q10-d760-ss02-cap62"]
VARIANTS["fee16-80-q24-wide-pairs-0.6-return-0.75-thin760-all-onward-q10-d760-ss02-cap62"] = {
    **_ROW_7_F, "when_tight": {**_ROW_7_F["when_tight"], "queue_hours": 0}}
VARIANTS["fee16-80-q24-wide-pairs-0.6-return-0.75-thin760-default-onward-q10-d760-ss02"] = {
    **_ROW_7_F, "thin_play": {"drivers": 760, "params": VARIANTS["slow-friday-late-150-kinds-limits"], "version": thin_play.VERSION}}
