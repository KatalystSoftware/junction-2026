"""Generate the synthetic dataset for the prototype (seeded, so every build is identical).
All companies, job ads and people are fictional. Writes app/data.js (window.DATA = {...})."""
import json, os, random

ROOT = os.path.join(os.path.dirname(__file__), "..")
rng = random.Random(2026)
SK = {s["id"]: s for s in json.load(open(os.path.join(ROOT, "data", "skills.json")))}

ROLES = {
    "backend": "Software development (back-end)",
    "frontend": "Software development (web front-end)",
    "mobile": "Mobile apps",
    "data": "Data & analytics",
    "ml": "AI / machine learning",
    "devops": "Cloud & DevOps",
    "qa": "Testing & quality",
    "embedded": "Embedded & hardware",
    "design": "UX / UI design",
    "product": "Product & project management",
    "security": "Cybersecurity",
    "support": "IT support & systems",
    "erp": "Business systems (ERP / CRM)",
    "game": "Game development",
}
EXP = ["Under 1 year (incl. studies or traineeship)", "1–3 years", "3–6 years", "6+ years"]
TRADEOFFS = [
    {"id": "build", "q": "Which kind of work do you want more of?", "a": "Building new things from scratch", "b": "Improving and running existing systems",
     "qe": "Which kind of work does this role have more of?"},
    {"id": "depth", "q": "Which describes you better?", "a": "Deep specialist in one area", "b": "Generalist who covers many areas",
     "qe": "Which does this role need more?"},
    {"id": "pace", "q": "Which team rhythm suits you?", "a": "Fast experiments, ship often", "b": "Careful planning, fewer mistakes",
     "qe": "Which rhythm does this team have?"},
]

