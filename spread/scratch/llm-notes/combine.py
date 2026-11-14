"""On the sample: the rules, each model, and the rules with the model as a second reader, on the three facts the rules read.
Also lists each model's errors, and weighs the strata to a week of the reference (won orders with a note)."""
import sys, json, collections
from spreadlab import notes
import llm_test as T
D = T.D
rows = [json.loads(l) for l in open(D + "sample.jsonl")]
by = collections.defaultdict(dict)
for l in open(D + "answers.jsonl"):
    a = json.loads(l); by[a["spec"]][a["text"]] = a
WEEK = {"none": 77.7, "ready later": 10.7, "plates": 2.4, "manual": 2.5, "summer tyres": 1.3, "deadline": 6.6, "pickup hours": 7.0, "delivery hours": 3.8}  # the reference's won orders a week with each fact
show = "--show" in sys.argv
for spec in sorted(by):
    n = collections.Counter(); per = collections.defaultdict(collections.Counter); errs = collections.defaultdict(list)
    for r in rows:
        ans = by[spec].get(r["note"]["text"])
        if ans is None: continue
        a = T.parse(ans.get("content"))
        f, t, leg = notes.read(r["note"], r["arrivedAt"]), r["truth"][0], r["legs"][0]
        stated, true_from = leg["pickup"]["window"]["from"], max(t["readyAt"], t["releasedAt"] or 0)
        rule_from = max(stated, f.pickup_from)
        llm_from = max(stated, T.when(a["ready_day"], a["ready_time"], r["arrivedAt"]) or 0) if a else stated
        lp, lm = bool(a and a["no_plates"]), bool(a and a["manual"])
        readers = {
            "rules": (rule_from == true_from, f.plates == t["needsPlates"], f.manual == t["manualGearbox"]),
            "model": (llm_from == true_from, lp == t["needsPlates"], lm == t["manualGearbox"]),
            "rules, and plates or manual when either says so": (rule_from == true_from, (f.plates or lp) == t["needsPlates"], (f.manual or lm) == t["manualGearbox"]),
            "the same, and the later ready time of the two": (max(rule_from, llm_from) == true_from, (f.plates or lp) == t["needsPlates"], (f.manual or lm) == t["manualGearbox"]),
        }
        n["notes"] += 1; rules_ok = all(readers["rules"]); n["rules right"] += rules_ok
        for name, ok in readers.items():
            n[name] += all(ok)
            n[name + (": breaks a note the rules read right" if rules_ok else ": mends a note the rules read wrong")] += all(ok) != rules_ok
            per[name][r["stratum"]] += all(ok); per[name]["n " + r["stratum"]] += 1
        j = T.judge(r, a)
        for fact, ok in j.items():
            if not ok: errs[fact].append((r["note"]["text"], {k: v for k, v in (a or {"unreadable": ans.get("content") or ans.get("error")}).items() if v}))
        if not all(readers["model"]) and rules_ok and not any(not j[k] for k in ("ready", "plates", "manual")): pass
    print(f"== {spec}: {n['notes']} notes, the rules read {n['rules right']} right and {n['notes'] - n['rules right']} wrong on ready time, plates and manual")
    for name in ("rules", "model", "rules, and plates or manual when either says so", "the same, and the later ready time of the two"):
        week = sum(WEEK[s] * (1 - per[name][s] / per[name]["n " + s]) for s in WEEK if per[name]["n " + s])
        print(f"   {name:50s} right {n[name]:3d}; mends {n[name + ': mends a note the rules read wrong']:2d}, breaks {n[name + ': breaks a note the rules read right']:2d}; wrong notes in a week's mix of the rules-right strata {week:.2f}")
    if show:
        for fact, items in errs.items():
            print("   --", fact, len(items))
            for text, a in items[:12]: print("        ", text, "=>", json.dumps(a, ensure_ascii=False))
