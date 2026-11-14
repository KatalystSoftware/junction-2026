"""Offline test of the note fallback (spreadlab/fallback.py) against the reveal. No world is played. From spread/:

    PYTHONPATH=. uv run python scratch/note-actions/eval.py trigger dev           # how often it would ask, and which misses it catches
    PYTHONPATH=. uv run python scratch/note-actions/eval.py run held [n]          # asks the model on the split's triggered notes (cached)
    PYTHONPATH=. uv run python scratch/note-actions/eval.py score held            # fixed and broken fields, wrong actions, latency, € a week
    PYTHONPATH=. uv run python scratch/note-actions/eval.py inject held           # notes in wording the archive has not seen, with known facts

Splits, by wording as the note-check thread draws them (spreadlab/notecheck.held_out): a note is held out when the
sha256 of its lower-cased text with digits as 0 is 0 modulo 5. `dev` is the rest, which the prompt, the trigger and
the rule candidates may look at; `held` is scored, never tuned on.
Needs data/llm-notes/rows.jsonl and notes.jsonl from scratch/llm-notes/extract.py. The model comes from NOTE_ACTIONS_MODEL.
"""
import sys, os, json, random, collections, statistics, re, hashlib
from concurrent.futures import ThreadPoolExecutor
from spreadlab import fallback, notes, watch
from spreadlab.server import data_dir

D = os.path.dirname(os.path.abspath(__file__)) + "/"
DATA = data_dir() / "llm-notes"
# What a field read wrong costs, in euros an order (scratch/llm-notes/upside.py and rule_cost.py on 401 weeks of
# steep-notes-offers-8, which reads no limits): failed visits, waiting and late refunds over the orders with the fact.
# A wrong action is taken to cost what a miss of its field costs: a post to the wrong hours or deadline. Haste has no truth.
EURO = {"ready": 19.0, "plates": 19.0, "manual": 19.0, "summer": 3.3, "deadline": 7.8, "pickup_hours": 13.6, "delivery_hours": 15.3}
WON_NOTES_A_WEEK = 110  # 43,915 won notes in those 401 weeks
FIELDS = ("ready", "plates", "manual", "summer", "deadline", "pickup_hours", "delivery_hours")
ACTION_FIELD = {"delay": "ready", "plates": "plates", "manual": "manual", "summer_tyres": "summer", "deadline": "deadline",
                "pickup_hours": "pickup_hours", "delivery_hours": "delivery_hours"}


def held_out(text):
    return int(hashlib.sha256(re.sub(r"\d", "0", text.lower()).encode()).hexdigest(), 16) % 5 == 0


def rows_of(split):
    return [r for r in map(json.loads, open(DATA / "rows.jsonl")) if r["note"] and len(r["truth"]) == 1 and held_out(r["note"]["text"]) == (split == "held")]


def vocabulary(split):
    """The archive's words and sentences without the held-out wordings, so they read as new as in a new week."""
    words, patterns = set(), set()
    for line in open(DATA / "notes.jsonl"):
        n = json.loads(line)
        if held_out(n["note"]["text"]):
            continue
        words |= watch.words(n["note"]["text"])
        patterns |= {watch.pattern_hash(s) for s in watch.sentences(n["note"]["text"])}
    return watch.Vocabulary({"words": sorted(words), "patterns": sorted(patterns), "topics": {}})


def msgs_of(r, facts, limits):
    """The fallback's prompt for a row, as the desk builds it (fallback.Decision)."""
    return fallback.messages(r["note"]["text"], fallback.reading(facts, limits, r["arrivedAt"], notes.summer_tyres(r["note"])), watch.stated(r, r["deadline"]))


def hours_of(stated, noted):
    """Weekday hours as the desk posts them: the stated ones cut to the note's (0 is as stated)."""
    if not stated:
        return None
    return (max(stated["opens"], noted[0]), min(stated["closes"], noted[1] or 24 * 60))


def state(r, facts, limits, fix=None):
    """Each field as the desk would post it, with the fallback's fix merged as the desk merges it."""
    fix, leg = fix or {}, r["legs"][0]
    limits = fallback.merge(limits, fix)
    start = leg["pickup"]["window"]["from"]
    return {"ready": max(start, facts.pickup_from, fix.get("pickupFrom", 0)), "plates": facts.plates or fix.get("plates", False),
            "manual": facts.manual or fix.get("manual", False), "summer": notes.summer_tyres(r["note"]) or bool(fix.get("summer")),
            "deadline": min(r["deadline"], limits.deadline or r["deadline"]),
            "pickup_hours": hours_of(leg["pickup"]["hours"], limits.pickup_hours), "delivery_hours": hours_of(leg["delivery"]["hours"], limits.delivery_hours)}


