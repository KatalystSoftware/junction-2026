"""The won notes whose posted reading the rules get wrong, by field, against the reveal. From spread/:

    PYTHONPATH=. uv run python scratch/note-actions/misses.py dev [field]     # the dev wordings: these may seed rule candidates
    PYTHONPATH=. uv run python scratch/note-actions/misses.py all --count     # counts only, every wording: the no-regression check

`--rules <module>` scores another copy of notes.py (a candidate), e.g. scratch.note-actions.candidate, for the
self-healing check: every field must have no more misses than the current rules, on every split.
"""
import sys, json, collections, importlib
sys.path.insert(0, __file__.rsplit("/", 1)[0])
import eval as ev
from spreadlab import notes as current


def wrong_fields(r, reader):
    facts, limits = reader.read(r["note"], r["arrivedAt"]), reader.limits(r["note"], r["arrivedAt"])
    rules, real = ev.state(r, facts, limits), ev.truth(r)
    rules["summer"] = reader.summer_tyres(r["note"])
    return {f for f in ev.FIELDS if rules[f] != real[f]}, rules, real


def main():
    split = sys.argv[1]
    field = next((a for a in sys.argv[2:] if a in ev.FIELDS), None)
    reader = importlib.import_module(sys.argv[sys.argv.index("--rules") + 1]) if "--rules" in sys.argv else current
    rows = [r for r in map(json.loads, open(ev.DATA / "rows.jsonl")) if r["note"] and len(r["truth"]) == 1
            and (split == "all" or ev.held_out(r["note"]["text"]) == (split == "held"))]
    c, shown = collections.Counter(), collections.Counter()
    for r in rows:
        wrong, rules, real = wrong_fields(r, reader)
        c.update(wrong); c["notes"] += 1
        for f in wrong:
            if "--count" not in sys.argv and (field in (None, f)) and shown[f] < 40 and f != "summer" or (f == field == "summer" and shown[f] < 40):
                shown[f] += 1
                print(json.dumps({"field": f, "text": r["note"]["text"], "rules": rules[f], "truth": real[f], "arrived": r["arrivedAt"]}, ensure_ascii=False))
    print(json.dumps({"split": split, "rules": reader.__name__, **c}))


if __name__ == "__main__":
    main()
