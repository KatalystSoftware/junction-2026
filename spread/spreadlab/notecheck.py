"""The rules' reading of dealer notes against what the reveal says was true, field by field, on every won note of the
archive. Run it on every change to `notes.py` or to how the policy reads notes; CI runs `--check`.

    python3 -m spreadlab.notecheck                         # the miss table, dev and held-out
    python3 -m spreadlab.notecheck --show 10 --field deadline --split dev   # the dev notes the rules misread on one field
    python3 -m spreadlab.notecheck --check                 # fails when a field misses more notes than note-misses.json allows
    python3 -m spreadlab.notecheck --check --write         # after an improvement: lower the allowance to the new counts
    uv run python -m spreadlab.notecheck extract           # rebuild note-truth.jsonl.gz from archive/bundles (git lfs pull first)

The truth exists only for won orders: the reveal of a week holds the cars of the orders won in it. A seed's world is
the same in every week played on it, so each request that any saved week won is one row, whatever variant won it.
`extract` also writes the notes that no week has won, which have no truth, to the data folder for a model to label.

Held out: a note belongs to the held-out split when the hash of its text, digits masked, falls in one of five buckets,
so a wording and its copies with other times sit on one side only. Fix rules from the dev split's misses; the held-out
split says whether a fix generalises. Never read the held-out misses to write a rule (`--show` refuses them).

Each field counts a row as missed when the rules' reading, put together with what the request states, differs from the
truth: the first minute the car can be collected, plates, a manual gearbox, the note's own deadline when it is earlier
than the order's, the pickup and delivery sites' hours where the request gives hours, and summer tyres, which the rules
do not read at all.
"""
from __future__ import annotations

import argparse
import functools
import gzip
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

from . import notes

PROJECT = Path(__file__).resolve().parent.parent
TRUTH = PROJECT / "catalogue" / "note-truth.jsonl.gz"
BASELINE = PROJECT / "catalogue" / "note-misses.json"
DAY = 24 * 60
FIELDS = ("ready", "plates", "manual", "deadline", "pickup_hours", "delivery_hours", "summer_tyres")


# The rules look each word up in their word lists, with typos, which takes minutes over the archive; notes share few
# distinct words, so the lookups are cached here. They are pure functions of the word, so the reading is the same.
for name in ("tag", "weekday", "hour_in_words"):
    setattr(notes, name, functools.lru_cache(maxsize=None)(getattr(notes, name)))


def held_out(text: str) -> bool:
    return int(hashlib.sha256(re.sub(r"\d", "0", text.lower()).encode()).hexdigest(), 16) % 5 == 0


def clock(minute) -> str:
    return "-" if minute is None else f"d{minute // DAY} {minute % DAY // 60:02d}:{minute % 60:02d}"


def rules(row: dict) -> dict:
    """The rules' reading of a row's note, in the shape of the reveal's truth."""
    note, arrived = {"text": row["text"]}, row["arrivedAt"]
    facts, limits = notes.read(note, arrived), notes.limits(note, arrived)
    out = {"ready": facts.pickup_from, "plates": facts.plates, "manual": facts.manual, "summer": notes.summer_tyres(note), "deadline": limits.deadline or None}
    for site, read in (("pickup", limits.pickup_hours), ("delivery", limits.delivery_hours)):
        stated = row[site + "Hours"]
        out[site + "Hours"] = None if stated is None else [read[0] or stated[0], read[1] or stated[1]]
    return out


def view(row: dict, truth: dict) -> dict:
    """Each field as it matters to the desk, put together with what the request states: the ready time counts from the
    pickup window's start, and a deadline at or after the order's own counts as none. A site without hours (a private
    address) has no hours field."""
    out = {"ready": max(row["from"], truth["ready"] or 0), "plates": truth["plates"], "manual": truth["manual"],
           "deadline": truth["deadline"] if truth["deadline"] and truth["deadline"] < row["deadline"] else None, "summer_tyres": truth["summer"]}
    for site in ("pickup", "delivery"):
        if row[site + "Hours"] is not None and truth[site + "Hours"] is not None:
            out[site + "_hours"] = list(truth[site + "Hours"])
    return out


def score(row: dict, reading: dict | None = None, truth: dict | None = None) -> dict:
    """Each field: (right, read, true). By default the rules' reading against the reveal."""
    read, real = view(row, reading or rules(row)), view(row, truth or row["truth"])
    return {field: (read[field] == real[field], read[field], real[field]) for field in FIELDS if field in read and field in real}


def say(field: str, value) -> str:
    if field in ("ready", "deadline"):
        return clock(value)
    if field.endswith("_hours"):
        return f"{clock(value[0])[3:]}-{clock(value[1])[3:]}"
    return str(value)