def truth(r):
    t, leg = r["truth"][0], r["legs"][0]
    h = lambda x: (x["opens"], x["closes"]) if x else None
    return {"ready": max(leg["pickup"]["window"]["from"], t["readyAt"], t["releasedAt"] or 0), "plates": t["needsPlates"], "manual": t["manualGearbox"],
            "summer": t["summerTyres"], "deadline": min(r["deadline"], t["noteDeadline"] or r["deadline"]),
            "pickup_hours": h(t["pickupHours"]) if leg["pickup"]["hours"] else None, "delivery_hours": h(t["deliveryHours"]) if leg["delivery"]["hours"] else None}


def prepare(r, vocab):
    facts, limits = notes.read(r["note"], r["arrivedAt"]), notes.limits(r["note"], r["arrivedAt"])
    news = vocab.score(r["note"]["text"])
    why = fallback.trigger(r["note"]["text"], r["arrivedAt"], facts, limits, news)
    return facts, limits, why


def prepared(split):
    """Each row of the split with the rules' reading and the trigger, kept on disk: reading 50,000 notes takes minutes."""
    import pickle
    path = DATA.parent / "note-actions" / f"prepared-{split}.pickle"
    if path.exists():
        return pickle.load(open(path, "rb"))
    rows, vocab = rows_of(split), vocabulary(split)
    out = [(r, *prepare(r, vocab)) for r in rows]
    path.parent.mkdir(parents=True, exist_ok=True)
    pickle.dump(out, open(path, "wb"))
    return out


def trigger(split):
    rows, vocab = rows_of(split), vocabulary(split)
    c, miss_in, miss_all = collections.Counter(), collections.Counter(), collections.Counter()
    for r in rows:
        facts, limits, why = prepare(r, vocab)
        rules, real = state(r, facts, limits), truth(r)
        wrong = {f for f in FIELDS if rules[f] != real[f]}
        c["notes"] += 1; c["asked"] += bool(why)
        for w in why: c["why " + w.split(":")[0]] += 1
        for f in wrong:
            miss_all[f] += 1; miss_in[f] += bool(why)
        c["any wrong"] += bool(wrong); c["any wrong asked"] += bool(wrong) and bool(why)
    print(f"{split}: {c['notes']} won notes; the trigger asks on {c['asked']} ({c['asked'] / c['notes']:.1%}); "
          f"the rules are wrong on {c['any wrong']}, of which {c['any wrong asked']} asked ({c['any wrong asked'] / max(1, c['any wrong']):.0%})")
    print("   reasons: " + ", ".join(f"{k[4:]} {v}" for k, v in c.items() if k.startswith("why ")))
    for f in FIELDS:
        print(f"   {f:15s} rules wrong {miss_all[f]:5d} ({miss_all[f] / c['notes']:.2%}), asked on {miss_in[f]:5d} ({miss_in[f] / max(1, miss_all[f]):.0%})")


def ask_all(split, limit=10 ** 9, workers=4):
    rows = list(prepared(split))
    random.seed(3); random.shuffle(rows)
    todo, wrong = [], []
    for r, facts, limits, why in rows:
        if why:
            rules, real = state(r, facts, limits), truth(r)
            (wrong if any(rules[f] != real[f] for f in FIELDS) else todo).append((r, facts, limits))
    todo = wrong + todo[:max(0, limit - len(wrong))]  # every miss that the trigger asks on, then a random draw of the rest
    cache = fallback.Cache(DATA.parent / "note-actions" / "cache.jsonl")
    def one(item):
        r, facts, limits = item
        msgs = msgs_of(r, facts, limits)
        return cache.ask(msgs)
    with ThreadPoolExecutor(workers) as pool:
        answers = list(pool.map(one, todo))
    errors = collections.Counter(a.get("error") for a in answers)
    print(f"asked {len(todo)} ({sum(a.get('cached', False) for a in answers)} cached); errors {dict(errors)}")


