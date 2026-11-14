"""A sample pool: who came to Espoo's past events, as counts. Nobody in it is real.

Espoo plans the next event from the people who came to earlier ones. Kutsu has no such people and
must not collect any for a demo, so this draws them from a fixed seed and keeps only the counts the
screens show: per field, how many do that work, how many more want to move into it, their level,
their languages, which events they came to and which of the skills employers ask for they know.

Run:  python3 pool.py      (writes pool.json; the same numbers every run)
"""
import collections
import json
import pathlib
import random

HERE = pathlib.Path(__file__).parent
PEOPLE = 1140
# field: its share of the pool
FIELDS = {
    "Software": 24, "AI and data": 16, "Embedded and electronics": 8, "Semiconductors and photonics": 6,
    "Quantum": 3, "Space and RF": 3, "Mechanical and manufacturing": 7, "Research and science": 8,
    "Security": 5, "Product and design": 7, "Sales and business": 6, "Operations and support": 5, "Leadership": 2,
}
LEVELS = {"Early career": 30, "Experienced": 40, "Senior": 22, "Lead": 8}
# past events, each with the fields it drew most; None draws from every field alike
EVENTS = [
    {"id": "talent-2025", "name": "International talent evening", "date": "2025-11-20", "where": "Online", "employers": 31, "fields": None},
    {"id": "cloud-2026", "name": "Security and cloud morning", "date": "2026-03-12", "where": "Otaniemi", "employers": 14,
     "fields": ["Security", "Software", "Operations and support"]},
    {"id": "deep-2026", "name": "Deep tech evening", "date": "2026-05-21", "where": "Otaniemi", "employers": 19,
     "fields": ["Semiconductors and photonics", "Quantum", "Space and RF", "Embedded and electronics", "Research and science"]},
    {"id": "ai-2026", "name": "Software and AI day", "date": "2026-09-10", "where": "Online", "employers": 26,
     "fields": ["Software", "AI and data", "Product and design"]},
]


def asked():
    """The skills employers ask for, per field, from the drafted roles."""
    skills = collections.defaultdict(collections.Counter)
    for brief in json.loads((HERE / "signals.json").read_text()):
        for need in brief["card"]["needs"]:
            skills[need["family"]].update(need["skills"])
    return {field: [s for s, _ in counted.most_common(14)] for field, counted in skills.items()}


def main():
    rng = random.Random(2026)
    pick = lambda weights: rng.choices(list(weights), weights=list(weights.values()))[0]
    skills = asked()
    # how common each asked skill is among the people of its field: some are rare, which is the gap worth seeing
    common = {field: {s: rng.uniform(0.08, 0.6) for s in names} for field, names in skills.items()}
    blank = lambda: {"people": 0, "wanting": 0, "levels": dict.fromkeys(LEVELS, 0), "english": 0, "finnish": 0, "abroad": 0,
                     "events": dict.fromkeys((e["id"] for e in EVENTS), 0), "skills": collections.Counter()}
    fields = {field: blank() for field in FIELDS}
    came = collections.Counter()
    for _ in range(PEOPLE):
        field = pick(FIELDS)
        at = fields[field]
        at["people"] += 1
        at["levels"][pick(LEVELS)] += 1
        # what a person wants is asked apart from what they can do: three in ten want to move to another field
        if rng.random() < 0.3:
            fields[pick({f: w for f, w in FIELDS.items() if f != field})]["wanting"] += 1
        abroad = rng.random() < 0.18
        at["abroad"] += abroad
        at["english"] += rng.random() < 0.9
        at["finnish"] += (not abroad) and rng.random() < 0.55
        at["skills"].update(s for s, share in common.get(field, {}).items() if rng.random() < share)
        events = [e["id"] for e in EVENTS if rng.random() < (0.3 if e["fields"] is None else 0.55 if field in e["fields"] else 0.06)]
        for event in events or [rng.choice(EVENTS)["id"]]:
            at["events"][event] += 1
            came[event] += 1
    for at in fields.values():
        at["skills"] = dict(at["skills"].most_common())
    pool = {
        "note": "Sample data. Nobody counted here is a real person, and the past events and their numbers are made up.",
        "people": PEOPLE,
        "events": [{**{k: e[k] for k in ("id", "name", "date", "where", "employers")}, "people": came[e["id"]]} for e in EVENTS],
        "fields": fields,
    }
    (HERE / "pool.json").write_text(json.dumps(pool, indent=1, ensure_ascii=False) + "\n")
    for field, at in fields.items():
        print(f"{at['people']:4} do  {at['wanting']:3} want  {field}")


if __name__ == "__main__":
    main()
