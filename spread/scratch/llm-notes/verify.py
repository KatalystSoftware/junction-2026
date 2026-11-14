"""Offline test of the live desk's note check (spreadlab/watch.py) against the reveal: the model gets each note with
what the rules read and answers yes or no. No world is played. From spread/:

    PYTHONPATH=. uv run python scratch/llm-notes/verify.py draw            # random.jsonl: 300 won notes drawn at random, not in sample.jsonl
    PYTHONPATH=. uv run python scratch/llm-notes/verify.py run sample [n] [step]   # asks the model on sample.jsonl (NVIDIA_API_KEY); appends to verify-answers.jsonl
    PYTHONPATH=. uv run python scratch/llm-notes/verify.py run random
    PYTHONPATH=. uv run python scratch/llm-notes/verify.py score           # false no's, what a no finds, what the safe fixes mend and break
    PYTHONPATH=. uv run python scratch/llm-notes/verify.py misses          # every won note in the archive: the facts the rules leave out, by kind

`draw` and `misses` need rows.jsonl from extract.py; `run` and `score` need only the committed jsonl files here.
"""
import sys, os, json, time, random, collections, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from llm_test import flags  # the facts that the reveal says a note stated
from spreadlab import notes, watch
D = os.path.dirname(os.path.abspath(__file__)) + "/"
ANSWERS = D + "verify-answers.jsonl"
OTHER = {"deadline": "deadline", "pickup hours": "pickup_hours", "delivery hours": "delivery_hours", "summer tyres": "summer_tyres"}


def rows_of(name):
    return [json.loads(l) for l in open(D + name + ".jsonl")]


def draw():
    from spreadlab.server import data_dir
    known = {r["note"]["text"] for r in rows_of("sample")}
    rows = [r for r in map(json.loads, open(data_dir() / "llm-notes" / "rows.jsonl")) if r["note"] and len(r["truth"]) == 1 and r["note"]["text"] not in known]
    random.seed(11)
    picked, texts = [], set()
    for r in random.sample(rows, 2000):
        if r["note"]["text"] not in texts and len(picked) < 300:
            texts.add(r["note"]["text"]); picked.append({**r, "flags": sorted(flags(r))})
    with open(D + "random.jsonl", "w") as f:
        for r in picked: f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(len(picked), collections.Counter(x for r in picked for x in r["flags"]))


def run(name, limit=10**6, step=1, gap=2.5):
    done = {a["text"] for a in map(json.loads, open(ANSWERS)) if a["answer"] is not None and a["model"] == watch.MODEL} if os.path.exists(ANSWERS) else set()  # a refused call goes again
    key = os.environ[watch.KEY]
    for r in rows_of(name)[:limit:step]:  # every step-th of the first limit notes
        text = r["note"]["text"]
        if text in done: continue
        started = time.monotonic()
        read = watch.reading(notes.read(r["note"], r["arrivedAt"]), r["arrivedAt"])
        for attempt in range(4):
            answer = watch.ask(text, read, watch.stated(r, r["deadline"]), key, timeout=30)
            if answer.get("error") not in ("HTTP 429", "HTTP 503", "timeout", "TimeoutError", "URLError"): break
            time.sleep(10 * (attempt + 1))
        with open(ANSWERS, "a") as f:
            f.write(json.dumps({"model": watch.MODEL, "text": text, "rules": read, "attempts": attempt + 1, **answer}, ensure_ascii=False) + "\n")
        done.add(text)
        time.sleep(max(0, gap - (time.monotonic() - started)))
    print("done", name)


def truth(r):
    """What the rules missed, by the reveal: ready, no_plates, manual when the rules read them wrong, and the other facts the note stated."""
    f, t, leg = notes.read(r["note"], r["arrivedAt"]), r["truth"][0], r["legs"][0]
    start = leg["pickup"]["window"]["from"]
    real = max(t["readyAt"], t["releasedAt"] or 0)
    missed = set()
    if max(start, f.pickup_from) != max(start, real): missed.add("ready")
    if f.plates != t["needsPlates"]: missed.add("no_plates")
    if f.manual != t["manualGearbox"]: missed.add("manual")
    missed |= {OTHER[x] for x in flags(r) if x in OTHER}
    return f, missed, (start, real, t["needsPlates"], t["manualGearbox"])