# ---------------------------------------------------------------- companies + their public job ads (synthetic)
COMPANIES = [
 {"id": "puro", "name": "Puro Analytics", "sector": "Data consultancy", "size": "40 people", "stand": "A3",
  "title": "Data Analyst (Power BI)",
  "ad": """Data Analyst (Power BI)
Puro Analytics helps Finnish retail and logistics companies make sense of their data.
You have:
- 3+ years of experience in data analysis or business intelligence.
- Strong SQL skills.
- Experience building Power BI dashboards.
- Fluent Finnish required.
Nice to have:
- Python for data cleaning.
- Statistics knowledge.
We offer a full-time permanent position in a hybrid model, office in Espoo Keilaniemi.
Start as soon as possible.""",
  "confirmed": None,  # never responded: the demo confirms it live
  "tradeoffs": {"build": "b", "depth": "a", "pace": "b"}},
 {"id": "kajo", "name": "Kajo Systems", "sector": "Telecom software", "size": "300 people", "stand": "B1",
  "title": "Senior C++ Developer, 5G base stations",
  "ad": """Senior C++ Developer, 5G base stations
Kajo Systems builds software for 5G radio networks used by operators in 40 countries.
You have:
- 6+ years of software development experience.
- Excellent C++ skills.
- Linux experience.
- Telecom or 5G background.
Nice to have:
- Python for test tooling.
- CI/CD pipelines.
Our working language is English and we welcome international applicants. We support relocation and the work permit process.
Full-time, hybrid in Espoo Kera. Start within 3 months.""",
  "confirmed": {"at": "2026-11-12T09:14:00Z", "by": "Recruiter, Kajo Systems"},
  "tradeoffs": {"build": "b", "depth": "a", "pace": "b"}},
 {"id": "otsola", "name": "Otsola Cloud", "sector": "Cloud services", "size": "25 people", "stand": "B4",
  "title": "DevOps Engineer",
  "ad": """DevOps Engineer
Otsola Cloud runs cloud platforms for Nordic software companies.
You have:
- 3+ years of experience in DevOps or infrastructure.
- Kubernetes in production.
- AWS experience.
- Infrastructure as code (Terraform).
Nice to have:
- Go or Python scripting.
- Security mindset.
English is our working language. Remote or hybrid, office in Espoo Otaniemi. Full-time. Start within 3 months.""",
  "confirmed": {"at": "2026-11-11T15:40:00Z", "by": "CTO, Otsola Cloud"},
  "tradeoffs": {"build": "b", "depth": "b", "pace": "a"}},
 {"id": "tammi", "name": "Tammi Health Tech", "sector": "Health software", "size": "60 people", "stand": "A1",
  "title": "Full-stack Developer (TypeScript)",
  "ad": """Full-stack Developer (TypeScript)
Tammi Health Tech builds patient-flow software for Finnish wellbeing services counties.
You have:
- 1+ years of experience as a software developer.
- TypeScript and React.
- SQL databases.
Nice to have:
- Knowledge of health data regulation.
- Test automation.
- Finnish language skills are an advantage.
Full-time, hybrid in Espoo Leppävaara. Start as soon as possible.""",
  "confirmed": {"at": "2026-11-12T12:02:00Z", "by": "Engineering lead, Tammi Health Tech"},
  "tradeoffs": {"build": "a", "depth": "b", "pace": "a"}},
 {"id": "revontuli", "name": "Revontuli Play", "sector": "Games", "size": "18 people", "stand": "C2",
  "title": "Game Developer Trainee (Unity)",
  "ad": """Game Developer Trainee (Unity)
Revontuli Play makes cosy mobile games.
You have:
- C# programming skills from studies or own projects.
- Unity game development.
Nice to have:
- Mobile apps experience.
- UX / UI design interest.
Paid traineeship for 6 months, possible to continue. On-site in Espoo Tapiola. Our team works in English and we welcome international applicants. Start within 3 months.""",
  "confirmed": {"at": "2026-11-10T10:30:00Z", "by": "Studio lead, Revontuli Play"},
  "tradeoffs": {"build": "a", "depth": "b", "pace": "a"}},
 {"id": "kidelab", "name": "Kidelab Energy", "sector": "Energy & IoT", "size": "90 people", "stand": "C1",
  "title": "Embedded Software Engineer",
  "ad": """Embedded Software Engineer
Kidelab Energy designs smart battery storage for homes and housing companies.
You have:
- 3+ years of experience with embedded software.
- C programming.
- Electronics understanding.
Nice to have:
- Rust.
- Linux.
English working language, Finnish is a plus. Full-time, on-site in Espoo Kilo. Start within 3 months.""",
  "confirmed": {"at": "2026-11-12T08:05:00Z", "by": "R&D manager, Kidelab Energy"},
  "tradeoffs": {"build": "a", "depth": "a", "pace": "b"}},
 {"id": "turva", "name": "Turvaketju Security", "sector": "Cybersecurity services", "size": "120 people", "stand": "B2",
  "title": "SOC Analyst",
  "ad": """SOC Analyst
Turvaketju Security monitors networks for Finnish public sector clients around the clock.
You have:
- 1+ years of experience in cybersecurity or IT operations.
- Networking knowledge.
- Linux.
- Fluent Finnish required, as all client communication is in Finnish.
Nice to have:
- Identity & access management.
- Python scripting.
Full-time, on-site in Espoo with shift work. Security clearance required. Start within 3 months.""",
  "confirmed": {"at": "2026-11-11T13:20:00Z", "by": "Security operations lead, Turvaketju Security"},
  "tradeoffs": {"build": "b", "depth": "a", "pace": "b"}},
 {"id": "lahde", "name": "Lähde Logistics IT", "sector": "Logistics", "size": "800 people", "stand": "A2",
  "title": "ERP Specialist (SAP)",
  "ad": """ERP Specialist (SAP)
Lähde Logistics moves groceries to 900 stores in Finland.
You have:
- Experience with SAP / ERP systems.
- Project management skills.
- Understanding of logistics processes. Career changers from logistics roles are welcome.
Nice to have:
- SQL.
- Data analysis / BI.
Finnish and English. Full-time, hybrid in Espoo Suomenoja. Start as soon as possible.""",
  "confirmed": None,
  "tradeoffs": {"build": "b", "depth": "b", "pace": "b"}},
 {"id": "virta", "name": "Virtalähde AI", "sector": "Applied AI", "size": "35 people", "stand": "C3",
  "title": "Machine Learning Engineer",
  "ad": """Machine Learning Engineer
Virtalähde AI builds forecasting models for energy grids.
You have:
- 3+ years of experience in machine learning or data science.
- Python.
- Machine learning in production.
Nice to have:
- LLM / generative AI apps.
- Data pipelines.
- AWS.
English is our working language. We support relocation and work permits. Full-time, hybrid or remote, office in Espoo Otaniemi. Start within 3 months.""",
  "confirmed": {"at": "2026-11-12T16:45:00Z", "by": "Head of ML, Virtalähde AI"},
  "tradeoffs": {"build": "a", "depth": "a", "pace": "a"}},
 {"id": "kuura", "name": "Kuurapolku Fintech", "sector": "Payments", "size": "150 people", "stand": "B3",
  "title": "Back-end Developer (Kotlin)",
  "ad": """Back-end Developer (Kotlin)
Kuurapolku Fintech processes card payments for Nordic merchants.
You have:
- 3+ years of back-end development experience.
- Kotlin or Java.
- SQL databases.
Nice to have:
- Kubernetes.
- Security mindset.
Our team works in English. Full-time, hybrid in Espoo Keilaniemi. Start within 3 months.""",
  "confirmed": {"at": "2026-11-11T09:55:00Z", "by": "Engineering manager, Kuurapolku Fintech"},
  "tradeoffs": {"build": "a", "depth": "a", "pace": "b"}},
 {"id": "nokkela", "name": "Nokkela Apps", "sector": "App agency", "size": "12 people", "stand": "C4",
  "title": "Junior Mobile Developer",
  "ad": """Junior Mobile Developer
Nokkela Apps builds mobile apps for Finnish brands.
You have:
- JavaScript or TypeScript.
- Mobile apps development from work, studies or own projects.
Nice to have:
- React.
- Figma.
Junior level welcome. Full-time or part-time, hybrid in Espoo Tapiola. Finnish is helpful but not required. Start as soon as possible.""",
  "confirmed": None,
  "tradeoffs": {"build": "a", "depth": "b", "pace": "a"}},
 {"id": "sointu", "name": "Sointu Quality", "sector": "Software testing services", "size": "70 people", "stand": "A4",
  "title": "Test Automation Engineer",
  "ad": """Test Automation Engineer
Sointu Quality tests software for banks and the public sector.
You have:
- 1+ years of software testing experience.
- Test automation.
- Python or JavaScript.
Nice to have:
- Manual testing.
- CI/CD pipelines.
- Agile / Scrum.
Finnish is an advantage. Full-time, hybrid in Espoo Leppävaara. Start as soon as possible.""",
  "confirmed": {"at": "2026-11-12T10:10:00Z", "by": "Delivery manager, Sointu Quality"},
  "tradeoffs": {"build": "b", "depth": "b", "pace": "b"}},
]
# What each company corrected when it confirmed its draft (applied on top of the extractor's draft in the app)
CORRECTIONS = {
    "kajo": {"nice": ["python", "cicd"], "finnish": "no"},
    "otsola": {"finnish": "no"},
    "tammi": {"finnish": "helpful"},
    "turva": {"finnish": "required", "note": "Finnish truly required: all client calls are in Finnish."},
    "virta": {"finnish": "no"},
    "kuura": {"finnish": "no", "international": "open"},
    "revontuli": {"finnish": "no"},
    "kidelab": {"finnish": "helpful"},
    "sointu": {"finnish": "helpful"},
}
for c in COMPANIES:
    c["corrections"] = CORRECTIONS.get(c["id"], {})

