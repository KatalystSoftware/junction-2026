"""Offline test of an LLM note reader on archived notes, against the reveal. No world is played.
From spread/, with rows.jsonl from extract.py in the data folder (only `sample` needs it):

    PYTHONPATH=. uv run python scratch/llm-notes/llm_test.py sample                        # writes sample.jsonl: won orders with a note, drawn by fact
    PYTHONPATH=. uv run python scratch/llm-notes/llm_test.py run <model>[@on|@off] [n] [step] [gap]   # asks a model on NVIDIA's API (NVIDIA_API_KEY); appends to answers.jsonl
    PYTHONPATH=. uv run python scratch/llm-notes/llm_test.py score                         # the rules and each model against the reveal; writes score.json

`run` skips the notes a model has answered, takes every `step`-th note of the first `n`, and waits `gap` seconds between calls.
"""
import sys, os, json, time, random, re, collections, statistics, urllib.request
D = os.path.dirname(os.path.abspath(__file__)) + "/"  # sample.jsonl and answers.jsonl: committed, next to this file; score.json is not
DAYS = {"today": 0, "tomorrow": 1, "day_after_tomorrow": 2}
WEEK = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

SYSTEM = """You read a note that a Finnish car dealer wrote on a car transport request. Notes are in Finnish, Swedish or English, with abbreviations and typos. Extract only what the note states. Answer with one JSON object and nothing else.

Fields:
- "ready_day", "ready_time": the first time the car can be collected: when it is ready, or when it is handed over after payment. Not opening hours, not a time by which it must be collected, not a time that the note denies.
- "deadline_day", "deadline_time": the time by which the car must be at its destination.
- "pickup_opens", "pickup_closes": the opening hours of the pickup site, or the time by which the car must be collected.
- "delivery_opens", "delivery_closes": the hours of the receiving site at the destination.
- "no_plates": true when the car has no registration plates.
- "manual": true when the car has a manual gearbox.
- "summer_tyres": true when the car is on summer tyres or has no winter tyres on.

Days: "today", "tomorrow", "day_after_tomorrow", "mon", "tue", "wed", "thu", "fri", "sat", or null. A time with no day is "today". Give a weekday as the note names it; do not convert it.
Times: "HH:MM" on a 24-hour clock. Digits are the hour on a 24-hour clock unless am or pm follows. An hour written as a word is the working hour with that number, from 9 to 17: "kolmelta", "three" and "tre" are 15:00, "yhdeksältä" is 09:00, "kahdeltatoista" is 12:00. "Half three", "puoli kolme" and "halv tre" are 14:30: half an hour before three.
When the note corrects itself ("korjaus", "eiku", "ei kun", "sorry", "rättelse"), the correction counts. A corrected day keeps the earlier time, and a corrected time keeps the earlier day.
A field that the note does not state is null, or false for the three yes/no fields. Most notes state none: calls, keys, reference numbers and greetings are not facts."""
EMPTY = {"ready_day": None, "ready_time": None, "deadline_day": None, "deadline_time": None, "pickup_opens": None, "pickup_closes": None,
         "delivery_opens": None, "delivery_closes": None, "no_plates": False, "manual": False, "summer_tyres": False}
SHOTS = [  # made up, as the handbook's examples are
    ("Klar först på onsdag kl 12. Bilen saknar skyltar.", {"ready_day": "wed", "ready_time": "12:00", "no_plates": True}),
    ("Moi, auto valmis huomenna kolmelta, eiku ylihuomenna. Viite 55120.", {"ready_day": "day_after_tomorrow", "ready_time": "15:00"}),
    ("Must be at destination by tomorrow 5pm. Stick shift. Call 15 min before.", {"deadline_day": "tomorrow", "deadline_time": "17:00", "manual": True}),
    ("Nouto arkisin 9-15.30. Vastaanotto klo 16 asti. Vielä kesärenkaat.", {"pickup_opens": "09:00", "pickup_closes": "15:30", "delivery_closes": "16:00", "summer_tyres": True}),
    ("Avaimet tiskiltä, soita 20 min ennen. Kiitos!", {}),
    ("Maksun jälkeen, ei ennen klo 13.30. Haettava ennen puolta viittä.", {"ready_day": "today", "ready_time": "13:30", "pickup_closes": "16:30"}),
]


def messages(text):
    out = [{"role": "system", "content": SYSTEM}]
    for note, facts in SHOTS:
        out += [{"role": "user", "content": "Note: " + note}, {"role": "assistant", "content": json.dumps({**EMPTY, **facts}, ensure_ascii=False)}]
    return out + [{"role": "user", "content": "Note: " + text}]


def flags(r):
    t, leg = r["truth"][0], r["legs"][0]
    out = set()
    if max(t["readyAt"], t["releasedAt"] or 0) > leg["pickup"]["window"]["from"]: out.add("ready later")
    if t["needsPlates"]: out.add("plates")
    if t["manualGearbox"]: out.add("manual")
    if t["summerTyres"]: out.add("summer tyres")
    if t["noteDeadline"] is not None: out.add("deadline")
    if t["pickupHours"] != leg["pickup"]["hours"]: out.add("pickup hours")
    if t["deliveryHours"] != leg["delivery"]["hours"]: out.add("delivery hours")
    return out or {"none"}


