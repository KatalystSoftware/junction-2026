"""Sample applications to an event, drawn against the real employers' drafted needs, for the applications screen.

    python3 applicants.py            # writes applications.json

Nobody here is real. Each applicant is built from the needs of two or three employers that are coming to the
event (`presets.json`), so that fit against the real roles exists to analyse. Each one carries two kinds of lines,
kept apart on the screen: `drafted` lines, read from the applicant's sources by the pipeline and left as drafted
(the AI summary), and `confirmed` lines, which the applicant explicitly answered, corrected or wrote. Only counts
and the handle leave the applicant anonymous until an organiser decides, as in Esittely.
"""

import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
LEVELS = ["Early career", "Experienced", "Senior", "Lead"]
FI = ["none", "basic", "working level", "fluent"]
EN = ["working level", "fluent", "fluent", "fluent"]
CITIES = ["Espoo", "Helsinki", "Vantaa", "Tampere", "Turku", "Oulu", "Berlin", "Tallinn", "Kyiv", "Bengaluru", "Lisbon"]
ABROAD = {"Berlin", "Tallinn", "Kyiv", "Bengaluru", "Lisbon"}
WANTS_MORE = {"build": ("Building new things from scratch", "Improving and running existing systems"),
              "depth": ("Deep specialist in one area", "Generalist who covers many areas"),
              "pace": ("Fast experiments, ship often", "Careful planning, fewer mistakes")}
ABOUT = [
    "I like being the person who explains the numbers to people who hate numbers.",
    "Most of my best work started as a side script nobody asked for.",
    "I am happiest when a messy system becomes boring and reliable.",
    "I read datasheets for fun. I also know that is not normal.",
    "I moved to Finland two years ago and want to stay; my Finnish is getting there.",
    "I have shipped things used by thousands of people and fixed them at 3 am.",
    "I am switching from research to industry and want work that reaches a customer.",
    "Give me a hard measurement problem and a quiet room.",
    "I am better at finishing than starting, and teams tend to need that.",
    "I care about security as a habit, not a department.",
]
LOOKING = [
    "A team where I can grow from building pieces into owning a system.",
    "Hardware that leaves the lab and gets manufactured.",
    "Work in English, with a real path to learning Finnish on the job.",
    "A small team, a clear product, and customers I can talk to.",
    "Research-adjacent engineering: rigorous, but shipped.",
    "A first role in Finland after my degree here.",
    "Less reporting, more forecasting and decisions.",
    "Deep technical work with people who review each other's code properly.",
]
QUOTES = {
    "role": ["{title} at a {kind} company, {y1}–present", "{title}, {kind}, {y1}–{y2}"],
    "skill_work": ["Built and ran {skill} in production for {n} teams.", "Owned {skill} for a {kind} product used daily.", "Led the move to {skill}; cut incidents by a third.", "Daily {skill} work since {y1}."],
    "skill_project": ["Personal project: {skill}, open on GitHub.", "Thesis work used {skill} end to end.", "Weekend repository exploring {skill}."],
    "skill_learning": ["Currently taking a {skill} course.", "Learning {skill} on the side this autumn."],
    "lang_fi": ["Finnish: {lvl}", "Suomi: {lvl}"],
}
KINDS = ["fintech", "health tech", "space", "telecom", "semiconductor", "cleantech", "consultancy", "gaming", "defence", "logistics", "energy", "research"]


