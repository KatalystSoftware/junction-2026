"""Self-healing of the note rules: the cases that the fallback handled become candidate rules for notes.py, and a
candidate is admitted only when it passes every gate. Offline, between runs. From spread/:

    PYTHONPATH=. uv run python scratch/note-actions/heal.py cases [rules]       # dev cases: notes the rules read wrong, with the fallback's actions
    PYTHONPATH=. uv run python scratch/note-actions/heal.py propose [rules]     # Opus groups them into rules (candidates.jsonl)
    PYTHONPATH=. uv run python scratch/note-actions/heal.py check [rules]      # the gates, rule by rule

`rules` is the module of the rules to heal: spreadlab.notes (the default), or notes_before, the rules before the
note-check thread's fixes (8ccb2b5^), to replay the loop on the misses that those fixes mended by hand.

A rule is an addition to one of the word lists or patterns that notes.py already has, never free code, so the gates
can apply it and the merge is ordinary code: words for a tag of WORDS or LIMIT_WORDS, a phrase of HOUR_CASES, or an
alternative of MANUAL or PLATES. The gates, on the reveal of the archive's won notes:

  1. every wording: no field misses more notes than with the current rules, and some field misses fewer;
  2. the held-out wordings (eval.held_out), which no candidate is derived from: no field worse; the gain there, against
     the gain on the dev wordings, tells a general rule from one dealer's quirk;
  3. the policy replays, once 1 and 2 pass: a sweep against the default (README, How to try an idea).

The cases come from the dev wordings only: the fallback's offline decisions (eval.py run dev) and any live
review.jsonl whose world's reveal is saved, where the rules' reading was wrong by the reveal.
"""
import sys, os, json, re, collections, importlib, urllib.request, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import eval as ev
from spreadlab import fallback, notes, watch

D = os.path.dirname(os.path.abspath(__file__)) + "/"
CASES, CANDIDATES = ev.DATA.parent / "note-actions" / "cases.jsonl", D + "candidates.jsonl"


def module(name="spreadlab.notes"):
    return importlib.reload(importlib.import_module(name))


def reading(reader, r):
    facts, limits = reader.read(r["note"], r["arrivedAt"]), reader.limits(r["note"], r["arrivedAt"])
    rules, real = ev.state(r, facts, limits), ev.truth(r)
    rules["summer"] = reader.summer_tyres(r["note"]) if hasattr(reader, "summer_tyres") else False
    return facts, limits, rules, real


def cases(name="spreadlab.notes"):
    """Dev won notes on which the rules are wrong by the reveal, with what the fallback did on them."""
    cache, reader = fallback.Cache(ev.DATA.parent / "note-actions" / "cache.jsonl"), module(name)
    out = []
    for r in ev.rows_of("dev"):
        facts, limits, rules, real = reading(reader, r)
        wrong = [f for f in ev.FIELDS if rules[f] != real[f] and f != "summer"]  # a new field needs new code, not a word: out of a rule's reach
        if not wrong:
            continue
        msgs = ev.msgs_of(r, facts, limits)
        answer = cache.answers.get(cache.key(msgs), {})
        kept, _ = fallback.vet(fallback.parse(answer.get("content")) or [], r["note"]["text"], r, r["deadline"], facts, limits)
        out.append({"text": r["note"]["text"], "wrong": wrong, "rules": {f: rules[f] for f in wrong}, "truth": {f: real[f] for f in wrong},
                    "fallback": [{k: v for k, v in a.items() if k in ("action", "cite", "opens", "closes", "day", "time")} for a in kept]})
    CASES.parent.mkdir(parents=True, exist_ok=True)
    with open(CASES, "w") as f:
        for c in out: f.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"{len(out)} dev cases: " + ", ".join(f"{k} {v}" for k, v in collections.Counter(w for c in out for w in c["wrong"]).most_common()))


