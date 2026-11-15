"""Link each skill in skills_src.SKILLS to an ESCO concept (official EU skills taxonomy) via the public ESCO API."""
import json, sys, urllib.parse, urllib.request, os
sys.path.insert(0, os.path.dirname(__file__))
from skills_src import SKILLS
out = []
for sid, label, fam, plain, q in SKILLS:
    url = "https://ec.europa.eu/esco/api/search?" + urllib.parse.urlencode({"text": q, "type": "skill", "language": "en", "limit": 1})
    try:
        r = json.load(urllib.request.urlopen(url, timeout=20))["_embedded"]["results"][0]
        esco = {"title": r["title"], "uri": r["uri"]}
    except Exception as e:
        esco = None
    out.append({"id": sid, "label": label, "family": fam, "plain": plain, "esco": esco})
    print(sid, "->", esco and esco["title"])
json.dump(out, open(os.path.join(os.path.dirname(__file__), "..", "data", "skills.json"), "w"), indent=1)
