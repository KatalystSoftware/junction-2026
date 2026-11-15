"""Reads a search round's rows, scores each arm against the base, fits a quadratic model of the settings, and writes the next round.

    python scratch/search/analyze.py --spec scratch/search/r1.json --rows <folder with standin-search-* artifacts> ... \
        [--next scratch/search/r2.json --n 192 --seed 2] [--report out.md]

Several `--spec`/`--rows` pairs fit one model over all rounds (same half, same base). Gains are euros a week on natural worlds
(seeds with 720+ drivers): an arm plays only the ones with 760+, and its weeks at 720 to 759 are the base's, so they count as 0.
`score` is what the search maximises: the gain less 20 euros for each extra order a week and 150 for each extra late order. The
stand-in pays an extra order about twice what play does, and a late order is the risk to the 90% rule the stand-in reads low.
"""
from __future__ import annotations

import argparse
import csv
import itertools
import json
import random
from pathlib import Path

import numpy as np

import space

ORDER_PENALTY, LATE_PENALTY = 20.0, 150.0


def load(rows_dirs: list[str]) -> dict:
    """arm -> seed -> week row, from every rows.csv under the folders. The base's weeks must agree across shards."""
    out: dict = {}
    for folder in rows_dirs:
        for path in Path(folder).rglob("rows.csv"):
            for r in csv.DictReader(open(path)):
                if r["draw"] != "0":
                    continue
                week = {k: float(r[k]) for k in ("drivers", "orders", "late", "on_time", "margin", "ranked_margin")}
                old = out.setdefault(r["variant"], {}).get(r["seed"])
                if old and old["ranked_margin"] != week["ranked_margin"]:
                    raise SystemExit(f"{r['variant']} {r['seed']} differs between shards: the stand-in is not deterministic here")
                out[r["variant"]][r["seed"]] = week
    return out


def interval(d: list[float], rounds: int = 2000) -> tuple[float, float]:
    r = random.Random(1)
    m = sorted(sum(r.choices(d, k=len(d))) / len(d) for _ in range(rounds))
    return m[int(0.025 * rounds)], m[int(0.975 * rounds) - 1]


def arm_stats(rows: dict, base: str, arm: str) -> dict | None:
    b = rows[base]
    natural = [s for s, w in b.items() if w["drivers"] >= 720]
    full = [s for s in natural if b[s]["drivers"] >= space_short()]
    have = [s for s in full if s in rows.get(arm, {})]
    if len(have) < len(full):
        return None
    k = len(natural)
    diff = [rows[arm][s]["ranked_margin"] - b[s]["ranked_margin"] for s in full] + [0.0] * (k - len(full))
    gain = sum(diff) / k
    lo, hi = interval(diff)
    d_orders = sum(rows[arm][s]["orders"] - b[s]["orders"] for s in full) / k
    d_late = sum(rows[arm][s]["late"] - b[s]["late"] for s in full) / k
    return {"gain": gain, "lo": lo, "hi": hi, "orders": d_orders, "late": d_late,
            "u90": sum(rows[arm][s]["on_time"] < 0.90 for s in full), "b90": sum(b[s]["on_time"] < 0.90 for s in full),
            "u92": sum(rows[arm][s]["on_time"] < 0.92 for s in full), "b92": sum(b[s]["on_time"] < 0.92 for s in full),
            "score": gain - ORDER_PENALTY * max(0.0, d_orders) - LATE_PENALTY * max(0.0, d_late), "seeds": k}


def space_short() -> int:
    return 760


def features(u: np.ndarray) -> np.ndarray:
    """1, x, x^2 and x_i x_j of the points' unit coordinates, centred on the middle of each range."""
    x = np.atleast_2d(u) - 0.5
    n = x.shape[1]
    cols = [np.ones(len(x))] + [x[:, i] for i in range(n)] + [x[:, i] ** 2 for i in range(n)] + [x[:, i] * x[:, j] for i, j in itertools.combinations(range(n), 2)]
    return np.stack(cols, axis=1)


