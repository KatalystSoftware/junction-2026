"""Named variants: each changes some of the policy's parameters (policy.DEFAULTS). Add one here to
compare it with the others on the same seeds."""
from __future__ import annotations

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
}
