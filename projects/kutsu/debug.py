"""Offline look at one seed: careers pages, job system, candidates. `ESPOO_OFFLINE=1 python3 debug.py tuxera`"""
import json
import sys

import pipeline

seeds = json.loads((pipeline.WORK / "seeds.json").read_text())
for s in seeds:
    name = s.get("name") or s.get("name_hint") or ""
    if sys.argv[1].lower() not in (name + " " + (s.get("website") or "")).lower():
        continue
    f = pipeline.safe_discover(s)
    d, c = f["diag"], f["company"]
    print(name, "|", {k: v for k, v in d.items() if k not in ("id", "name")})
    print("  careers_url:", c.get("careers_url", {}).get("value"), "| feed:", c.get("ats_feed_url", {}).get("value"))
    for cand in f["candidates"][:int(sys.argv[2]) if len(sys.argv) > 2 else 8]:
        r = pipeline.prepare(cand, name)
        print("  ", cand["kind"], "|", (r.get("title") or {}).get("value", "")[:70], "|", r["_url"][:110], "|", len(r["_body"]))
