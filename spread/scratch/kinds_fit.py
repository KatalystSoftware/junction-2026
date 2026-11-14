"""Scratch: how far the win curve is off for the kinds of request it has no answers from. Reads weeks that quoted those
kinds at random prices (`learn-kinds-2`), takes for each quote the log odds that the desk's curve gave it at that minute
(the curve with a level for each day, the dealer's count, and the day's shift so far), and fits what must be added to
them for the kind: `odds`, and with it a factor on the slope to see whether the kind answers the price as dealers do.

    PYTHONPATH=. uv run python scratch/kinds_fit.py --variant learn-kinds-2 --seeds kinds-001,kinds-002
"""
from __future__ import annotations

import argparse
import collections
import math

from spreadlab import curve
from spreadlab.play import load_run, run_path
from spreadlab.policy import kind

MODEL = curve.MODELS["day"]


def fit(rows: list[tuple[float, bool]], with_slope: bool) -> tuple[float, float, float]:
    """The offset a, and the factor b when it is fitted, of logit = a + b * z, with the log loss."""
    a, b = 0.0, 1.0
    for _ in range(200):
        ga = gb = haa = hbb = hab = 0.0
        for z, won in rows:
            p = 1 / (1 + math.exp(-(a + b * z)))
            ga += won - p
            gb += (won - p) * z
            haa += p * (1 - p)
            hab += p * (1 - p) * z
            hbb += p * (1 - p) * z * z
        if with_slope:
            det = haa * hbb - hab * hab
            a, b = a + (hbb * ga - hab * gb) / det, b + (haa * gb - hab * ga) / det
        else:
            a += ga / haa
    loss = -sum(math.log(max(1e-9, (lambda p: p if won else 1 - p)(1 / (1 + math.exp(-(a + b * z)))))) for z, won in rows) / len(rows)
    return a, b, loss


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--variant", default="learn-kinds-2")
    parser.add_argument("--seeds", required=True)
    args = parser.parse_args()
    rows = collections.defaultdict(list)  # kind -> (seed, log odds by the curve, won)
    for seed in args.seeds.split(","):
        if not run_path(args.variant, seed).exists():
            continue
        run = load_run(args.variant, seed)
        won = {e["order"]["id"] for e in run["events"] if e["kind"] == "order_won"}
        for x in run["reveal"]["requests"]:
            request, decision = x["request"], run["decisions"][x["request"]["id"]]
            if decision["declined"] or not decision.get("explored"):
                continue
            options = [o for o in request["options"] if o["kind"] in decision["prices"]]
            first = curve.fastest(options)
            multiple = decision["prices"][first["kind"]] / first["listPriceCents"]
            z = curve.at_list(request, options, decision["seen"]["trust"], MODEL) - MODEL["slope"] * (math.log(multiple) - decision["seen"]["shift"])
            rows[kind(request)].append((seed, z, request["id"] in won))
    for name, kind_rows in sorted(rows.items()):
        data = [(z, won) for _, z, won in kind_rows]
        share = sum(won for _, won in data) / len(data)
        expected = sum(1 / (1 + math.exp(-z)) for z, _ in data) / len(data)
        zero = -sum(math.log(max(1e-9, (lambda p: p if won else 1 - p)(1 / (1 + math.exp(-z))))) for z, won in data) / len(data)
        a, _, loss = fit(data, False)
        a2, b2, loss2 = fit(data, True)
        # The offset fitted on half of the weeks, scored on the other half.
        seeds = sorted({seed for seed, _, _ in kind_rows})
        held = []
        for part in (0, 1):
            train = [(z, won) for seed, z, won in kind_rows if seeds.index(seed) % 2 != part]
            test = [(z, won) for seed, z, won in kind_rows if seeds.index(seed) % 2 == part]
            a_, _, _ = fit(train, False)
            held.append(-sum(math.log(max(1e-9, (lambda p: p if won else 1 - p)(1 / (1 + math.exp(-(a_ + z)))))) for z, won in test) / len(test))
        print(f"{name:17s} quotes {len(data):4d} won {share:5.1%}, the curve expected {expected:5.1%}; log loss {zero:.3f} as it is, {loss:.3f} with odds {a:+.2f} "
              f"({sum(held) / 2:.3f} on the weeks it was not fitted on), {loss2:.3f} with odds {a2:+.2f} and {b2:.2f} x the slope")


if __name__ == "__main__":
    main()
