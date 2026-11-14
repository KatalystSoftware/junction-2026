"""Another variant's play in a week with a short driver list. `when_tight` (policy.py) can only change the policy's own
parameters, and the wide late chance and pairs take theirs out before the policy sees them; this switches the whole set.

With `thin_play` {"drivers": N, "params": {...}, "version": VERSION}, a week whose driver list is shorter than N plays
`params` in place of the variant's own, known before the first quote. A pair desk given the default's parameters holds no
car and keeps slow.py's late chance, so it plays the default's decisions. Off when the variant does not set it.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from .late_wide import WidePairPolicy

VERSION = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:12]


class ThinPlay:
    """Put it first among the bases: it chooses the parameters before the others read them."""

    def __init__(self, world, level: int, now: int, params: dict, roster: list[dict], map_: dict):
        rule = params.get("thin_play")
        params = {k: v for k, v in params.items() if k != "thin_play"}
        if rule and len(roster) < rule["drivers"]:
            params = rule["params"]
        super().__init__(world, level, now, params, roster, map_)


class ThinWidePairPolicy(ThinPlay, WidePairPolicy):
    """The wide late chance with pairs, and another variant's play in a thin week."""
