"""Append one line of round metrics to metrics.jsonl (run after validate.py --apply).

    python3 metrics.py <round label>          # append
    python3 metrics.py --print                # print the line, do not append
"""

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = HERE / "work"


def line(label):
    diag = json.loads((WORK / "diag.json").read_text())
    stats = json.loads((WORK / "validate_stats.json").read_text())
    roles = json.loads((HERE / "roles.json").read_text())
    comps = diag["companies"]
    hiring = {r["company_id"] for r in roles}
    lang = Counter(r["language_requirement"]["value"] for r in roles if "language_requirement" in r)
    drops = Counter()
    for c in comps:
        drops.update(c.get("drops") or {})
    return {
        "round": label,
        "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "companies_checked": len(comps),
        "site_reachable": sum(1 for c in comps if c.get("site")),
        "with_careers_page_or_feed": sum(1 for c in comps if c.get("careers") or c.get("feed")),
        "with_public_feed": sum(1 for c in comps if c.get("feed")),
        "with_job_system_detected": sum(1 for c in comps if c.get("ats")),
        "companies_with_open_tech_roles": len(hiring),
        "roles": len(roles),
        "roles_espoo": sum(1 for r in roles if r.get("is_espoo", {}).get("value")),
        "roles_english_enough": lang.get("english_enough", 0),
        "roles_by_language_requirement": dict(lang),
        "fields_kept": stats["kept"],
        "fields_not_stated": stats["absent"],
        "fields_dropped": stats["dropped"],
        "roles_dropped_by_validate": stats["roles_dropped"],
        "roles_by_source": dict(Counter(r["source"] for r in roles)),
        "roles_by_job_system": dict(Counter(r.get("ats") or "none" for r in roles)),
        "companies_by_source": dict(Counter(c.get("source") or "none" for c in comps)),
        "companies_by_job_system": dict(Counter(c.get("ats") or "none" for c in comps)),
        "candidates_dropped_why": dict(drops),
        "llm": diag.get("llm"),
        "fetch": diag.get("fetch"),
    }


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "--print"
    out = line(None if arg == "--print" else arg)
    if arg != "--print":
        with (HERE / "metrics.jsonl").open("a") as f:
            f.write(json.dumps(out, ensure_ascii=False) + "\n")
    print({k: out[k] for k in ("companies_checked", "with_careers_page_or_feed", "companies_with_open_tech_roles", "roles", "roles_english_enough", "fields_kept", "fields_dropped")})
    print("roles by job system", out["roles_by_job_system"])
    print("companies by job system", out["companies_by_job_system"])