def sample():
    from spreadlab import notes
    from spreadlab.server import data_dir
    rows = [r for r in map(json.loads, open(data_dir() / "llm-notes" / "rows.jsonl")) if r["note"] and len(r["truth"]) == 1]
    random.seed(7)
    random.shuffle(rows)
    rows.sort(key=lambda r: not r["seed"].startswith("fresh"))  # the seeds played last first; the sort is stable
    picked, texts = [], set()
    def take(r, why):
        if r["note"]["text"] not in texts:
            texts.add(r["note"]["text"]); picked.append({**r, "stratum": why, "flags": sorted(flags(r))})
            return True
    for r in rows:  # every note that the rules read wrong
        facts, t = notes.read(r["note"], r["arrivedAt"]), r["truth"][0]
        if max(r["legs"][0]["pickup"]["window"]["from"], facts.pickup_from) != max(t["readyAt"], t["releasedAt"] or 0) or facts.plates != t["needsPlates"] or facts.manual != t["manualGearbox"]:
            take(r, "rules wrong")
    for why, n in (("ready later", 60), ("plates", 30), ("manual", 30), ("summer tyres", 30), ("deadline", 40), ("pickup hours", 40), ("delivery hours", 40), ("none", 60)):
        k = 0
        for r in rows:
            if k == n: break
            if why in flags(r): k += bool(take(r, why))
    with open(D + "sample.jsonl", "w") as f:
        for r in picked: f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(len(picked), collections.Counter(r["stratum"] for r in picked), collections.Counter(r["seed"].rstrip("0123456789-") for r in picked))


def run(spec, limit, step=1, gap=1.7):
    model, _, think = spec.partition("@")
    extra = {"chat_template_kwargs": {"enable_thinking": think == "on"}} if think else {}
    done = {json.loads(l)["text"] for l in open(D + "answers.jsonl") if json.loads(l)["spec"] == spec} if os.path.exists(D + "answers.jsonl") else set()
    rows = [json.loads(l) for l in open(D + "sample.jsonl")][:limit:step]  # gap: seconds between calls; 1.7 is under the free tier's 40 a minute
    for r in rows:
        text = r["note"]["text"]
        if text in done: continue
        body = json.dumps({"model": model, "messages": messages(text), "temperature": 0, "max_tokens": 2000 if think == "on" else 200, **extra}).encode()
        for attempt in range(6):
            req = urllib.request.Request("https://integrate.api.nvidia.com/v1/chat/completions", body, {"Authorization": "Bearer " + os.environ["NVIDIA_API_KEY"], "Content-Type": "application/json"})
            started = time.monotonic()
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    d = json.load(resp)
                took = time.monotonic() - started
                rec = {"spec": spec, "text": text, "seconds": round(took, 3), "attempts": attempt + 1, "content": d["choices"][0]["message"].get("content"), "usage": d.get("usage")}
                break
            except urllib.error.HTTPError as e:
                rec = {"spec": spec, "text": text, "error": e.code, "attempts": attempt + 1}
                time.sleep(6 if e.code == 429 else 2)
            except Exception as e:
                rec = {"spec": spec, "text": text, "error": type(e).__name__, "attempts": attempt + 1}
        with open(D + "answers.jsonl", "a") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        time.sleep(max(0, gap - (time.monotonic() - started)))
    print("done", spec)


def minute(s):
    m = re.fullmatch(r"(\d{1,2})[:.](\d{2})", s.strip()) if isinstance(s, str) else None
    return int(m[1]) * 60 + int(m[2]) if m and int(m[1]) <= 24 and int(m[2]) < 60 else None