# ---------------------------------------------------------------- candidates (synthetic)
ARCH = {  # role -> (skills at high probability, skills at lower probability)
 "backend": (["python", "java", "sql", "docker"], ["kotlin", "go", "kubernetes", "aws", "cicd", "linux", "csharp", "typescript"]),
 "frontend": (["javascript", "typescript", "react"], ["figma", "uiux", "testauto", "mobile", "sql"]),
 "mobile": (["mobile", "javascript", "kotlin"], ["typescript", "react", "figma"]),
 "data": (["sql", "analytics", "python"], ["statistics", "dataeng", "ml", "azure", "sap"]),
 "ml": (["python", "ml", "statistics"], ["llm", "dataeng", "aws", "sql", "docker"]),
 "devops": (["linux", "docker", "cicd"], ["kubernetes", "aws", "azure", "terraform", "python", "go", "security"]),
 "qa": (["manualtest", "testauto"], ["python", "javascript", "agile", "cicd", "sql"]),
 "embedded": (["cpp", "embedded", "electronics"], ["linux", "rust", "python", "robotics", "telecom"]),
 "design": (["uiux", "figma", "userresearch"], ["javascript", "react", "productmgmt"]),
 "product": (["agile", "projectmgmt", "productmgmt"], ["analytics", "sql", "uiux", "sap"]),
 "security": (["security", "networks", "linux"], ["iam", "python", "azure", "cicd"]),
 "support": (["itsupport", "networks"], ["linux", "azure", "iam", "manualtest"]),
 "erp": (["sap", "projectmgmt"], ["sql", "analytics", "salesforce", "agile"]),
 "game": (["csharp", "gamedev"], ["cpp", "mobile", "uiux", "javascript"]),
}
ROLE_WEIGHTS = {"backend": 14, "frontend": 10, "mobile": 4, "data": 14, "ml": 7, "devops": 7, "qa": 8, "embedded": 7,
                "design": 6, "product": 6, "security": 5, "support": 6, "erp": 4, "game": 4}
