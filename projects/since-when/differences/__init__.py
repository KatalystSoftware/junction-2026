"""Differences between aligned passages of two Wikipedia language editions, with the quotes behind them.

See README.md for the input and output format.
"""

from .classify import TYPE_WEIGHT, TYPES, classify_pair, classify_pairs, locate

__all__ = ["TYPE_WEIGHT", "TYPES", "classify_pair", "classify_pairs", "locate"]
