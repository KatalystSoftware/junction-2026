"""Count where Nemotron and Haiku agree on the hero topics' pairs, per category.

    python3 projects/mariadb-wikipedia/demo/hero_agree.py

Reads <model>/index.jsonl and <model>/differences.jsonl of both models under $HERO_CLASSIFY
(default ~/junction2026-data/mariadb/classify), as hero_classify.py wrote them, and compares the
pairs both models answered. Two rows of one pair are about the same thing when their quotes from
the same edition share at least half of the shorter quote's words. Each Nemotron row is matched to
at most one Haiku row, the one sharing most (a row of the same category first).

Prints the counts and writes agreement.json beside the two folders: for every Nemotron row the
category Haiku gave the same thing, or null when Haiku reported nothing there.
"""
import collections
import json
import os
import re
from pathlib import Path

ROOT = Path(os.environ.get("HERO_CLASSIFY", Path.home() / "junction2026-data/mariadb/classify"))
TYPES = ["contradiction", "numbers", "missing_fact", "framing"]


def read(model):
    answered = {json.loads(line)["pair_id"] for line in open(ROOT / model / "index.jsonl", encoding="utf-8")
                if json.loads(line)["cached"]}
    rows = collections.defaultdict(list)
    for line in open(ROOT / model / "differences.jsonl", encoding="utf-8"):
        row = json.loads(line)
        rows[row["pair_id"]].append(row)
    return answered, rows


words = lambda text: set(re.findall(r"\w+", (text or "").lower()))


def shared(x, y):
    """The larger share, over the two editions, of the shorter quote's words found in the other."""
    best = 0.0
    for side in ("quote_a", "quote_b"):
        a, b = words(x[side]), words(y[side])
        if a and b:
            best = max(best, len(a & b) / min(len(a), len(b)))
    return best


def main():
    (n_answered, nemotron), (h_answered, haiku) = read("nemotron"), read("haiku")
    both = sorted(n_answered & h_answered)
    table = {t: collections.Counter() for t in TYPES}
    haiku_only, out, pairs = collections.Counter(), [], collections.Counter()
    for pid in both:
        n_rows, h_rows = nemotron.get(pid, []), haiku.get(pid, [])
        pairs[("some" if n_rows else "none", "some" if h_rows else "none")] += 1
        candidates = sorted(((x["type"] == y["type"], shared(x, y), -i, -j)
                             for i, x in enumerate(n_rows) for j, y in enumerate(h_rows)), reverse=True)
        match = {}
        for _, share, i, j in candidates:
            if share >= 0.5 and -i not in match and -j not in match.values():
                match[-i] = -j
        for i, x in enumerate(n_rows):
            y = h_rows[match[i]] if i in match else None
            table[x["type"]]["rows"] += 1
            table[x["type"]][y["type"] if y else "nothing"] += 1
            out.append({"pair_id": pid, "type": x["type"], "missing_in": x.get("missing_in"),
                        "quote_a": x["quote_a"], "quote_b": x["quote_b"], "summary": x["summary"],
                        "haiku_type": y["type"] if y else None, "haiku_summary": y["summary"] if y else None})
        for j, y in enumerate(h_rows):
            if j not in match.values():
                haiku_only[y["type"]] += 1

    print(f"pairs answered by both models: {len(both)} "
          f"(Nemotron {len(n_answered)}, Haiku {len(h_answered)})")
    for (n, h), count in sorted(pairs.items()):
        print(f"  Nemotron {n} differences, Haiku {h}: {count} pairs")
    print("\nNemotron's rows, by what Haiku said about the same thing:")
    print(f"{'Nemotron':14}{'rows':>6}{'same':>6}" + "".join(f"{t:>15}" for t in TYPES) + f"{'nothing':>9}")
    for t in TYPES:
        c = table[t]
        print(f"{t:14}{c['rows']:>6}{c[t]:>6}" + "".join(f"{c[u]:>15}" for u in TYPES) + f"{c['nothing']:>9}")
    print("\nHaiku's rows with no Nemotron row about the same thing: "
          + ", ".join(f"{t} {haiku_only[t]}" for t in TYPES))
    (ROOT / "agreement.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
    print(f"\n{len(out)} Nemotron rows written to {ROOT / 'agreement.json'}")


if __name__ == "__main__":
    main()