FIRST = ["Aino", "Mikko", "Olena", "Ahmed", "Priya", "Juho", "Sara", "Wei", "Laura", "Tomás", "Fatima", "Eero", "Ana", "Dmytro", "Emma",
         "Kofi", "Hanna", "Rahul", "Niina", "Yusuf", "Elif", "Ville", "Marta", "Chen", "Ida", "Omar", "Sofia", "Lucas", "Mei", "Antti",
         "Grace", "Ivan", "Leila", "Pekka", "Noor", "Katja", "Samuel", "Anjali", "Jonas", "Amina"]
PREV_FIELDS = ["logistics", "retail", "teaching", "hospitality", "nursing", "accounting", "journalism", "manufacturing", "customer service", "the army"]
EXAMPLES = {
 "python": ["Automated a weekly sales report that used to take a day by hand.", "Wrote an API that serves 2 000 requests a minute.", "Cleaned and merged three messy customer datasets."],
 "sql": ["Rewrote slow queries so a dashboard loads in 2 s instead of 40 s.", "Designed the database for an inventory app."],
 "analytics": ["Built a Power BI dashboard used by 30 store managers.", "Made a churn report that changed how support calls were prioritised."],
 "react": ["Built the booking screens of a clinic web app.", "Made a reusable component library for three products."],
 "typescript": ["Moved a 40 000-line JavaScript app to TypeScript."],
 "javascript": ["Built an event-signup site for a sports club."],
 "java": ["Maintained a payment service handling 1 M transactions a day."],
 "kotlin": ["Wrote an Android app for warehouse scanners."],
 "docker": ["Containerised a legacy app so new developers start in 10 minutes."],
 "kubernetes": ["Ran 40 services on Kubernetes with zero-downtime releases."],
 "cicd": ["Set up automatic tests and releases for a 6-person team."],
 "ml": ["Trained a model that forecasts bakery demand per store.", "Built an image classifier for sorting recycled materials."],
 "testauto": ["Automated 300 regression tests for an online bank.", "Wrote end-to-end tests that cut release checks from 2 days to 2 hours."],
 "manualtest": ["Wrote test plans for a public-sector e-service."],
 "cpp": ["Optimised signal-processing code to run 3x faster on a base station."],
 "embedded": ["Wrote firmware for a battery-monitoring sensor."],
 "electronics": ["Designed a circuit board for a soil-moisture sensor."],
 "uiux": ["Redesigned a checkout flow; drop-outs fell by a third.", "Ran usability tests with 12 elderly users."],
 "figma": ["Designed the full screen set of a food-delivery app."],
 "security": ["Investigated phishing incidents for a 500-person company."],
 "networks": ["Set up the office network and VPN for a 60-person firm."],
 "sap": ["Configured SAP purchasing for a new warehouse."],
 "projectmgmt": ["Led the move of 12 warehouses to a new ordering system."],
 "gamedev": ["Published a small puzzle game on Google Play."],
 "csharp": ["Wrote the gameplay code of a student game project."],
 "mobile": ["Built a React Native app for a running club."],
 "linux": ["Kept 50 Linux servers patched and monitored."],
 "itsupport": ["Supported 200 users and cut ticket backlog by half."],
 "aws": ["Moved a company's file storage and backups to AWS."],
}
EVIDENCE = {
 "python": "A public code repository with a small data-cleaning library: tests included, documented, last updated 2 months ago.",
 "analytics": "A public Power BI report on open Helsinki Region Transport data with five pages of charts.",
 "react": "A live portfolio web app built with React and TypeScript; source code public.",
 "ml": "A notebook comparing three demand-forecasting models on open data, with a written explanation of the results.",
 "gamedev": "A small game on an app store, made in Unity, with about 2 000 downloads.",
 "uiux": "A case study of a redesign: interview notes, sketches, three tested prototypes.",
 "embedded": "A public hardware project: firmware and circuit board files for a sensor node.",
 "testauto": "A public repository of automated browser tests for a demo shop, running on every change.",
}

