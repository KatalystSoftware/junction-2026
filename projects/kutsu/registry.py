"""A company's Finnish business ID (Y-tunnus), for a company found by its name or domain rather than taken from our
Espoo register list (companies.json, whose ids already are business IDs).

    python3 registry.py              # fill in business_id for every company in signals.json that has none
    python3 registry.py nitor.com    # look one up and print it, changing nothing

First the open trade register (PRH's YTJ, free and keyless, the source seeds.py uses): search by the company's name
and keep only companies whose registered website is this domain. A group often registers its website for several
companies (Nitor Creations, Nitor Group, Nitor Delta), so the operating one is preferred: not a holding company or
head office, and in a tech line of business when one is. Failing that, the company's own site: a Finnish company
usually prints its Y-tunnus (or its VAT number, FI and the same digits) in a footer, imprint or privacy page. A
number found there is used only when it passes the check digit and the register confirms it belongs to a company
with this website or this name.

Nothing is guessed. With no match, or several equal ones, a company has no business ID, which is also the right
answer for one registered abroad. Every request goes through lib.fetch: cached, rate limited, robots.txt obeyed.
"""

import html
import json
import re
import sys
import urllib.parse

import lib
import seeds

ID = re.compile(r"(?<![\d-])(\d{7}-\d)(?![\d-])")
VAT = re.compile(r"\bFI ?(\d{8})\b")
# a holding company or head office registers the group's website too; it is not the employer people meet
HEAD = {"64200", "64201", "64202", "64209", "70100"}
# pages where a Finnish site prints its business ID, in the order tried after the front page
PAGES = ["", "yhteystiedot", "contact", "en/contact", "contact-us", "tietosuojaseloste", "privacy-policy", "privacy",
         "about", "about-us", "imprint"]


def valid(bid):
    """The Y-tunnus check digit: weights 7 9 10 5 8 4 2 over the seven digits, 11 minus the remainder of 11."""
    if not re.fullmatch(r"\d{7}-\d", bid or ""):
        return False
    r = sum(int(d) * w for d, w in zip(bid[:7], (7, 9, 10, 5, 8, 4, 2))) % 11
    return r != 1 and int(bid[-1]) == (0 if r == 0 else 11 - r)


def _site(c):
    return seeds.domain((c.get("website") or {}).get("url") or "") if (c.get("website") or {}).get("url") else ""


def _line(c):
    return str((c.get("mainBusinessLine") or {}).get("type") or "")


def _live(c):
    return seeds._name(c) and not c.get("endDate") and not c.get("companySituations")


def pick(found):
    """The one operating company among those sharing a website, or None when it cannot be told."""
    found = list({seeds._name(c) and c["businessId"]["value"]: c for c in found if _live(c)}.values())
    operating = [c for c in found if _line(c) not in HEAD and "holding" not in seeds._name(c).casefold()]
    tech = [c for c in operating if _line(c) in seeds.TOL]
    for group in (tech, operating, found):
        if len(group) == 1:
            return group[0]
    return None


def record(c, url, meta, found_on=None):
    return {"value": c["businessId"]["value"], "name": seeds._name(c), "source_url": url, "found_on": found_on,
            "retrieved_at": meta.get("retrieved_at") or lib.now_iso(), "kind": "registry"}


def by_name(name, domain, pages=3):
    """Companies in the register under this name whose registered website is this domain."""
    url = f"{seeds.PRH}?name={urllib.parse.quote(name)}"
    hits, meta = [], {}
    for page in range(1, pages + 1):
        meta, d = seeds._get(f"{url}&page={page}" if page > 1 else url)
        hits += [c for c in d.get("companies", []) if _site(c) == domain]
        if page * 100 >= (d.get("totalResults") or 0):
            break
    chosen = pick(hits)
    return record(chosen, url, meta) if chosen else None


def by_id(bid):
    url = f"{seeds.PRH}?businessId={bid}"
    meta, d = seeds._get(url)
    found = [c for c in d.get("companies", []) if c["businessId"]["value"] == bid and _live(c)]
    return (found[0], url, meta) if found else (None, url, meta)


def text_of(body):
    return html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", body.decode("utf-8", "replace"))))


def from_site(name, domain):
    """A business ID the company prints on its own site, confirmed by the register."""
    first = (name.split() or [""])[0].casefold()
    for path in PAGES:
        page = f"https://{domain}/{path}"
        meta, body = lib.fetch(page)
        if not lib.ok(meta):
            continue
        text = text_of(body)
        seen = ID.findall(text) + [f"{v[:7]}-{v[7]}" for v in VAT.findall(text)]
        for bid in dict.fromkeys(b for b in seen if valid(b)):
            c, url, rmeta = by_id(bid)
            if c and (_site(c) == domain or (first and first in seeds._name(c).casefold())):
                return record(c, url, rmeta, found_on=page)
    return None


def business_id(name, domain):
    """The business ID of a company known by its name and domain, with where it came from, or None."""
    if not domain:
        return None
    names = dict.fromkeys(n for n in (name, name.split(" ")[0] if " " in name else "", domain.split(".")[0]) if n)
    for n in names:
        found = by_name(n, domain)
        if found:
            return found
    return from_site(name, domain)


def main():
    if len(sys.argv) > 1:
        print(json.dumps(business_id(sys.argv[1].split(".")[0].title(), sys.argv[1]), indent=1, ensure_ascii=False))
        return
    import signals  # noqa: PLC0415 (not needed for a single lookup)

    briefs = json.loads(signals.OUT.read_text())
    companies = {c["id"]: c for c in json.loads((lib.HERE / "companies.json").read_text())}
    changed = []
    for b in briefs:
        if b.get("business_id"):
            continue
        c = companies.get(b["id"])
        if c and c.get("business_id"):  # from the register already: its id is its business ID
            b["business_id"] = {"value": c["business_id"]["value"], "name": c["name"]["value"],
                                "source_url": c["business_id"]["source_url"], "found_on": None,
                                "retrieved_at": c["business_id"]["retrieved_at"], "kind": "registry"}
        else:
            domain = seeds.domain(b.get("website") or "") or (b["id"] if "." in b["id"] else "")
            b["business_id"] = business_id(b["name"], domain)
            print(f"{b['id']:24} {(b['business_id'] or {}).get('value') or 'none found':12} "
                  f"{(b['business_id'] or {}).get('name') or ''}", file=sys.stderr)
        changed.append(b)
    signals.save(changed)
    print(f"business IDs: {sum(1 for b in briefs if b.get('business_id'))} of {len(briefs)} companies", file=sys.stderr)


if __name__ == "__main__":
    main()