def score(split, rows=None, label=None):
    rows = rows or prepared(split)
    cache = fallback.Cache(DATA.parent / "note-actions" / "cache.jsonl")
    c, per = collections.Counter(), collections.defaultdict(collections.Counter)
    seconds, examples, why_of = [], collections.defaultdict(list), collections.defaultdict(collections.Counter)
    only = os.environ.get("TRIGGERS")  # e.g. "new wording": score only the asks that version 4's trigger would make
    for r, facts, limits, why in rows:
        why = [w for w in why if not only or w in only.split(",")]
        rules, real = state(r, facts, limits), truth(r)
        c["notes"] += 1
        for f in FIELDS:
            per[f]["rules wrong"] += rules[f] != real[f]
        if not why:
            continue
        msgs = msgs_of(r, facts, limits)
        key = cache.key(msgs)
        clean = all(rules[f] == real[f] for f in FIELDS)  # the rows that `run` draws a sample of; those with a miss are all asked
        c["triggered clean"] += clean
        if key not in cache.answers:
            c["not asked yet"] += 1; continue
        c["asked clean"] += clean
        a = cache.answers[key]
        c["asked"] += 1
        if a.get("seconds") is not None: seconds.append(a["seconds"])
        late = (a.get("seconds") or 0) > fallback.HOLD
        actions = fallback.parse(a.get("content")) if not a.get("error") else None
        if a.get("error") or actions is None:
            c["error " + str(a.get("error") or "unreadable")] += 1; continue
        c["late"] += late
        kept, dropped = fallback.vet(actions, r["note"]["text"], r, r["deadline"], facts, limits)
        for d in dropped: c["dropped " + d["why"]] += 1
        fix = fallback.fix_of(kept, fallback.RISKY)  # every action as if it acted; the risky ones are reported apart
        after = state(r, facts, limits, fix)
        for a_ in kept:
            per[ACTION_FIELD.get(a_["action"], a_["action"])]["actions"] += 1
        for f in FIELDS:
            if after[f] == rules[f]:
                continue
            ok_before, ok_after = rules[f] == real[f], after[f] == real[f]
            outcome = "fixed" if ok_after and not ok_before else "broken" if ok_before else "still wrong"
            weight = 1 if not clean else None  # scaled below, by the share of clean rows asked
            per[f][outcome + (" clean" if clean else "")] += 1
            per[f]["changed"] += 1
            for w in why: why_of[w.split(":")[0]][f"{f} {outcome}"] += 1
            per[f]["late " + outcome] += late
            if outcome != "fixed" and len(examples[f]) < 6:
                examples[f].append((outcome, r["note"]["text"][:140], [k for k in kept if ACTION_FIELD.get(k["action"]) == f]))
        if any(k["action"] == "urgent" for k in kept):
            per["urgent"]["actions"] += 1; per["urgent"]["with a note deadline"] += r["truth"][0]["noteDeadline"] is not None
    scale = c["triggered clean"] / max(1, c["asked clean"])  # the clean rows asked stand for all the clean rows the trigger fires on
    week = WON_NOTES_A_WEEK / c["notes"]
    print(f"== {label or split}: {c['notes']} won notes, asked {c['asked']}, " + ", ".join(f"{k} {v}" for k, v in sorted(c.items()) if k not in ("notes", "asked"))
          + f"; clean rows weighted x{scale:.2f}")
    print(f"   {'field':15s} {'rules wrong':>11s} {'actions':>8s} {'fixed':>6s} {'broken':>7s} {'still wrong':>11s}  {'wrong actions':>14s}  {'€ saved/wk':>10s} {'€ lost/wk':>9s}")
    total = [0.0, 0.0]
    for f in FIELDS + ("urgent",):
        p = per[f]
        broken = p["broken"] + p["broken clean"] * scale
        wrong = broken + p["still wrong"]
        changed = p["fixed"] + broken + p["still wrong"]
        saved, lost = p["fixed"] * EURO.get(f, 0) * week, broken * EURO.get(f, 0) * week
        total[0] += saved; total[1] += lost
        print(f"   {f:15s} {p['rules wrong']:11d} {p['actions']:8d} {p['fixed']:6d} {broken:7.1f} {p['still wrong']:11d}  "
              f"{wrong:6.1f}/{changed:<6.1f}({wrong / max(1, changed):.0%})  {saved:10.2f} {lost:9.2f}"
              + (f"  [{p['with a note deadline']} of {p['actions']} with a note deadline]" if f == "urgent" else ""))
    print(f"   € a week at {WON_NOTES_A_WEEK} won notes: saved {total[0]:.2f}, lost {total[1]:.2f}, net {total[0] - total[1]:+.2f}")
    for w, outcomes in why_of.items():
        print(f"   trigger '{w}': " + ", ".join(f"{k} {v}" for k, v in sorted(outcomes.items())))
    if seconds:
        s = sorted(seconds)
        print(f"   seconds: median {statistics.median(s):.2f}, p95 {s[int(.95 * len(s))]:.2f}, max {s[-1]:.2f}; over {fallback.HOLD} s {sum(x > fallback.HOLD for x in s)}/{len(s)} "
              f"({sum(x > fallback.HOLD for x in s) / len(s):.1%})")
    for f, xs in examples.items():
        print(f"   {f}:")
        for x in xs: print("     ", json.dumps(x, ensure_ascii=False)[:300])
    return c, per