def when(day, clock, arrived_at):
    """The world minute of a day word and a clock time, by RULES.md; None when the answer gives no time."""
    m = minute(clock)
    if m is None: return None
    day = (day or "today").lower() if isinstance(day, str) or day is None else "today"
    if day in DAYS: offset = DAYS[day]
    elif day[:3] in WEEK: offset = (WEEK.index(day[:3]) - arrived_at // 1440 % 7 - 2) % 7 + 2
    else: return None
    return (arrived_at // 1440 + offset) * 1440 + m


def parse(content):
    try:
        return {**EMPTY, **json.loads(re.search(r"\{.*\}", content or "", re.S)[0])}
    except Exception:
        return None


def judge(r, a):
    """Which of the seven facts an answer has right. `a` is the parsed answer, or None for an answer that cannot be read (then: the request as stated)."""
    a = a or EMPTY
    t, leg = r["truth"][0], r["legs"][0]
    stated = leg["pickup"]["window"]["from"]
    out = {"ready": max(stated, when(a["ready_day"], a["ready_time"], r["arrivedAt"]) or 0) == max(t["readyAt"], t["releasedAt"] or 0),
           "plates": bool(a["no_plates"]) == t["needsPlates"], "manual": bool(a["manual"]) == t["manualGearbox"], "summer tyres": bool(a["summer_tyres"]) == t["summerTyres"],
           "deadline": when(a["deadline_day"], a["deadline_time"], r["arrivedAt"]) == t["noteDeadline"]}
    for side, key in (("pickup", "pickupHours"), ("delivery", "deliveryHours")):
        h, real = leg[side]["hours"], t[key]
        if h is None or real is None:  # a private address has no hours
            out[side + " hours"] = out[side + " closes"] = True
            continue
        opens, closes = minute(a[side + "_opens"]), minute(a[side + "_closes"])
        out[side + " hours"] = (opens if opens is not None else h["opens"], closes if closes is not None else h["closes"]) == (real["opens"], real["closes"])
        out[side + " closes"] = (closes if closes is not None else h["closes"]) == real["closes"]
    return out


def score():
    from spreadlab import notes
    rows = [json.loads(l) for l in open(D + "sample.jsonl")]
    by = collections.defaultdict(dict)
    for l in open(D + "answers.jsonl"):
        a = json.loads(l); by[a["spec"]][a["text"]] = a
    def rules(r):
        f = notes.read(r["note"], r["arrivedAt"])
        day = f.pickup_from // 1440 - r["arrivedAt"] // 1440
        return {**EMPTY, "ready_day": ["today", "tomorrow", "day_after_tomorrow"][day] if 0 <= day < 3 else WEEK[f.pickup_from // 1440 % 7] if f.pickup_from else None,
                "ready_time": f"{f.pickup_from % 1440 // 60:02d}:{f.pickup_from % 1440 % 60:02d}" if f.pickup_from else None, "no_plates": f.plates, "manual": f.manual}
    FACTS = ["ready", "plates", "manual", "summer tyres", "deadline", "pickup hours", "pickup closes", "delivery hours", "delivery closes"]
    result = {}
    for spec in ["rules"] + sorted(by):
        got = [(r, rules(r) if spec == "rules" else parse(by[spec][r["note"]["text"]].get("content"))) for r in rows if spec == "rules" or r["note"]["text"] in by[spec]]
        calls = [by[spec][r["note"]["text"]] for r, _ in got] if spec != "rules" else []
        right = collections.Counter(); total = collections.Counter(); wrong = collections.defaultdict(list)
        for r, a in got:
            j = judge(r, a)
            for fact in FACTS:
                has = {"ready": "ready later", "pickup closes": "pickup hours", "delivery closes": "delivery hours"}.get(fact, fact) in r["flags"]
                for group in (fact + (" stated" if has else " not stated"), fact + " all"):
                    total[group] += 1; right[group] += j[fact]
                if not j[fact]: wrong[fact].append((r["note"]["text"], {k: v for k, v in (a or {"unreadable": True}).items() if v}))
            three = j["ready"] and j["plates"] and j["manual"]
            total["notes"] += 1; right["three facts right"] += three; right["all seven right"] += all(v for k, v in j.items() if not k.endswith("closes"))
            if r["stratum"] == "rules wrong": total["rules-wrong notes"] += 1; right["rules-wrong notes"] += three
        if spec != "rules":
            same = [judge(r, rules(r)) for r, _ in got]
            print(f"== rules on the notes of the next model: three facts right {sum(j['ready'] and j['plates'] and j['manual'] for j in same)}/{len(same)}")
        print(f"== {spec}: {total['notes']} notes; ready, plates and manual all right {right['three facts right']}; all seven right {right['all seven right']}; the notes the rules read wrong {right['rules-wrong notes']}/{total['rules-wrong notes']}")
        for fact in FACTS:
            print(f"   {fact:15s} stated {right[fact + ' stated']}/{total[fact + ' stated']}   not stated {right[fact + ' not stated']}/{total[fact + ' not stated']}")
        if calls:
            ok = [c for c in calls if "seconds" in c]
            s = sorted(c["seconds"] for c in ok)
            print(f"   calls {len(calls)}, failed {len(calls) - len(ok)}, unreadable {sum(1 for r, a in got if a is None)}, retried {sum(c['attempts'] > 1 for c in calls)}; seconds median {statistics.median(s):.2f}, p95 {s[int(.95 * len(s))]:.2f}, max {s[-1]:.2f}; "
                  f"tokens in {statistics.mean(c['usage']['prompt_tokens'] for c in ok):.0f}, out {statistics.mean(c['usage']['completion_tokens'] for c in ok):.0f}, cached {statistics.mean((c['usage'].get('prompt_tokens_details') or {}).get('cached_tokens', 0) for c in ok):.0f}")
        result[spec] = {"right": dict(right), "total": dict(total), "wrong": {k: v for k, v in wrong.items()}}
    json.dump(result, open(D + "score.json", "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    if sys.argv[1] == "sample": sample()
    elif sys.argv[1] == "run": run(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 10**6, int(sys.argv[4]) if len(sys.argv) > 4 else 1, float(sys.argv[5]) if len(sys.argv) > 5 else 1.7)
    else: score()