def rows() -> list[dict]:
    with gzip.open(TRUTH, "rt", encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def table(data: list[dict]) -> dict:
    """{split: {field: [notes scored, missed]}} for dev, held-out and all."""
    counts = {split: {field: [0, 0] for field in FIELDS} for split in ("dev", "held_out", "all")}
    for row in data:
        for field, (right, _, _) in score(row).items():
            for split in ("held_out" if held_out(row["text"]) else "dev", "all"):
                counts[split][field][0] += 1
                counts[split][field][1] += not right
    return counts


def show(data: list[dict], field: str, split: str, n: int) -> None:
    if split != "dev":
        raise SystemExit("Only the dev split's misses are listed: the held-out split is for measuring a fix, not for writing it.")
    misses = Counter()
    for row in data:
        if held_out(row["text"]) or field not in (s := score(row)) or s[field][0]:
            continue
        misses[(row["text"], say(field, s[field][1]), say(field, s[field][2]), clock(row["arrivedAt"]))] += 1
    print(f"{sum(misses.values())} dev notes misread on {field}, {len(misses)} distinct (text, read, true):")
    for (text, read, real, arrived), k in misses.most_common(n):
        print(f"  x{k:<3} arrived {arrived}  read {read}  true {real} | {text[:300]}")


def hours(h) -> list[int] | None:
    return None if h is None else [h["opens"], h["closes"]]


def stated(seed: str, request: dict) -> dict:
    """What a request states beside its note, as a row holds it."""
    leg = request["legs"][0]
    return {"seed": seed, "id": request["id"], "arrivedAt": request["arrivedAt"], "text": request["note"]["text"], "legs": len(request["legs"]),
            "from": leg["pickup"]["window"]["from"], "pickupHours": hours(leg["pickup"]["hours"]), "deliveryHours": hours(leg["delivery"]["hours"])}


def extract(bundles: Path) -> None:
    """note-truth.jsonl.gz from the bundles' weeks, and the notes no week has won to the data folder."""
    from . import archive
    from .server import data_dir

    held, rows, notes_seen = archive.packed(bundles), {}, {}
    for bundle in sorted(bundles.glob("*.tar.zst")):
        for name, content in archive.members(bundle):
            if held[name][1] != bundle or not name.endswith(".json.gz"):
                continue
            week = json.loads(content)
            if name.startswith("scans/"):
                for event in week["events"]:
                    if event["kind"] == "price_request" and event["request"]["note"]:
                        r = event["request"]  # no option is won yet: the latest deadline stands for the order's
                        notes_seen[(week["seed"], r["id"])] = {**stated(week["seed"], r), "deadline": max(o["deadline"] for o in r["options"])}
                continue
            requests = {r["request"]["id"]: r["request"] for r in week["reveal"]["requests"]}
            won = {e["order"]["id"]: e["order"] for e in week["events"] if e["kind"] == "order_won"}
            for order in week["reveal"]["orders"]:
                r = requests[order["orderId"]]
                if not r["note"] or order["orderId"] not in won or (week["seed"], r["id"]) in rows:
                    continue
                truth = order["legs"][0]
                rows[(week["seed"], r["id"])] = {
                    **stated(week["seed"], r), "deadline": won[r["id"]]["deadline"],
                    "truth": {"ready": max(truth["readyAt"], truth["releasedAt"] or 0), "plates": truth["needsPlates"], "manual": truth["manualGearbox"],
                              "summer": truth["summerTyres"], "deadline": truth["noteDeadline"], "pickupHours": hours(truth["pickupHours"]),
                              "deliveryHours": hours(truth["deliveryHours"])}}
            print(f"{len(rows)} won notes after {name}", file=sys.stderr, end="\r")
    lines = "".join(json.dumps(rows[key], ensure_ascii=False, separators=(",", ":")) + "\n" for key in sorted(rows))
    TRUTH.write_bytes(gzip.compress(lines.encode(), compresslevel=9, mtime=0))  # no time stamp: the same weeks give the same file
    unlabelled = data_dir() / "llm-notes" / "unlabelled.jsonl"
    unlabelled.parent.mkdir(parents=True, exist_ok=True)
    with open(unlabelled, "w", encoding="utf-8") as f:
        for key in sorted(notes_seen):
            if key not in rows:
                f.write(json.dumps(notes_seen[key], ensure_ascii=False) + "\n")
    print(f"\n{TRUTH.name}: {len(rows)} won notes of {len({k[0] for k in rows})} seeds; {unlabelled}: "
          f"{sum(1 for k in notes_seen if k not in rows)} of {len(notes_seen)} scanned notes have no truth")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", nargs="?", choices=["table", "extract"], default="table")
    parser.add_argument("--bundles", type=Path, default=None, help="extract: the folder of bundles; default archive/bundles")
    parser.add_argument("--show", type=int, default=0, help="list this many of the dev split's misread notes on --field")
    parser.add_argument("--field", choices=FIELDS, default="ready")
    parser.add_argument("--split", default="dev")
    parser.add_argument("--check", action="store_true", help="exit 1 when a field misses more notes than note-misses.json allows")
    parser.add_argument("--write", action="store_true", help="with --check: write the current counts as the new allowance")
    parser.add_argument("--json", action="store_true", help="print the table as JSON")
    args = parser.parse_args()
    if args.command == "extract":
        from . import archive
        return extract(args.bundles or archive.BUNDLES)
    data = rows()
    if args.show:
        return show(data, args.field, args.split, args.show)
    counts = table(data)
    if args.json:
        print(json.dumps(counts))
    else:
        print(f"{len(data)} won notes of {len({r['seed'] for r in data})} seeds with what the reveal says was true; held out: "
              f"{sum(held_out(r['text']) for r in data)} (a fifth of the wordings, by hash)")
        print(f"  {'field':<15} {'dev missed':>18} {'held-out missed':>18} {'all missed':>18}")
        for field in FIELDS:
            cells = [f"{c[1]:>5}/{c[0]:<6} {c[1] / max(1, c[0]):6.2%}" for c in (counts[s][field] for s in ("dev", "held_out", "all"))]
            print(f"  {field:<15} " + " ".join(f"{cell:>18}" for cell in cells))
    if args.check:
        if args.write:
            BASELINE.write_text(json.dumps({field: counts["all"][field][1] for field in FIELDS}, indent=1) + "\n")
            print(f"{BASELINE.name} written.")
            return
        allowed = json.loads(BASELINE.read_text())
        worse = [f"{field}: {counts['all'][field][1]} missed, {allowed[field]} allowed" for field in FIELDS if counts["all"][field][1] > allowed[field]]
        if worse:
            raise SystemExit("The rules miss more notes than before: " + "; ".join(worse))
        print("No field misses more notes than note-misses.json allows.")


if __name__ == "__main__":
    main()