PROMPT = """You maintain a rule-based reader of car transport notes (Finnish, Swedish, English; typos are common). Below are notes that the reader read wrong, by the true answer, and what a model fallback did with each. Propose rules that make the reader right on them next time, as additions to the reader's existing lists only:

- {"target": "WORDS", "key": <tag>, "add": [words]}: a word that means the tag. Tags: %(words)s. Current words: %(words_now)s
- {"target": "LIMIT_WORDS", "key": <kind>, "add": [words]}: words of the note's own limits. Kinds: %(limit)s. Current: %(limit_now)s
- {"target": "HOUR_CASES", "add": {"<phrase>": "HH.MM"}}: a Finnish hour phrase in a case form and the clock time it means, e.g. {"kahteen": "14.00"}. Current: %(hours_now)s
- {"target": "MANUAL", "add": [regex]} or {"target": "PLATES", "add": [regex]}: an alternative for the pattern that finds a manual gearbox or a car without plates. Current MANUAL: %(manual)s

Words of five letters or more already match with one typo (a letter changed, added, dropped or swapped), so add a typo only when it is two edits away. Prefer one general rule over many quirks. Each rule must not change notes it is not about. Answer with one JSON object: {"rules": [{"target": ..., "key": ..., "add": ..., "why": "a few words", "examples": [indexes of the notes it explains]}]}.

Notes:
%(cases)s"""


def propose(name="spreadlab.notes", model="claude-opus-5-5"):
    notes = module(name)
    rows = [json.loads(l) for l in open(CASES)]
    text = "\n".join(f"{i}. {json.dumps(c, ensure_ascii=False)}" for i, c in enumerate(rows))
    prompt = PROMPT % {"words": sorted(notes.WORDS), "words_now": json.dumps(notes.WORDS, ensure_ascii=False), "limit": sorted(notes.LIMIT_WORDS),
                       "limit_now": json.dumps(notes.LIMIT_WORDS, ensure_ascii=False), "hours_now": json.dumps(notes.HOUR_CASES, ensure_ascii=False),
                       "manual": notes.MANUAL.pattern, "cases": text}
    # Opus 5.5 refuses thinking off; adaptive thinking at low effort, as spreadlab.notelabel asks it.
    body = {"model": model, "max_tokens": 16000, "messages": [{"role": "user", "content": prompt}], "thinking": {"type": "adaptive"}, "output_config": {"effort": "low"}}
    started = time.monotonic()
    request = urllib.request.Request("https://api.anthropic.com/v1/messages", json.dumps(body).encode(),
                                     {"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01", "content-type": "application/json"})
    data = json.load(urllib.request.urlopen(request, timeout=600))
    content = next(c["text"] for c in data["content"] if c["type"] == "text")
    rules = json.loads(re.search(r"\{.*\}", content, re.S)[0])["rules"]
    with open(CANDIDATES, "w") as f:
        for rule in rules: f.write(json.dumps(rule, ensure_ascii=False) + "\n")
    print(f"{model}: {len(rules)} candidates in {time.monotonic() - started:.0f} s; tokens {data['usage']}")


def apply(rule, name="spreadlab.notes"):
    """A copy of the rules with the rule in it."""
    module = importlib.reload(importlib.import_module(name))
    target, add = rule["target"], rule["add"]
    if target in ("WORDS", "LIMIT_WORDS"):
        getattr(module, target)[rule["key"]] = getattr(module, target)[rule["key"]] + [w.lower() for w in add]
    elif target == "HOUR_CASES":
        module.HOUR_CASES.update(add)
        module.HOUR_CASE = re.compile(r"(?<!puoli )\b(" + "|".join(sorted(module.HOUR_CASES, key=len, reverse=True)) + r")\b")
    else:
        pattern = getattr(module, target)
        setattr(module, target, re.compile(pattern.pattern + "|" + "|".join(add)))
    return module


def touches(rule, text):
    """Whether the rule can change the reading of this note: it has a token one edit from an added word, or the pattern."""
    text = text.lower()
    if rule["target"] in ("WORDS", "LIMIT_WORDS"):
        tokens = set(notes.TOKEN.findall(text))
        return any(notes.near(t, w.lower()) for t in tokens for w in rule["add"])
    if rule["target"] == "HOUR_CASES":
        return any(phrase in text for phrase in rule["add"])
    return any(re.search(a, text) for a in rule["add"])


def misses(rows, reader):
    c = collections.Counter()
    for r in rows:
        _, _, rules, real = reading(reader, r)
        c.update(f for f in ev.FIELDS if rules[f] != real[f])
    return c