def pick_level(p):
    r = rng.random(); acc = 0
    for lvl, w in p:
        acc += w
        if r < acc: return lvl
    return p[-1][0]

roles = list(ROLE_WEIGHTS)
cands = []
for i in range(1, 361):
    role = rng.choices(roles, [ROLE_WEIGHTS[r] for r in roles])[0]
    second = rng.choice([r for r in roles if r != role]) if rng.random() < 0.3 else None
    exp = rng.choices([0, 1, 2, 3], [18, 30, 32, 20])[0]
    career_change = rng.random() < 0.18
    if career_change: exp = rng.choice([0, 0, 1])
    hi, lo = ARCH[role]
    skills = {}
    for s in hi:
        if rng.random() < 0.85: skills[s] = rng.choices(["work", "project", "learning"], [60, 30, 10] if exp >= 1 else [15, 65, 20])[0]
    for s in rng.sample(lo, k=min(len(lo), rng.randint(1, 4))):
        skills.setdefault(s, rng.choices(["work", "project", "learning"], [40, 40, 20] if exp >= 1 else [10, 60, 30])[0])
    if second:
        for s in rng.sample(ARCH[second][0], k=min(2, len(ARCH[second][0]))):
            skills.setdefault(s, rng.choice(["project", "learning", "work"]))
    if role == "erp" or (career_change and rng.random() < 0.4): skills.setdefault("projectmgmt", "work")
    if role == "embedded" and rng.random() < 0.3: skills["telecom"] = "work"
    sk = []
    for s, d in skills.items():
        e = {"id": s, "depth": d}
        if d == "work": e["years"] = rng.choice([1, 2, 3, 4, 5, 7]) if exp >= 2 else rng.choice([1, 2])
        if d in ("work", "project") and s in EXAMPLES and rng.random() < 0.45: e["example"] = rng.choice(EXAMPLES[s])
        sk.append(e)
    fi = pick_level([("fluent", 0.38), ("working", 0.12), ("basic", 0.22), ("none", 0.28)])
    en = "fluent" if fi != "fluent" or rng.random() < 0.7 else pick_level([("working", 0.7), ("basic", 0.3)])
    sv = pick_level([("working", 0.08), ("basic", 0.2), ("none", 0.72)])
    langs = {"en": en, "fi": fi, "sv": sv}
    permit = fi in ("none", "basic") and rng.random() < 0.3
    c = {
        "id": f"C-{i:03d}", "name": f"{rng.choice(FIRST)} {chr(65 + rng.randrange(26))}.",
        "registered": f"2026-11-{rng.randint(2, 13):02d}T{rng.randint(7, 22):02d}:{rng.randint(0, 59):02d}:00Z",
        "roles": [role] + ([second] if second else []), "exp": exp, "skills": sk, "langs": langs,
        "mode": rng.choice([["onsite", "hybrid"], ["hybrid"], ["hybrid", "remote"], ["onsite", "hybrid", "remote"], ["remote"]]),
        "start": rng.choices(["now", "3m", "later"], [45, 40, 15])[0],
        "types": rng.choice([["full"], ["full"], ["full", "part"], ["trainee", "full"], ["part"], ["contract", "full"]]) if exp else rng.choice([["trainee"], ["trainee", "full"], ["full"], ["part", "trainee"]]),
        "permit": permit,
        "tradeoffs": {t["id"]: rng.choice("ab") for t in TRADEOFFS},
        "careerChange": rng.choice(PREV_FIELDS) if career_change else None,
        "next": None, "evidence": None, "wants": [],
    }
    ev_sk = [s["id"] for s in sk if s["id"] in EVIDENCE and s["depth"] in ("work", "project")]
    if ev_sk and rng.random() < 0.3:
        s = rng.choice(ev_sk)
        c["evidence"] = {"skill": s, "link": f"https://example.org/portfolio/{c['id'].lower()}", "summary": EVIDENCE[s], "status": "approved"}
    cands.append(c)

