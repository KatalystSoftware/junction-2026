"""Labels dealer notes with a strong model where no reveal says what was true, and lists where the label and the rules
disagree, field by field, as `notecheck` does against the reveal. Offline: latency does not matter, so it uses Claude
Opus 5.5 with ANTHROPIC_API_KEY from the environment.

    uv run python -m spreadlab.notelabel label truth --held-out --limit 300   # calibration: label held-out won notes
    uv run python -m spreadlab.notelabel label data/llm-notes/unlabelled.jsonl --new --limit 2000  # notes no week has won
    uv run python -m spreadlab.notelabel label <world folder>/events.jsonl.gz # a live week's notes
    uv run python -m spreadlab.notelabel report truth --held-out   # the model's own misses against the reveal
    uv run python -m spreadlab.notelabel report data/llm-notes/unlabelled.jsonl --show deadline  # the rules against the labels

A label is the note's facts in the note's own words for days ("tomorrow", "thu"), so it holds for the note's text
whatever day the request arrived, and each wording (digits masked) is asked once. Labels go to data/llm-notes/labels.jsonl.
`--new` keeps only the notes whose wording (digits masked) no won note of note-truth.jsonl.gz has: those that the
reveal's check cannot speak for. Disagreements are listed only from the dev split (`notecheck.held_out`).
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import notecheck, watch
from .server import data_dir

MODEL = os.environ.get("NOTE_LABEL_MODEL", "claude-opus-5-5")
EFFORT = os.environ.get("NOTE_LABEL_EFFORT", "low")
LABELS = data_dir() / "llm-notes" / "labels.jsonl"
SYSTEM = """You read a note that a Finnish car dealer wrote on a car transport request, and extract its operational facts. Notes are in Finnish, Swedish or English, with abbreviations and typos. Answer with one JSON object and nothing else:

{"ready": {"day": ..., "time": ...} or null,
 "no_plates": true or false,
 "manual": true or false,
 "summer_tyres": true or false,
 "deadline": {"day": ..., "time": ...} or null,
 "pickup_hours": {"opens": ..., "closes": ...} or null,
 "delivery_hours": {"opens": ..., "closes": ...} or null}

- "ready": the first day and time the car can be collected: when it is ready, or when it is handed over, for example after payment. Null when the note states none.
- "no_plates": the car has no registration plates, so the driver brings transfer plates.
- "manual": the car has a manual gearbox, so the driver needs a licence for manual cars.
- "summer_tyres": the car is on summer tyres.
- "deadline": a time by which the car must be at its destination, or by which the receiving customer needs it. Null when the note states none.
- "pickup_hours": opening hours of the pickup site that the note states, or a time by which the car must be collected or the site closes. Give "opens" null when the note states only a closing time, and "closes" null when it states only an opening time. Null when the note states none.
- "delivery_hours": the same for the receiving site.

Keys, calls, reference numbers, spare tyres, where the car is parked, greetings and thanks are not facts here.