def check(name="spreadlab.notes", path=CANDIDATES):
    rules = [json.loads(l) for l in open(path)]
    rows = [r for r in map(json.loads, open(ev.DATA / "rows.jsonl")) if r["note"] and len(r["truth"]) == 1]
    for rule in rules:
        hit = [r for r in rows if touches(rule, r["note"]["text"])]
        held = [r for r in hit if ev.held_out(r["note"]["text"])]
        dev = [r for r in hit if not ev.held_out(r["note"]["text"])]
        before = {"dev": misses(dev, module(name)), "held": misses(held, module(name))}
        candidate = apply(rule, name)
        after = {"dev": misses(dev, candidate), "held": misses(held, candidate)}
        module(name)
        delta = {s: {f: after[s][f] - before[s][f] for f in ev.FIELDS if after[s][f] != before[s][f]} for s in ("dev", "held")}
        worse = [f"{s} {f} +{d}" for s in delta for f, d in delta[s].items() if d > 0]
        gain = sum(-d for s in delta for d in delta[s].values() if d < 0)
        verdict = "fails: " + ", ".join(worse) if worse else "no gain" if not gain else "passes gates 1 and 2"
        print(json.dumps({"rule": {k: rule[k] for k in ("target", "key", "add") if k in rule}, "notes touched": {"dev": len(dev), "held": len(held)},
                          "misses changed": delta, "held-out gain": -sum(d for d in delta["held"].values() if d < 0), "verdict": verdict}, ensure_ascii=False))



def rate(*names):
    """How often the fallback would ask, a share of the held-out won notes, under each version of the rules: it should
    fall as the rules heal. `notes_before+opus` is notes_before with every candidate that passed the gates."""
    import pickle
    rows, vocab = ev.rows_of("held"), ev.vocabulary("held")
    news = [vocab.score(r["note"]["text"]) for r in rows]
    for name in names or ("notes_before", "notes_before+opus", "spreadlab.notes"):
        base, opus = name.split("+")[0], name.endswith("+opus")
        reader = module(base)
        if opus:
            for rule in map(json.loads, open(CANDIDATES)):
                reader = apply_to(reader, rule)
        c = collections.Counter()
        for r, n in zip(rows, news):
            text, arrived = r["note"]["text"], r["arrivedAt"]
            limits = reader.limits(r["note"], arrived)
            said = watch.topics(text, arrived) & fallback.FIELDS
            summer = reader.summer_tyres(r["note"]) if hasattr(reader, "summer_tyres") else False
            why = [w for w, on in (("new wording", n["newWords"] or n["newSentences"]), ("summer tyres", "summer" in said and not summer),
                                   ("deadline or delivery unread", said & {"by", "delivery"} and not limits.deadline and limits.delivery_hours == (0, 0)),
                                   ("hours unread", said & {"closing", "hours"} and limits.pickup_hours == (0, 0) and limits.delivery_hours == (0, 0))) if on]
            c["asked"] += bool(why); c.update(why)
            _, _, rules, real = reading(reader, r)
            c["misses"] += any(rules[f] != real[f] for f in ev.FIELDS)
        print(f"{name:22s} asks on {c['asked']:5d} of {len(rows)} held-out won notes ({c['asked'] / len(rows):.1%}); rules wrong on {c['misses']}; "
              + ", ".join(f"{k} {v}" for k, v in c.items() if k not in ("asked", "misses")))
        module(base)


def apply_to(reader, rule):
    """`apply` on a module already loaded, so several rules stack."""
    target, add = rule["target"], rule["add"]
    if target in ("WORDS", "LIMIT_WORDS"):
        getattr(reader, target)[rule["key"]] = getattr(reader, target)[rule["key"]] + [w.lower() for w in add]
    elif target == "HOUR_CASES":
        reader.HOUR_CASES.update(add)
        reader.HOUR_CASE = re.compile(r"(?<!puoli )\b(" + "|".join(sorted(reader.HOUR_CASES, key=len, reverse=True)) + r")\b")
    else:
        setattr(reader, target, re.compile(getattr(reader, target).pattern + "|" + "|".join(add)))
    return reader


if __name__ == "__main__":
    {"cases": cases, "propose": propose, "check": check, "rate": rate}[sys.argv[1]](*sys.argv[2:])