def fit(u: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, float, float]:
    """Ridge on the quadratic features, its penalty chosen by leave-one-out error; the intercept and linear terms are not shrunk."""
    X = features(u)
    n = u.shape[1]
    shrink = np.ones(X.shape[1])
    shrink[: 1 + n] = 1e-6
    best = None
    for lam in (0.03, 0.1, 0.3, 1, 3, 10, 30):
        A = X.T @ X + lam * np.diag(shrink)
        H = X @ np.linalg.solve(A, X.T)
        beta = np.linalg.solve(A, X.T @ y)
        res = (y - X @ beta) / np.clip(1 - np.diag(H), 1e-3, None)
        loo = float(np.sqrt(np.mean(res ** 2)))
        if best is None or loo < best[1]:
            best = (beta, loo, lam)
    return best


def predict(beta: np.ndarray, u: np.ndarray) -> np.ndarray:
    return features(u) @ beta


def report(points: dict, stats: dict, models: dict, base_u: np.ndarray) -> list[str]:
    lines = []
    names = space.NAMES
    n = len(names)
    grid = np.linspace(0, 1, 11)
    lines.append("## Each setting alone, the others at the base (model, euros a week on natural worlds)")
    lines.append(f"{'setting':18} {'range':>13} {'base':>6} | {'score swing':>11} {'gain swing':>10} {'orders':>7} {'late':>6} | good region (score within 150 of its best)")
    rows = []
    for i, name in enumerate(names):
        u = np.repeat(base_u[None], len(grid), axis=0)
        u[:, i] = grid
        curves = {k: predict(m[0], u) for k, m in models.items()}
        sc = curves["score"]
        good = grid[sc >= sc.max() - 150]
        lo, hi, b, _ = space.SPACE[name]
        val = lambda g: lo + g * (hi - lo)
        edge = " (base near its edge)" if (abs(base_u[i] - good.min()) < 0.1 or abs(base_u[i] - good.max()) < 0.1) and not (good.min() == 0 and good.max() == 1) else ""
        outside = " (base outside it)" if not (good.min() - 0.05 <= base_u[i] <= good.max() + 0.05) else ""
        rows.append((sc.max() - sc.min(), f"{name:18} {f'{lo:g}..{hi:g}':>13} {b:>6g} | {sc.max() - sc.min():11.0f} {curves['gain'].max() - curves['gain'].min():10.0f} "
                     f"{curves['orders'][-1] - curves['orders'][0]:+7.1f} {curves['late'][-1] - curves['late'][0]:+6.2f} | "
                     f"{val(good.min()):.3g} to {val(good.max()):.3g}, best {val(grid[sc.argmax()]):.3g}{outside or edge}"))
    lines += [r for _, r in sorted(rows, key=lambda t: -t[0])]
    lines.append("")
    lines.append("(orders and late: the change from the low end of the range to the high end)")
    lines.append("")
    lines.append("## Pairs that interact (model's x_i x_j term: the extra score at both highs or both lows, euros a week)")
    beta = models["score"][0]
    pairs = list(itertools.combinations(range(n), 2))
    inter = beta[1 + 2 * n:]
    order = np.argsort(-np.abs(inter))[:10]
    for k in order:
        i, j = pairs[k]
        lines.append(f"- {names[i]} x {names[j]}: {inter[k] / 4:+.0f} (corner to corner {inter[k]:+.0f})")
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--spec", nargs="+", required=True)
    parser.add_argument("--rows", nargs="+", required=True)
    parser.add_argument("--next", default="")
    parser.add_argument("--n", type=int, default=192)
    parser.add_argument("--seed", type=int, default=2)
    parser.add_argument("--report", default="")
    parser.add_argument("--table", default="", help="a CSV of every arm's numbers and settings")
    args = parser.parse_args()
    rows = load(args.rows)
    points, base = {}, None
    for path in args.spec:
        spec = json.loads(Path(path).read_text())
        base = spec["baseline"]
        points.update(spec["points"])
    stats = {a: s for a in points if (s := arm_stats(rows, base, a))}
    arms = list(stats)
    u = np.stack([space.unit(points[a]) for a in arms])
    base_u = space.unit({n: space.SPACE[n][2] for n in space.NAMES})
    models = {k: fit(u, np.array([stats[a][k] for a in arms])) for k in ("score", "gain", "orders", "late")}
    lines = [f"# Search: {len(arms)} arms of {len(points)} against {base}", ""]
    lines += [f"Model fit (leave-one-out error, ridge): " + ", ".join(f"{k} {m[1]:.1f} (sd {np.std([stats[a][k] for a in arms]):.1f}, lambda {m[2]})" for k, m in models.items()), ""]
    lines += report(points, stats, models, base_u) + [""]
    top = sorted(arms, key=lambda a: -stats[a]["score"])[:15]
    lines.append("## Best arms by score (played on this half)")
    lines.append(f"{'arm':10} {'score':>6} {'gain':>6} {'95% interval':>14} {'orders':>7} {'late':>6} {'<90':>6} {'<92':>6}  model")
    for a in top:
        s = stats[a]
        lines.append(f"{a:10} {s['score']:6.0f} {s['gain']:+6.0f} {f'{s['lo']:+.0f}..{s['hi']:+.0f}':>14} {s['orders']:+7.1f} {s['late']:+6.2f} "
                     f"{s['u90']:>2}/{s['b90']:<3} {s['u92']:>2}/{s['b92']:<3} {predict(models['score'][0], space.unit(points[a])[None])[0]:6.0f}")
    lines.append("")
    # The model's best point within the box, from many random points and a few steps of local search.
    rng = np.random.default_rng(args.seed)
    cand = np.vstack([rng.random((40000, len(space.NAMES))), np.stack([space.unit(points[a]) for a in top])])
    pred = predict(models["score"][0], cand)
    best_u = cand[np.argsort(-pred)[:20]]
    for _ in range(30):
        moves = np.clip(best_u[:, None] + rng.normal(0, 0.05, (len(best_u), 200, len(space.NAMES))), 0, 1).reshape(-1, len(space.NAMES))
        allc = np.vstack([best_u, moves])
        p = predict(models["score"][0], allc)
        best_u = allc[np.argsort(-p)[:20]]
    opt = space.point_of(best_u[0])
    lines.append(f"Model's best point: score {predict(models['score'][0], best_u[:1])[0]:.0f}, gain {predict(models['gain'][0], best_u[:1])[0]:.0f}, "
                 f"orders {predict(models['orders'][0], best_u[:1])[0]:+.1f}, late {predict(models['late'][0], best_u[:1])[0]:+.2f}")
    lines.append("    " + json.dumps(opt))
    if args.table:
        with open(args.table, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["arm", *stats[arms[0]].keys(), *space.NAMES])
            for a in arms:
                w.writerow([a, *(round(v, 2) if isinstance(v, float) else v for v in stats[a].values()), *(points[a][n] for n in space.NAMES)])
    if args.next:
        # Next round: a third from the model's best and its neighbours, two thirds from an evolution step around the best played arms
        # (the mean and spread of the top fifth by score, weighted by rank, as in CMA-ES).
        elite = sorted(arms, key=lambda a: -stats[a]["score"])[: max(8, len(arms) // 5)]
        e = np.stack([space.unit(points[a]) for a in elite])
        w = np.log(len(elite) + 0.5) - np.log(np.arange(1, len(elite) + 1))
        w /= w.sum()
        mean = w @ e
        cov = (e - mean).T @ np.diag(w) @ (e - mean) + np.eye(len(mean)) * 0.002
        n_model = args.n // 3
        model_pts = [best_u[0]] + [np.clip(best_u[0] + rng.normal(0, 0.08, len(mean)), 0, 1) for _ in range(n_model - 1)]
        cma_pts = list(np.clip(rng.multivariate_normal(mean, cov * 1.5, args.n - n_model), 0, 1))
        new = [space.point_of(x) for x in model_pts + cma_pts]
        space.write(new, Path(args.next).stem, args.next)
        lines.append(f"Next round {args.next}: {n_model} around the model's best, {args.n - n_model} from the top {len(elite)} played arms' spread")
    text = "\n".join(lines) + "\n"
    if args.report:
        Path(args.report).write_text(text)
    print(text)


if __name__ == "__main__":
    main()
