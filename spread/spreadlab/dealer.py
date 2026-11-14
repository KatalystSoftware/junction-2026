"""The day's correction of the win curve with an offset for each dealer, fitted together (variant `...-dealer`).

The policy's `learn` shifts the curve along the price by one amount for the day, from the day's answers. Here the same
answers also give each dealer its own offset from that level, the price it accepts this week beyond the day's level,
with what the trust count already explains left in the curve. Both are fitted in one likelihood, so an answer counts
once: the day's level takes what all dealers share (the competitor's day factor, the price war), and a dealer's offset
only what differs at that dealer. An answer is censored: a sale says the dealer's price is above the quote, a loss that
it is under; with the curve's logistic noise its likelihood is the curve's chance.

Each offset has a normal prior around 0, the market's level, with sd `dealer_sd` on Monday. Each morning a dealer's prior
is the posterior of the day before, with `dealer_drift`^2 added to its variance, so its step never falls under the
drift's and it follows the competitor's morning cuts at the dealers where the desk wins most. A dealer with few
answers stays near the market's level. The day's level starts again each morning, as `learn` does.

Kept out of policy.py so that the fingerprints of the saved weeks stay: play.py takes this class when `dealer_sd` is
set. Raise `dealer_version` whenever this file changes, so a sweep plays the weeks again.
"""
from __future__ import annotations

import math

from . import curve
from .policy import Policy

PARAMS = {
    "dealer_sd": 0,       # the spread of the dealers' offsets on Monday, in log price; 0 is the day's correction alone
    "dealer_drift": 0,    # how far a dealer's offset moves from one day to the next, in log price
    "dealer_version": 1,  # raised when this file changes
}
STEP = 0.3  # the largest move of one Newton step, in log price


def sig(v: float) -> float:
    return 1 / (1 + math.exp(-v)) if v > -500 else 0.0


def joint(answers: list[tuple[str, float, bool]], prior: dict[str, tuple[float, float]], learn: float, slope: float,
          sweeps: int = 4) -> tuple[float, dict[str, float], dict[str, float]]:
    """The most likely shift of the day and offset of each dealer, from the day's answers (dealer, the curve's log odds
    of the quote without a shift, sold). `prior`: dealer -> mean and variance of its offset. Returns the shift, the
    offsets, and the curvature of each dealer's likelihood today, which turns its prior into tomorrow's."""
    m = {d: prior[d][0] for d, _, _ in answers}
    o, shift = dict(m), 0.0
    for _ in range(sweeps):
        for _ in range(2):
            rise, curvature = -shift / learn**2, 1 / learn**2
            for d, z, sold in answers:
                c = sig(z + slope * (shift + o[d]))
                rise, curvature = rise + slope * (sold - c), curvature + slope**2 * c * (1 - c)
            shift += max(-STEP, min(STEP, rise / curvature))
        rise = {d: -(o[d] - m[d]) / prior[d][1] for d in o}
        curvature = {d: 1 / prior[d][1] for d in o}
        for d, z, sold in answers:
            c = sig(z + slope * (shift + o[d]))
            rise[d] += slope * (sold - c)
            curvature[d] += slope**2 * c * (1 - c)
        for d in o:
            o[d] += max(-STEP, min(STEP, rise[d] / curvature[d]))
    seen = {d: 0.0 for d in o}
    for d, z, _ in answers:
        c = sig(z + slope * (shift + o[d]))
        seen[d] += slope**2 * c * (1 - c)
    return shift, o, seen


class DealerPolicy(Policy):
    def __init__(self, world, level: int, now: int, params: dict, roster: list[dict], map_: dict):
        own = {name: params.get(name, default) for name, default in PARAMS.items()}
        super().__init__(world, level, now, {k: v for k, v in params.items() if k not in PARAMS}, roster, map_)
        self.p.update(own)
        self.prior: dict[str, tuple[float, float]] = {}  # dealer -> the mean and variance of its offset at the start of the day
        self.day_answers: tuple[int, list[tuple[str, float, bool]]] = (0, [])  # the day, and its answers: dealer, log odds, sold
        self.fitted: tuple[tuple[int, int], tuple[float, dict[str, float]]] = ((-1, -1), (0.0, {}))
        self.dealer = ""  # the dealer of the request being quoted

    def prior_of(self, dealer: str) -> tuple[float, float]:
        return self.prior.get(dealer, (0.0, max(self.p["dealer_sd"], 1e-6) ** 2))

    def roll(self, day: int) -> None:
        """At the first answer or quote of a new day, the day before's answers become the dealers' prior, with the drift."""
        old, answers = self.day_answers
        if day <= old:
            return
        if answers and self.p["learn"]:
            prior = {d: self.prior_of(d) for d, _, _ in answers}
            _, offsets, seen = joint(answers, prior, self.p["learn"], self.model["slope"])
            for d, offset in offsets.items():
                self.prior[d] = (offset, 1 / (1 / prior[d][1] + seen[d]))
        drift = self.p["dealer_drift"] ** 2
        self.prior = {d: (mean, variance + drift) for d, (mean, variance) in self.prior.items()}
        self.day_answers = (day, [])

    def quote(self, request) -> None:
        self.dealer = request["dealerId"]
        super().quote(request)

    def shift(self, day: int, p: dict, place: str = "") -> float:
        if not p["dealer_sd"] or not p["learn"]:
            return super().shift(day, p, place)
        self.roll(day)
        answers, slope = self.day_answers[1], self.model["slope"]
        if self.fitted[0] != (day, len(answers)):
            if answers:
                shift, offsets, _ = joint(answers, {d: self.prior_of(d) for d, _, _ in answers}, p["learn"], slope)
            else:
                shift, offsets = 0.0, {}
            self.fitted = ((day, len(answers)), (shift, offsets))
        shift, offsets = self.fitted[1]
        shift += offsets.get(self.dealer, self.prior_of(self.dealer)[0])
        here = self.today_at.get(place, []) if self.today[0] == day else []
        if p["learn_pickup"] and here:  # as the policy does, on top of the day's and the dealer's
            shift += curve.shift([(log_odds + slope * shift, won) for log_odds, won in here], p["learn_pickup"], slope)
        return shift

    def handle(self, event) -> None:
        asked = None
        if event["kind"] in ("order_won", "order_lost"):
            asked = self.asked.get(event["order"]["id"] if event["kind"] == "order_won" else event["requestId"])
        super().handle(event)
        if asked is not None and self.p["dealer_sd"]:
            dealer, day, log_odds = asked
            self.roll(day)
            if self.day_answers[0] == day:
                self.day_answers[1].append((dealer, log_odds, event["kind"] == "order_won"))
