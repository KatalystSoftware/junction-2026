"""The one check. Fixed before round 1 and never loosened.

Every field of every record is re-checked against the cached raw response of its `source_url`:

  quote     `quote` is a verbatim substring (after whitespace normalisation) of the canonical text
            of the cached response. For a role that came out of a feed with many jobs, the text
            is narrowed to that role's own item in the feed, so a quote cannot be borrowed from a
            neighbouring job. A quote that carries an email, phone number or contact person fails.
  url       as `quote`, and `value` must be the quoted string itself or that string resolved
            against `source_url` (relative links).
  fetched   `value` is a URL that we fetched ourselves and got a 2xx for (`source_url` == `value`).
  registry  structured registry API field: no quote, but every string in `value` must appear in
            the cached API response.
  derived   computed by code from another field of the same record (`derived_from`); kept only
            while that field is kept.
  absent    `value` is "not_stated": nothing in the source says it, so there is nothing to quote.
            Kept, counted separately, never counted as grounded.

A failing field is dropped. A role without a grounded title and URL is dropped.

  python3 validate.py           check the committed companies.json and roles.json, exit 1 on any failure
  python3 validate.py --apply   read work/*.raw.json, drop what fails, write companies.json and roles.json
"""

import json
import sys
import urllib.parse
from collections import Counter
from functools import lru_cache
from pathlib import Path

import ats
import lib

HERE = Path(__file__).resolve().parent
KINDS = {"quote", "url", "fetched", "registry", "derived", "absent"}


@lru_cache(maxsize=4096)
def _doc_text(url):
    return lib.source_text(url)


@lru_cache(maxsize=65536)
def _item_text(url, parser, key):
    hit = lib.cached(url)
    if hit is None or not lib.ok(hit[0]):
        return None
    for it in ats.PARSERS[parser](hit[0], hit[1]):
        if str(it["key"]) == str(key):
            return it["text"]
    return None


def _leaves(v):
    if isinstance(v, dict):
        for x in v.values():
            yield from _leaves(x)
    elif isinstance(v, list):
        for x in v:
            yield from _leaves(x)
    elif isinstance(v, str):
        yield v


def check_field(f, item=None):
    """Return None if the field is grounded, else the reason it fails. `derived` is handled by
    the caller."""
    if not isinstance(f, dict) or "value" not in f:
        return "not a field object"
    kind = f.get("kind", "quote")
    if kind not in KINDS:
        return f"unknown kind {kind}"
    if kind == "absent":
        return None if f["value"] == "not_stated" and not f.get("quote") else "absent field with a value"
    if kind == "derived":
        return None
    src = f.get("source_url")
    if not src or not f.get("retrieved_at"):
        return "no source_url or retrieved_at"
    if kind == "fetched":
        hit = lib.cached(src)
        if f["value"] != src:
            return "fetched url differs from source_url"
        return None if hit and lib.ok(hit[0]) else "source not cached with 2xx"
    if item and item.get("url") == src:
        text = _item_text(src, item["parser"], item["key"])
    else:
        text = _doc_text(src)
    if text is None:
        return "source not cached with 2xx"
    if kind == "registry":
        for s in _leaves(f["value"]):
            if lib.norm(s) not in text:
                return "registry value not in api response"
        return None
    q = f.get("quote")
    if not isinstance(q, str) or not lib.norm(q):
        return "no quote"
    if lib.norm(q) not in text:
        return "quote not in source"
    if kind == "url":
        if f["value"] not in (q.strip(), urllib.parse.urljoin(src, q.strip())):
            return "url value does not match quote"
        return None
    if lib.has_personal_data(q) or (isinstance(f["value"], str) and lib.has_personal_data(f["value"])):
        return "personal data in quote"
    return None


def clean_record(rec, stats, item=None):
    """Drop failing fields from a record in place. Fields are dict values carrying `value`, or
    lists of such dicts."""
    dropped = set()
    for name in list(rec):
        v = rec[name]
        if isinstance(v, dict) and "value" in v:
            if v.get("kind") == "derived":
                continue
            why = check_field(v, item)
            if why:
                stats["dropped"] += 1
                stats["why"][f"{name}: {why}"] += 1
                dropped.add(name)
                del rec[name]
            else:
                stats["absent" if v.get("kind") == "absent" else "kept"] += 1
        elif isinstance(v, list) and v and all(isinstance(x, dict) and "value" in x for x in v):
            keep = []
            for x in v:
                why = check_field(x, item)
                if why:
                    stats["dropped"] += 1
                    stats["why"][f"{name}[]: {why}"] += 1
                else:
                    stats["kept"] += 1
                    keep.append(x)
            rec[name] = keep
    for name in list(rec):
        v = rec[name]
        if isinstance(v, dict) and v.get("kind") == "derived":
            if v.get("derived_from") not in rec:
                stats["dropped"] += 1
                stats["why"][f"{name}: parent field dropped"] += 1
                del rec[name]
            else:
                stats["kept"] += 1
    return dropped


def run(companies, roles):
    stats = {"kept": 0, "absent": 0, "dropped": 0, "roles_dropped": 0, "why": Counter()}
    for c in companies:
        clean_record(c, stats)
    companies = [c for c in companies if "name" in c]
    ids = {c["id"] for c in companies}
    out = []
    for r in roles:
        clean_record(r, stats, r.get("item"))
        if "title" in r and "url" in r and r.get("company_id") in ids:
            out.append(r)
        else:
            stats["roles_dropped"] += 1
    return companies, out, stats


def main():
    apply = "--apply" in sys.argv
    src = HERE / "work" if apply else HERE
    suffix = ".raw.json" if apply else ".json"
    companies = json.loads((src / f"companies{suffix}").read_text())
    roles = json.loads((src / f"roles{suffix}").read_text())
    n_c, n_r = len(companies), len(roles)
    companies, roles, stats = run(companies, roles)
    stats["why"] = dict(stats["why"].most_common())
    print(f"companies {len(companies)}/{n_c}  roles {len(roles)}/{n_r}")
    print(f"fields kept {stats['kept']}  not stated {stats['absent']}  dropped {stats['dropped']}")
    for why, n in list(stats["why"].items())[:25]:
        print(f"  {n:5d}  {why}")
    if apply:
        dump = lambda p, x: p.write_text(json.dumps(x, ensure_ascii=False, indent=1) + "\n")
        dump(HERE / "companies.json", companies)
        dump(HERE / "roles.json", roles)
        (HERE / "work" / "validate_stats.json").write_text(json.dumps(stats))
        return 0
    bad = stats["dropped"] + stats["roles_dropped"] + (n_c - len(companies))
    print("OK" if not bad else "FAIL")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
