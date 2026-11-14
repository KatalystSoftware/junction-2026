"""The win curve: the chance that a dealer buys at a price, and the price that earns most by it.

The curve is a logistic function of the log of the quote over the list price. Its weights are in curve.json, fitted by
scratch/curve_fit.py on weeks that quoted random prices (variant `explore`), with only what holds in every world: the
slope, the dealer's count of orders on time, the options quoted, the typical fee over the list price, and the pickup and
delivery places. What is new in each world and each day (the competitor's price level, its day factor, the price war) is
not in the weights: the desk measures it during the day as one shift of the curve along the price (`shift`).
"""
from __future__ import annotations

import json
import math
from pathlib import Path

MODEL = json.loads(Path(__file__).with_name("curve.json").read_text(encoding="utf-8"))
# The same fit with a level for each week and day (scratch/curve_day.py). Days differ in their price level, and a fit
# without the levels takes that for a flatter curve. Inside a day, which is where the desk prices once it has the
# day's shift, the curve is steeper: the log odds fall 12.5 per unit of log price, against 9.2.
MODELS = {"": MODEL, "day": {**json.loads(Path(__file__).with_name("curve-day.json").read_text(encoding="utf-8")), "cost": MODEL["cost"], "late": MODEL["late"]}}
SLOPE = MODEL["slope"]  # the fall of the log odds per unit of log price
SPEED = ["same_day", "next_day", "within_3_days"]
LOW, HIGH, STEP = 1.0, 2.4, 0.02  # the multiples of the list price to choose from; the random weeks quoted 1.1 to 2.4


def fastest(options: list[dict]) -> dict:
    return min(options, key=lambda o: SPEED.index(o["kind"]))


def at_list(request: dict, options: list[dict], on_time: int, model: dict = MODEL) -> float:
    """The log odds that the dealer buys when every quoted option is at its list price, on an average day.
    `on_time` is the dealer's count of orders on time, which raises the prices it accepts."""
    leg, first = request["legs"][0], fastest(options)
    kinds = "+".join(sorted((o["kind"] for o in options), key=SPEED.index))
    return (model["intercept"] + model["trust"] * math.log(1 + 0.01 * on_time) + model["kinds"].get(kinds, 0.0)
            + model["feelist"] * math.log(request["referenceFeeCents"] / first["listPriceCents"])
            + model["from"].get(leg["pickup"]["placeId"], 0.0) + model["to"].get(leg["delivery"]["placeId"], 0.0))


def known(request: dict, options: list[dict], notified: int, unbooked: int) -> list[float]:
    """What the desk knows at a quote about how the order will go, in the order of the weights `cost` and `late`
    (scratch/cost_fit.py): the typical fee beyond 150 euros in hundreds of euros (long lanes), how few drivers are
    notified of the pickup, a dealer's note, the same_day option, and the won cars without a driver."""
    return [max(0.0, request["referenceFeeCents"] / 100 - 150) / 100, 1 / (1 + notified), float(request["note"] is not None),
            float(fastest(options)["kind"] == "same_day"), min(unbooked, 15) / 10]


def cost(known_: list[float]) -> float:
    """What the order costs, as a multiple of its typical fee: fees, failed visits, waiting and late refunds."""
    weights = MODEL["cost"]
    return weights["intercept"] + sum(w * v for w, v in zip(weights["weights"], known_))


def late(known_: list[float]) -> float:
    """The chance that the order arrives late."""
    weights = MODEL["late"]
    return 1 / (1 + math.exp(-(weights["intercept"] + sum(w * v for w, v in zip(weights["weights"], known_)))))


def chance(log_odds_at_list: float, multiple: float, shift: float = 0.0, slope: float = SLOPE) -> float:
    """The chance that the dealer buys at this multiple of the list price. A shift of 0.1 means that the dealer accepts
    prices about 10% higher than the curve says."""
    return 1 / (1 + math.exp(-(log_odds_at_list - slope * (math.log(multiple) - shift))))


def best(log_odds_at_list: float, shift: float, list_cents: int, cost_cents: float, slope: float = SLOPE) -> float:
    """The multiple of the list price with the highest expected margin: (price - cost) x chance."""
    multiples = [LOW + STEP * n for n in range(int(round((HIGH - LOW) / STEP)) + 1)]
    return max(multiples, key=lambda m: (m * list_cents - cost_cents) * chance(log_odds_at_list, m, shift, slope))


def shift(answers: list[tuple[float, bool]], sd: float, slope: float = SLOPE) -> float:
    """The shift of the curve that fits the answers best. Each answer is the log odds that the curve gave the quote,
    without a shift, and whether the dealer bought. `sd` says how far from 0 a day's shift usually is: with few answers
    the shift stays near 0."""
    d = 0.0
    for _ in range(8):  # Newton steps on the log posterior, which is concave
        chances = [1 / (1 + math.exp(-(z + slope * d))) for z, _ in answers]
        rise = slope * sum(won - c for (_, won), c in zip(answers, chances)) - d / sd**2
        curvature = slope**2 * sum(c * (1 - c) for c in chances) + 1 / sd**2
        d += max(-0.3, min(0.3, rise / curvature))
    return d
