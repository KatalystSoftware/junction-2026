"""The on-time budget (budget.py) switched off in a band of driver lists, known before the first quote.

With `budget_off` {"drivers": [from, under], "version": VERSION}, a week whose driver list has at least `from` and fewer
than `under` drivers plays without `budget`, so it decides as the variant without the budget; every other week plays the
budget. Kept apart from budget.py so the fingerprints of the variants that play the budget everywhere stay.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from .budget import BudgetThinWidePairPolicy

VERSION = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:12]


class BudgetBand:
    """Put it before Budget among the bases."""

    def __init__(self, world, level: int, now: int, params: dict, roster: list[dict], map_: dict):
        rule = params.get("budget_off")
        params = {k: v for k, v in params.items() if k != "budget_off"}
        if rule and rule["drivers"][0] <= len(roster) < rule["drivers"][1]:
            params = {k: v for k, v in params.items() if k != "budget"}
        super().__init__(world, level, now, params, roster, map_)


class BandBudgetThinWidePairPolicy(BudgetBand, BudgetThinWidePairPolicy):
    """The on-time budget outside a band of driver lists."""