def main():
    rnd = random.Random(2026)
    briefs = {b["id"]: b for b in json.loads((HERE / "signals.json").read_text())}
    preset = json.loads((HERE / "presets.json").read_text())[0]
    employers = [briefs[i] for i in preset["ids"] if i in briefs]
    needs = [(b, n) for b in employers for n in b["card"]["needs"] if n.get("skills") and n.get("family")]
    apps = []
    for k in range(36):
        b, home = rnd.choice(needs)
        same = [n for (bb, n) in needs if n["family"] == home["family"] and bb["id"] != b["id"]]
        other = rnd.choice(same) if same and rnd.random() < 0.8 else None
        level_i = min(3, max(0, LEVELS.index(home["seniority"]) + rnd.choice([-1, 0, 0, 0, 1]))) if home.get("seniority") in LEVELS else rnd.choice([0, 1, 1, 2])
        skills = []
        for s in rnd.sample(home["skills"], min(len(home["skills"]), rnd.choice([2, 3, 3, 4]))):
            skills.append({"name": s, "depth": rnd.choice(["work", "work", "work", "project"]), "years": None})
        if other:
            for s in rnd.sample(other["skills"], min(len(other["skills"]), rnd.choice([1, 2]))):
                if s not in [x["name"] for x in skills]:
                    skills.append({"name": s, "depth": rnd.choice(["work", "project", "learning"]), "years": None})
        for s in skills:
            if s["depth"] == "work":
                s["years"] = max(1, min(15, [1, 3, 7, 12][level_i] + rnd.choice([-1, 0, 1, 2])))
        city = rnd.choice(CITIES)
        fi = FI[rnd.choice([0, 0, 1, 1, 2, 3])] if city in ABROAD else FI[rnd.choice([0, 1, 1, 2, 2, 3, 3])]
        y1 = 2026 - (level_i * 4 + rnd.choice([1, 2, 3]))
        kind = rnd.choice(KINDS)
        drafted = [{"kind": "role", "text": f"{home['title'].rstrip('s')} ({home['family']})", "source": "LinkedIn", "quote": rnd.choice(QUOTES["role"]).format(title=home["title"].rstrip("s"), kind=kind, y1=y1, y2=y1 + 3)},
                   {"kind": "level", "text": f"{LEVELS[level_i]}: {2026 - y1} years of dated positions", "source": "LinkedIn", "quote": f"{2026 - y1} years of dated positions since {y1}"}]
        for s in skills:
            src = "GitHub" if s["depth"] == "project" and rnd.random() < 0.7 else "LinkedIn"
            q = rnd.choice(QUOTES["skill_" + s["depth"]]).format(skill=s["name"], n=rnd.choice([2, 3, 5, 8]), kind=kind, y1=y1 + rnd.choice([0, 1, 2]))
            drafted.append({"kind": "skill", "text": f"{s['name']}: {'used at work' if s['depth'] == 'work' else 'own projects' if s['depth'] == 'project' else 'learning it now'}{f', {s['years']} yr' if s['years'] else ''}", "source": src, "quote": q})
        drafted.append({"kind": "language", "text": f"English {EN[rnd.choice([0, 1, 2, 3])]}; Finnish {fi}", "source": "LinkedIn", "quote": rnd.choice(QUOTES["lang_fi"]).format(lvl=fi)})
        drafted.append({"kind": "where", "text": f"Lives in {city}{' (abroad)' if city in ABROAD else ''}; open to {rnd.choice(['hybrid or on-site', 'on-site', 'hybrid', 'remote or hybrid'])}", "source": "LinkedIn", "quote": f"{city} · open to new roles"})
        # what the applicant explicitly answered, corrected or wrote
        wants = list(dict.fromkeys([b["id"]] + ([bb["id"] for (bb, n) in needs if other and n is other][:1]) + [rnd.choice(employers)["id"] for _ in range(rnd.choice([0, 1, 1]))]))
        corrected = []
        if rnd.random() < 0.4 and skills:
            s = rnd.choice(skills)
            corrected.append({"kind": "skill", "text": f"{s['name']}: corrected to {rnd.choice(['used at work, 2 yr', 'own projects only', 'learning it now'])}", "was": f"{s['name']} as drafted"})
        if rnd.random() < 0.3:
            corrected.append({"kind": "remove", "text": f"Removed: {rnd.choice(['Excel', 'Jira', 'PowerPoint', 'MATLAB'])} (not worth listing)", "was": "a drafted skill"})
        answers = [
            {"q": "Which of these do you use, at work or in your own projects?", "a": ", ".join(x["name"] for x in skills if x["depth"] != "learning")},
            {"q": "How is your Finnish at work?", "a": fi},
            {"q": "Have you worked with " + rnd.choice(home["skills"]) + "?", "a": rnd.choice(["Yes, at work", "Learning it now", "Not yet"])},
            {"q": "Which kind of work do you want more of?", "a": rnd.choice(WANTS_MORE["build"])},
            {"q": "Which describes you better?", "a": rnd.choice(WANTS_MORE["depth"])},
            {"q": "Which team rhythm suits you?", "a": rnd.choice(WANTS_MORE["pace"])},
            {"q": "Which companies would you like to meet?", "a": ", ".join(briefs[w]["name"] for w in wants if w in briefs)},
            {"q": "I would need work-permit support", "a": "Yes" if city in ABROAD and rnd.random() < 0.7 else "No"},
        ]
        own = {"about": rnd.choice(ABOUT), "looking": rnd.choice(LOOKING)}
        applied = f"2026-11-{rnd.randint(3, 13):02d}T{rnd.randint(8, 21):02d}:{rnd.randint(0, 59):02d}:00Z"
        ai_summary = (f"{LEVELS[level_i]} {home['family'].lower()} profile. Works mainly with {', '.join(x['name'] for x in skills[:3])}"
                      f"{' and is learning ' + next((x['name'] for x in skills if x['depth'] == 'learning'), '') if any(x['depth'] == 'learning' for x in skills) else ''}. "
                      f"Based in {city}; Finnish {fi}. Sources read: LinkedIn{', GitHub' if any(d['source'] == 'GitHub' for d in drafted) else ''}.")
        apps.append({"id": f"A-{k + 1:03d}", "handle": f"Applicant {k + 1}", "field": home["family"], "level": LEVELS[level_i],
                     "skills": skills, "finnish": fi, "english": "fluent", "city": city, "abroad": city in ABROAD,
                     "permit": answers[-1]["a"] == "Yes", "wants": wants, "applied_at": applied, "sources": sorted({d["source"] for d in drafted}),
                     "ai_summary": ai_summary, "drafted": drafted, "corrected": corrected, "answers": answers, "own": own,
                     "project": rnd.choice([None, None, {"name": f"{rnd.choice(['sensor-pipeline', 'rf-notes', 'qc-dashboard', 'fw-bootloader', 'ml-eval'])}.pdf"}])})
    out = {"note": "Sample applications to the event, drawn from a fixed seed against the real employers' drafted needs. Nobody here is real.",
           "event": "deep-tech-talent-forum", "generated_from": "presets.json + signals.json needs", "applicants": apps}
    (HERE / "applications.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"{len(apps)} applicants, {len(employers)} employers, {len(needs)} needs")


if __name__ == "__main__":
    main()
