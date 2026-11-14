"""Scores the classifier against hand labels: for each type, did it find the pairs that have one."""

import json
from pathlib import Path

from . import llm
from .classify import QUOTE_CHECK, TYPES, classify_pairs

EVAL_DIR = Path(__file__).resolve().parent / "eval"


def load(pairs_path=EVAL_DIR / "pairs.jsonl", labels_path=EVAL_DIR / "labels.json"):
    labels = json.loads(Path(labels_path).read_text())
    pairs = [json.loads(line) for line in Path(pairs_path).read_text().splitlines() if line.strip()]
    return [p for p in pairs if p["pair_id"] in labels], labels


def evaluate(pairs, labels, workers=8):
    """{"per_type": {type: counts and scores}, "rows": n, "errors": [(pair_id, type, "FP"|"FN")]}"""
    counts = {t: {"tp": 0, "fp": 0, "fn": 0} for t in TYPES}
    errors, n_rows, models = [], 0, set()
    for pair, rows in zip(pairs, classify_pairs(pairs, workers=workers)):
        n_rows += len(rows)
        models.update(r["model"] for r in rows)
        got = {r["type"] for r in rows}
        want = set(labels[pair["pair_id"]]["types"])
        for t in TYPES:
            if t in got and t in want:
                counts[t]["tp"] += 1
            elif t in got:
                counts[t]["fp"] += 1
                errors.append((pair["pair_id"], t, "FP"))
            elif t in want:
                counts[t]["fn"] += 1
                errors.append((pair["pair_id"], t, "FN"))
    for c in counts.values():
        c["precision"] = c["tp"] / (c["tp"] + c["fp"]) if c["tp"] + c["fp"] else None
        c["recall"] = c["tp"] / (c["tp"] + c["fn"]) if c["tp"] + c["fn"] else None
    return {"pairs": len(pairs), "rows": n_rows, "models": sorted(models), "per_type": counts, "errors": errors}


def report(result):
    fmt = lambda x: "  –  " if x is None else f"{x:5.2f}"
    lines = [
        f"{result['pairs']} labelled pairs, {result['rows']} differences found, model: {', '.join(result['models']) or 'none'}",
        f"settings: {json.dumps(llm.options())}" if llm.config() else "settings: word list only",
        "",
        "type           labelled  found  right  precision  recall",
    ]
    for t, c in result["per_type"].items():
        lines.append(
            f"{t:14} {c['tp'] + c['fn']:8} {c['tp'] + c['fp']:6} {c['tp']:6}  {fmt(c['precision']):>9}  {fmt(c['recall']):>6}"
        )
    q = QUOTE_CHECK
    if q["kept"] + q["dropped"]:
        lines += [
            "",
            f"quote check: {q['kept']} of {q['kept'] + q['dropped']} model differences kept, "
            f"{q['dropped']} dropped for quotes not in the passage",
        ]
    u = llm.USAGE
    if u["calls"]:
        lines += [
            "",
            f"{u['calls']} model calls (not cached): {u['input_tokens']:,} input and {u['output_tokens']:,} output tokens, "
            f"{u['input_tokens'] / u['calls']:,.0f} and {u['output_tokens'] / u['calls']:,.0f} per call",
        ]
    return "\n".join(lines)