# Notes in wording that the archive has not seen, each stating facts with a known truth: {day} and {time} are filled
# in, and the truth is set on a held-out request. Made up; the prompt's shots share no words with them.
INJECT = [
    ("Drop-off point stops taking vehicles at {hh} on weekdays.", {"delivery_closes": True}),
    ("Our yard locks the gate at {hh} sharp, collect before that.", {"pickup_closes": True}),
    ("Ostajalle luvattu, auton oltava määränpäässä {dayfi} klo {hh}.", {"deadline": True}),
    ("Slutkunden väntar, bilen ska vara hos dem {daysv} kl {hh}.", {"deadline": True}),
    ("Tyres are the summer set still, no studs.", {"summer": True}),
    ("Sommarhjulen sitter kvar på bilen.", {"summer": True}),
    ("Rekisteritunnukset poistettu, tuokaa siirtokilvet.", {"plates": True}),
    ("Three-pedal car, automatic-only drivers can't take it.", {"manual": True}),
    ("Hallitie luovuttaa auton vasta {dayfi} klo {hh} jälkeen.", {"ready": True}),
    ("Workshop releases the car {dayen} after {hh}, not earlier.", {"ready": True}),
    ("Vastaanottava liike on auki vain {hh}:een saakka arkipäivisin.", {"delivery_closes": True}),
    ("Remember the coffee, see you soon!", {}),
    ("Huolto katsastaa ensin, kuljettaja voi soittaa portilta.", {}),
    ("Pls park it near the wash bay, the lads will sort it.", {}),
]


def inject(split):
    rows = [r for r in rows_of(split) if r["legs"][0]["pickup"]["hours"] and r["legs"][0]["delivery"]["hours"]]
    random.seed(5); random.shuffle(rows)
    vocab = vocabulary(split)
    made = []
    fi, sv, en = ["maanantaina", "tiistaina", "keskiviikkona", "torstaina", "perjantaina"], ["måndag", "tisdag", "onsdag", "torsdag", "fredag"], ["monday", "tuesday", "wednesday", "thursday", "friday"]
    for i, (template, says) in enumerate(INJECT * 6):
        r = json.loads(json.dumps(rows[i]))
        arrived, leg, t = r["arrivedAt"], r["legs"][0], r["truth"][0]
        t.update({"noteDeadline": None, "summerTyres": False, "needsPlates": False, "manualGearbox": False, "readyAt": 0, "releasedAt": None,
                  "pickupHours": leg["pickup"]["hours"], "deliveryHours": leg["delivery"]["hours"]})
        day = arrived // 1440 + 2  # two days on: a weekday name means 2 to 6 days after the request
        while day % 7 > 4: day += 1
        hh = 14 if i % 2 else 15
        text = template.format(hh=hh, dayfi=fi[day % 7], daysv=sv[day % 7], dayen=en[day % 7])
        if says.get("deadline"): t["noteDeadline"] = day * 1440 + hh * 60
        if says.get("ready"): t["readyAt"] = day * 1440 + hh * 60; leg["pickup"]["window"]["to"] = max(leg["pickup"]["window"]["to"], day * 1440 + 20 * 60); r["deadline"] = max(r["deadline"], day * 1440 + 22 * 60)
        if says.get("deadline"): r["deadline"] = max(r["deadline"], day * 1440 + 20 * 60)
        if says.get("summer"): t["summerTyres"] = True
        if says.get("plates"): t["needsPlates"] = True
        if says.get("manual"): t["manualGearbox"] = True
        if says.get("delivery_closes"): t["deliveryHours"] = {**leg["delivery"]["hours"], "closes": hh * 60}
        if says.get("pickup_closes"): t["pickupHours"] = {**leg["pickup"]["hours"], "closes": hh * 60}
        r["note"] = {"text": text}
        facts, limits = notes.read(r["note"], arrived), notes.limits(r["note"], arrived)
        r["why"] = fallback.trigger(text, arrived, facts, limits, vocab.score(text))
        made.append(r)
    print(f"injected {len(made)} notes; the trigger fires on {sum(bool(r['why']) for r in made)}")
    if "--ask" in sys.argv:
        cache = fallback.Cache(DATA.parent / "note-actions" / "cache.jsonl")
        def one(r):
            facts, limits = notes.read(r["note"], r["arrivedAt"]), notes.limits(r["note"], r["arrivedAt"])
            return cache.ask(msgs_of(r, facts, limits))
        with ThreadPoolExecutor(6) as pool:
            list(pool.map(one, [r for r in made if r["why"]]))
    score(split, rows=[(r, notes.read(r["note"], r["arrivedAt"]), notes.limits(r["note"], r["arrivedAt"]), r["why"]) for r in made],
          label=f"injected new wording on {split} requests")


if __name__ == "__main__":
    command, split = sys.argv[1], sys.argv[2]
    {"trigger": lambda: trigger(split), "run": lambda: ask_all(split, int(sys.argv[3]) if len(sys.argv) > 3 else 10 ** 9),
     "score": lambda: score(split), "inject": lambda: inject(split)}[command]()