# Demo candidate (follows the demo script): data analyst, Finnish basic, Power BI at work.
demo = next(c for c in cands if c["id"] == "C-027")
demo.update({"name": "Olena K.", "roles": ["data"], "exp": 2,
             "skills": [{"id": "sql", "depth": "work", "years": 5, "example": "Rewrote slow queries so a dashboard loads in 2 s instead of 40 s."},
                        {"id": "analytics", "depth": "work", "years": 4, "example": "Built a Power BI dashboard used by 30 store managers."},
                        {"id": "python", "depth": "project"}, {"id": "statistics", "depth": "work", "years": 3}, {"id": "sap", "depth": "learning"}],
             "langs": {"en": "fluent", "fi": "basic", "sv": "none"}, "mode": ["onsite", "hybrid"], "start": "now", "types": ["full"], "permit": False,
             "tradeoffs": {"build": "b", "depth": "a", "pace": "b"}, "careerChange": None,
             "evidence": {"skill": "analytics", "link": "https://example.org/portfolio/c-027", "summary": EVIDENCE["analytics"], "status": "approved"}})

# Who asked to meet whom (candidates pick stands from their recommendations); decided later in the app, stored here as seed
COMPANY_SKILLS = {"puro": ["sql", "analytics", "python", "statistics"], "kajo": ["cpp", "linux", "telecom", "python"], "otsola": ["kubernetes", "aws", "terraform", "docker", "linux"],
    "tammi": ["typescript", "react", "sql"], "revontuli": ["csharp", "gamedev", "mobile"], "kidelab": ["cpp", "embedded", "electronics", "rust"],
    "turva": ["networks", "linux", "security", "iam"], "lahde": ["sap", "projectmgmt", "sql", "analytics"], "virta": ["python", "ml", "llm", "dataeng"],
    "kuura": ["kotlin", "java", "sql", "kubernetes"], "nokkela": ["javascript", "typescript", "mobile", "react"], "sointu": ["testauto", "python", "javascript", "manualtest"]}
for c in cands:
    have = {s["id"] for s in c["skills"] if s["depth"] != "learning"}
    for co, sks in COMPANY_SKILLS.items():
        if len(have & set(sks)) >= 2 and rng.random() < 0.75: c["wants"].append(co)
    if not c["wants"] and rng.random() < 0.5: c["wants"].append(rng.choice(list(COMPANY_SKILLS)))
demo["wants"] = ["puro", "lahde"]

data = {
    "event": {"name": "Espoo Tech Talent Day", "date": "Thu 26 Nov 2026", "format": "Hybrid: Espoo Otaniemi + online", "organiser": "City of Espoo (synthetic demo)"},
    "roles": ROLES, "exp": EXP, "tradeoffs": TRADEOFFS, "skills": list(SK.values()),
    "companies": COMPANIES, "candidates": cands,
    "generated": "seed 2026 · 360 synthetic candidates · 12 fictional companies",
}
open(os.path.join(ROOT, "app", "data.js"), "w").write("// Synthetic data: every company, job ad and person here is fictional. Generated by tools/gen_data.py (seed 2026).\nwindow.DATA = " + json.dumps(data, ensure_ascii=False, indent=0) + ";\n")
print(len(cands), "candidates;", sum(1 for c in cands if c["evidence"]), "with evidence;", sum(1 for c in cands if c["langs"]["fi"] in ("fluent", "working")), "with working Finnish")
