"""Prepare a spot-check: N random roles, each written to work/spot/<n>.txt as the stored record
followed by the text of the posting it came from. A reviewer (a fresh sub-agent) reads each file
and judges every field against the posting.

    python3 spot.py [n] [seed]

The posting text is the copy fetched during the crawl (a cached URL is never fetched again); a
posting page that only the feed pointed at is fetched once, politely, through lib.fetch.
"""

import json
import random
import sys
from pathlib import Path

import lib

HERE = Path(__file__).resolve().parent
OUT = HERE / "work" / "spot"
FIELDS = ("title", "location", "workplace", "language_requirement", "seniority", "employment_type", "working_time", "role_family")


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 15
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    roles = json.loads((HERE / "roles.json").read_text())
    names = {c["id"]: (c.get("name") or c.get("name_on_site") or {}).get("value") for c in json.loads((HERE / "companies.json").read_text())}
    OUT.mkdir(parents=True, exist_ok=True)
    for p in OUT.glob("*.txt"):
        p.unlink()
    for i, r in enumerate(random.Random(seed).sample(roles, min(n, len(roles))), 1):
        url = r["url"]["value"]
        meta, body = lib.fetch(url)
        if lib.ok(meta):
            where, text = url, lib.raw_text(body, meta.get("content_type", ""))
        else:
            where, text = r["title"]["source_url"], lib.source_text(r["title"]["source_url"]) or ""
            at = text.find(lib.norm(r["title"]["value"]))
            text = text[max(0, at - 200): at + 12000] if at >= 0 else text[:12000]
        rec = [f"company: {names.get(r['company_id'])}", f"posting url: {url}", f"text below is from: {where}"]
        for name in FIELDS:
            f = r.get(name)
            rec.append(f"{name}: {f['value']!r}" + (f"   (quote: {f['quote']!r})" if f.get("quote") else "") if f else f"{name}: (not stated)")
        for name in ("must_have", "nice_to_have"):
            rec += [f"{name}: {x['value']!r} skill_id={x.get('skill_id')}   (quote: {x['quote']!r})" for x in r.get(name, [])] or [f"{name}: (none)"]
        (OUT / f"{i:02d}.txt").write_text("\n".join(rec) + "\n\n=== POSTING TEXT ===\n" + text[:14000] + "\n")
    print(f"wrote {min(n, len(roles))} files to {OUT}")


if __name__ == "__main__":
    main()