"""
SYSTEM += watch.SYSTEM[watch.SYSTEM.index("Days:"):]


def ask(text: str, key: str, timeout: float = 60) -> dict:
    # Opus 5.5 takes no "disabled" thinking; it thinks as much as the effort asks, inside max_tokens.
    body = {"model": MODEL, "max_tokens": 4000, "system": [{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
            "messages": [{"role": "user", "content": f"Note: {text}"}], "thinking": {"type": "adaptive"}, "output_config": {"effort": EFFORT}}
    request = urllib.request.Request("https://api.anthropic.com/v1/messages", json.dumps(body).encode(),
                                     {"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    started = time.monotonic()
    for attempt in range(5):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                answer = json.load(response)
            break
        except urllib.error.HTTPError as error:
            if error.code not in (429, 500, 502, 503, 529) or attempt == 4:
                return {"text": text, "model": MODEL, "error": f"HTTP {error.code}", "body": error.read()[:300].decode(errors="replace")}
        except Exception as error:  # a timeout or a lost connection
            if attempt == 4:
                return {"text": text, "model": MODEL, "error": type(error).__name__}
        time.sleep(5 * (attempt + 1))
    content = "".join(block["text"] for block in answer["content"] if block["type"] == "text")
    try:
        label = json.loads(re.search(r"\{.*\}", content, re.S)[0])
    except (TypeError, ValueError):
        label = None
    return {"text": text, "model": MODEL, "label": label, "seconds": round(time.monotonic() - started, 2), "usage": answer.get("usage"),
            **({} if label else {"error": "unreadable", "content": content[:500]})}


def truth_of(label: dict, row: dict) -> dict:
    """A label in the shape of the reveal's truth for one row: its days counted from the row's arrival."""
    at = lambda x: watch.when(x.get("day"), x.get("time"), row["arrivedAt"]) if isinstance(x, dict) else None  # noqa: E731
    out = {"ready": at(label.get("ready")) or 0, "plates": bool(label.get("no_plates")), "manual": bool(label.get("manual")),
           "summer": bool(label.get("summer_tyres")), "deadline": at(label.get("deadline"))}
    for site in ("pickup", "delivery"):
        stated, said = row[site + "Hours"], label.get(site + "_hours") or {}
        if stated is None:
            out[site + "Hours"] = None
            continue
        opens, closes = watch.minute_of(said.get("opens")), watch.minute_of(said.get("closes"))
        out[site + "Hours"] = [stated[0] if opens is None else opens, stated[1] if closes is None else closes]
    return out


def load(source: str, held_out: bool | None, new: bool) -> list[dict]:
    if source == "truth":
        data = notecheck.rows()
    elif source.endswith(".gz") and "events" in Path(source).name:  # a live week's log: its price requests with a note
        data = []
        with gzip.open(source, "rt", encoding="utf-8") as f:
            for line in f:
                event = json.loads(line)
                request = event.get("request") if event.get("kind") == "price_request" else None
                if request and request.get("note"):
                    data.append({**notecheck.stated(Path(source).parent.name, request), "deadline": max(o["deadline"] for o in request["options"])})
    else:
        data = [json.loads(line) for line in open(source, encoding="utf-8")]
    if held_out is not None:
        data = [row for row in data if notecheck.held_out(row["text"]) == held_out]
    if new:
        known = {pattern(row["text"]) for row in notecheck.rows()}
        data = [row for row in data if pattern(row["text"]) not in known]
    return data


def pattern(text: str) -> str:
    return re.sub(r"\d", "0", text.lower())


def labels() -> dict[str, dict]:
    if not LABELS.exists():
        return {}
    out = {}
    for line in open(LABELS, encoding="utf-8"):
        answer = json.loads(line)
        if answer.get("label") and answer["model"] == MODEL:
            out[answer["text"]] = answer
    return out


def label(data: list[dict], limit: int, workers: int) -> None:
    key = os.environ["ANTHROPIC_API_KEY"]
    done = labels()
    labelled = {pattern(text) for text in done}
    texts = list({pattern(row["text"]): row["text"] for row in data if pattern(row["text"]) not in labelled}.values())  # one text a wording
    random.Random(0).shuffle(texts)  # a sample across seeds, the same one each run
    texts = texts[:limit]
    print(f"{len(texts)} texts to label with {MODEL} ({len(done)} labelled before)", file=sys.stderr)
    LABELS.parent.mkdir(parents=True, exist_ok=True)
    tokens, failed = Counter(), 0
    with ThreadPoolExecutor(workers) as pool, open(LABELS, "a", encoding="utf-8") as out:
        for n, answer in enumerate(pool.map(lambda t: ask(t, key), texts), 1):
            out.write(json.dumps(answer, ensure_ascii=False) + "\n")
            out.flush()
            failed += "error" in answer
            tokens.update({k: v for k, v in (answer.get("usage") or {}).items() if isinstance(v, int)})
            if n % 50 == 0 or n == len(texts):
                print(f"{n}/{len(texts)} labelled, {failed} failed; tokens " + ", ".join(f"{k} {v}" for k, v in tokens.items() if isinstance(v, int)),
                      file=sys.stderr)


def report(data: list[dict], show: str | None, n: int) -> None:
    """With a reveal: the model's misses against it. Without: where the rules and the label disagree."""
    known = labels()
    data = [row for row in data if row["text"] in known]
    with_truth = bool(data) and "truth" in data[0]
    counts = {field: [0, 0] for field in notecheck.FIELDS}
    rules_counts = {field: [0, 0] for field in notecheck.FIELDS}
    examples = Counter()
    for row in data:
        said = truth_of(known[row["text"]]["label"], row)
        # With a reveal, the label is scored as a reading; without one, the label stands in for the truth and the rules are scored.
        scored = notecheck.score(row, reading=said) if with_truth else notecheck.score(row, truth=said)
        for field, (right, read, real) in scored.items():
            counts[field][0] += 1
            counts[field][1] += not right
            if not right and field == show and not notecheck.held_out(row["text"]):
                examples[(row["text"], notecheck.say(field, read), notecheck.say(field, real))] += 1
        if with_truth:
            for field, (right, _, _) in notecheck.score(row).items():
                rules_counts[field][0] += 1
                rules_counts[field][1] += not right
    if with_truth:
        print(f"{len(data)} won notes with a reveal and a {MODEL} label: misses against the reveal, the model's and the rules'")
        for field in notecheck.FIELDS:
            (k, m), (rk, rm) = counts[field], rules_counts[field]
            print(f"  {field:<15} model {m:>4}/{k:<5} {m / max(1, k):6.2%}   rules {rm:>4}/{rk:<5} {rm / max(1, rk):6.2%}")
    else:
        print(f"{len(data)} notes without a reveal, labelled by {MODEL}: notes where the rules disagree with the label")
        for field in notecheck.FIELDS:
            k, m = counts[field]
            print(f"  {field:<15} {m:>5}/{k:<6} {m / max(1, k):6.2%}")
    if show:
        side = ("model", "reveal") if with_truth else ("rules", "label")
        print(f"\n{show}, dev split only: {side[0]} read, {side[1]} says")
        for (text, read, real), k in examples.most_common(n):
            print(f"  x{k:<3} {side[0]} {read}  {side[1]} {real} | {text[:300]}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["label", "report"])
    parser.add_argument("source", help="'truth' (note-truth.jsonl.gz), a jsonl of rows such as unlabelled.jsonl, or a live week's events.jsonl.gz")
    split = parser.add_mutually_exclusive_group()
    split.add_argument("--held-out", dest="held_out", action="store_true", default=None, help="only the held-out split")
    split.add_argument("--dev", dest="held_out", action="store_false", help="only the dev split")
    parser.add_argument("--new", action="store_true", help="only wordings that no won note has")
    parser.add_argument("--limit", type=int, default=500, help="label: at most this many new texts")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--show", choices=notecheck.FIELDS, help="report: list the disagreements on this field")
    parser.add_argument("-n", type=int, default=20)
    args = parser.parse_args()
    data = load(args.source, args.held_out, args.new)
    if args.command == "label":
        label(data, args.limit, args.workers)
    else:
        report(data, args.show, args.n)


if __name__ == "__main__":
    main()