def score():
    answers = {}
    for l in open(ANSWERS):
        a = json.loads(l)
        if a["model"] == watch.MODEL: answers[a["text"]] = a  # the model of NOTE_MODEL
    for name in ("random", "sample"):
        rows = [r for r in rows_of(name) if r["note"]["text"] in answers]
        c, named, by_truth, examples = collections.Counter(), collections.Counter(), collections.defaultdict(collections.Counter), collections.defaultdict(list)
        for r in rows:
            a = answers[r["note"]["text"]]
            f, missed, (start, real, plates, manual) = truth(r)
            three = not missed & {"ready", "no_plates", "manual"}
            complete = not missed
            c["notes"] += 1; c["complete"] += complete; c["three right"] += three
            if a["answer"] is None: c["unanswered"] += 1; continue
            c["answered"] += 1; c["answered complete"] += complete
            raw = a["answer"] == "no"
            c["raw no when complete"] += raw and complete
            problems = watch.material(a["problems"], f, r, r["deadline"]) if raw else []  # as the live watcher counts a no
            no = any(p["fact"] != "other" for p in problems)  # as the live watcher counts a no; "other" alone is a review note
            c["no only other"] += bool(problems) and not no and complete
            a = {**a, "problems": problems}
            facts = {p["fact"] for p in problems}
            c["no"] += no
            if complete: c["no when complete"] += no
            else: c["no when incomplete"] += no
            for x in facts: named[x] += 1
            for x in missed: by_truth[x]["stated"] += 1; by_truth[x]["no"] += no; by_truth[x]["named"] += x in facts
            if complete and no and len(examples["false no"]) < 12: examples["false no"].append((r["note"]["text"], a["problems"]))
            fix = watch.safe_fix(a["problems"], f, r) if no else {}
            if fix:
                after = (max(start, f.pickup_from, fix.get("pickupFrom", 0)) == max(start, real), (f.plates or fix.get("plates", False)) == plates,
                         (f.manual or fix.get("manual", False)) == manual)
                right = all(after)
                c["fixed"] += 1; c["fix mends"] += right and not three; c["fix breaks"] += three and not right; c["fix leaves wrong"] += not three and not right
                for k, v in fix.items():
                    ok = {"pickupFrom": after[0], "plates": after[1], "manual": after[2]}[k]
                    c[f"fix {k} {'right' if ok else 'wrong'}"] += 1
                if three and not right: examples["fix breaks"].append((r["note"]["text"], fix, a["problems"]))
        ok = [answers[r["note"]["text"]]["seconds"] for r in rows if answers[r["note"]["text"]].get("seconds") is not None and answers[r["note"]["text"]]["answer"] is not None]
        print(f"== {name}: {c['notes']} notes, the rules' reading complete by the reveal on {c['complete']}, ready/plates/manual right on {c['three right']}; unanswered {c['unanswered']}")
        n_complete, n_incomplete = c["answered complete"], c["answered"] - c["answered complete"]
        print(f"   the model's raw no on {c['raw no when complete']}/{n_complete} complete readings ({c['raw no when complete'] / max(1, n_complete):.1%})")
        print(f"   a no that names a fact the desk lacks: false no {c['no when complete']}/{n_complete} ({c['no when complete'] / max(1, n_complete):.1%}) of the complete readings, "
              f"and {c['no only other']} more naming only 'other'; no on {c['no when incomplete']}/{n_incomplete} ({c['no when incomplete'] / max(1, n_incomplete):.1%}) of the incomplete ones")
        print(f"   safe fixes {c['fixed']}: mend {c['fix mends']}, break {c['fix breaks']}, leave a wrong reading wrong {c['fix leaves wrong']}; "
              + ", ".join(f"{k[4:]} {v}" for k, v in sorted(c.items()) if k.startswith("fix ") and k.split()[1] in ("pickupFrom", "plates", "manual")))
        print("   by what the rules missed (reveal): " + "; ".join(f"{x} {v['stated']}, a no on {v['no']}, named {v['named']}" for x, v in sorted(by_truth.items(), key=lambda kv: -kv[1]["stated"])))
        print("   facts the model named: " + ", ".join(f"{x} {n}" for x, n in named.most_common()))
        if ok: print(f"   seconds median {statistics.median(ok):.2f}, p95 {sorted(ok)[int(.95 * len(ok))]:.2f}, max {max(ok):.2f}")
        for kind, items in examples.items():
            print(f"   {kind}:")
            for item in items[:8]: print("     ", json.dumps(item, ensure_ascii=False)[:260])


def misses():
    """Every won note of the archive: which facts the rules leave out or read wrong, by the reveal."""
    from spreadlab.server import data_dir
    rows = [r for r in map(json.loads, open(data_dir() / "llm-notes" / "rows.jsonl")) if r["note"] and len(r["truth"]) == 1]
    c = collections.Counter()
    for r in rows:
        _, missed, _ = truth(r)
        c.update(missed); c["any"] += bool(missed)
    weeks = len({r["seed"] for r in rows})
    print(f"{len(rows)} won notes with one car in {weeks} weeks; the rules' reading is incomplete on {c['any']} ({c['any'] / len(rows):.1%}):")
    for x, n in c.most_common():
        if x != "any": print(f"   {x:15s} {n:6d}  {n / len(rows):6.2%} of won notes, {n / weeks:5.1f} a week")


if __name__ == "__main__":
    {"draw": draw, "run": lambda: run(sys.argv[2], *map(int, sys.argv[3:5])), "score": score, "misses": misses}[sys.argv[1]]()
