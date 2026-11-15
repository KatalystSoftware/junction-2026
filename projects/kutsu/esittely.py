"""Reshape companies.json and roles.json into the company and job-ad structure of the demo
(projects/kutsu/esittely/app/data.js), one entry per open role. Run after validate.py --apply.

    python3 esittely.py

Each entry has the demo's keys `id`, `name`, `sector`, `title`, `ad`, `confirmed`, `corrections`.
`ad` is built only from validated quotes, laid out so the demo's own `extract()` can read it
("You have:" and "Nice to have:" with "- " lines). `draft` holds the same reading as ids the demo
uses (role family, skill ids, Finnish, work modes) and `ad_lines` says where every line came from.
Left out because nothing public grounds them: `size`, `stand`, `tradeoffs`, minimum experience.
`confirmed` is null and `corrections` is empty: no company has seen its draft yet.
"""

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODES = {"hybrid": "hybrid", "fully": "remote", "remote": "remote", "telecommute": "remote", "on-site": "onsite", "onsite": "onsite"}
FINNISH = {"finnish_required": "required", "english_enough": "no"}


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def one_line(s):
    return re.sub(r"\s+", " ", s).strip()


def entry(c, r, n):
    lines = []

    def add(text, f, name):
        lines.append({"text": one_line(text), "field": name, "source_url": f.get("source_url"), "retrieved_at": f.get("retrieved_at")})

    add(r["title"]["value"], r["title"], "title")
    what = c.get("what_they_do")
    if what and what.get("quote"):
        add(what["quote"], what, "what_they_do")
    for name, head in (("must_have", "You have:"), ("nice_to_have", "Nice to have:")):
        items = [x for x in r.get(name, []) if x.get("quote")]
        if items:
            lines.append({"text": head, "field": "heading"})
            for x in items:
                add("- " + x["quote"], x, name)
    for name in ("language_requirement", "workplace", "location", "employment_type"):
        f = r.get(name) or {}
        if f.get("quote") and not (name == "workplace" and f["value"] not in MODES):
            add(f["quote"], f, name)

    draft = {}
    if r.get("role_family"):
        draft["role"] = r["role_family"]["value"]
    for name, key in (("must_have", "must"), ("nice_to_have", "nice")):
        ids = list(dict.fromkeys(x["skill_id"] for x in r.get(name, []) if x.get("skill_id")))
        if ids:
            draft[key] = [[i] for i in ids] if key == "must" else ids
    lang = (r.get("language_requirement") or {}).get("value")
    if lang in FINNISH:
        draft["finnish"] = FINNISH[lang]
    mode = MODES.get((r.get("workplace") or {}).get("value"))
    if mode:
        draft["modes"] = [mode]
    if (r.get("seniority") or {}).get("quote"):
        draft["seniority"] = r["seniority"]["value"]

    name = (c.get("name") or c.get("name_on_site") or {}).get("value")
    out = {"id": f"{slug(name)}-{n}", "company_id": c["id"], "name": name}
    ind = (c.get("industry") or {}).get("value")
    if ind and ind.get("label"):
        out["sector"] = ind["label"]
        out["sector_source"] = c["industry"]["source_url"]
    out.update(title=r["title"]["value"], ad="\n".join(x["text"] for x in lines), ad_url=r["url"]["value"],
               ad_lines=lines, draft=draft, confirmed=None, corrections={})
    return out


def main():
    companies = {c["id"]: c for c in json.loads((HERE / "companies.json").read_text())}
    roles = json.loads((HERE / "roles.json").read_text())
    out, seen = [], {}
    for r in roles:
        c = companies.get(r["company_id"])
        if not c:
            continue
        seen[c["id"]] = seen.get(c["id"], 0) + 1
        out.append(entry(c, r, seen[c["id"]]))
    doc = {"note": "Real companies and open roles from public sources, in the shape of DATA.companies in "
                   "projects/kutsu/esittely/app/data.js. One entry per role. See esittely.py for what is left out.",
           "companies": out}
    (HERE / "esittely-companies.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n")
    print(f"wrote {len(out)} entries for {len(seen)} companies; with role family {sum('role' in e['draft'] for e in out)}, "
          f"with a must-have skill id {sum('must' in e['draft'] for e in out)}")


if __name__ == "__main__":
    main()
