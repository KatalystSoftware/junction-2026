"""ATS detection and public job feed parsers.

Each parser takes the cached (meta, body) of a feed URL and returns a list of items:
  key       stable id of the job inside the feed
  text      canonical text of this one job (what validate.py narrows quotes to)
  title, url, location, posted, employment, remote   verbatim strings as they appear in the feed
  body      readable description text handed to the LLM (each part is a substring of `text`)
"""

import html
import json
import re
import urllib.parse

import lib


def plain(s):
    return lib.norm(lib.strip_tags(html.unescape(s or "")))


def _s(v):
    return v if isinstance(v, str) and v.strip() else None


def _item(key, obj, title, url, location, posted, employment, remote, parts):
    return {
        "key": str(key),
        "text": lib.json_text(obj),
        "title": _s(title),
        "url": _s(url),
        "location": _s(location),
        "posted": _s(posted),
        "employment": _s(employment),
        "remote": remote,
        "body": "\n\n".join(p for p in (plain(x) for x in parts if x) if p),
    }


def _json(body):
    try:
        return json.loads(body.decode("utf-8", "replace"))
    except Exception:
        return None


def parse_greenhouse(meta, body):
    d = _json(body) or {}
    out = []
    for j in d.get("jobs", []) if isinstance(d, dict) else []:
        loc = (j.get("location") or {}).get("name")
        out.append(_item(j.get("id"), j, j.get("title"), j.get("absolute_url"), loc,
                         j.get("first_published") or j.get("updated_at"), None, None, [j.get("content")]))
    return out


def parse_lever(meta, body):
    d = _json(body)
    out = []
    for j in d if isinstance(d, list) else []:
        cat = j.get("categories") or {}
        parts = [j.get("descriptionPlain") or j.get("description")]
        for l in j.get("lists") or []:
            parts += [l.get("text"), l.get("content")]
        parts.append(j.get("additionalPlain") or j.get("additional"))
        out.append(_item(j.get("id"), j, j.get("text"), j.get("hostedUrl"), cat.get("location"),
                         None, cat.get("commitment"), j.get("workplaceType"), parts))
    return out


def parse_ashby(meta, body):
    d = _json(body) or {}
    out = []
    for j in d.get("jobs", []) if isinstance(d, dict) else []:
        out.append(_item(j.get("id"), j, j.get("title"), j.get("jobUrl"), j.get("location"),
                         j.get("publishedAt"), j.get("employmentType"),
                         # isRemote is true on hybrid roles too; workplaceType is Remote/Hybrid/OnSite
                         j.get("workplaceType"),
                         [j.get("descriptionPlain") or j.get("descriptionHtml")]))
    return out


def parse_recruitee(meta, body):
    d = _json(body) or {}
    out = []
    for j in d.get("offers", []) if isinstance(d, dict) else []:
        out.append(_item(j.get("id"), j, j.get("title"), j.get("careers_url"), j.get("location"),
                         j.get("published_at") or j.get("created_at"), j.get("employment_type_code"),
                         "remote" if j.get("remote") else None,
                         [j.get("description"), j.get("requirements")]))
    return out


def parse_workable(meta, body):
    d = _json(body) or {}
    out = []
    for j in d.get("jobs", []) if isinstance(d, dict) else []:
        city, country = _s(j.get("city")), _s(j.get("country"))
        out.append(_item(j.get("shortcode"), j, j.get("title"), j.get("url"), city or country,
                         j.get("published_on") or j.get("created_at"), j.get("employment_type"),
                         "remote" if j.get("telecommuting") else None, [j.get("description")]))
        out[-1]["location2"] = country if city else None
    return out


_RSS_ITEM = re.compile(r"<item\b[^>]*>(.*?)</item>", re.S | re.I)


def _tag(xml, name):
    m = re.search(rf"<{name}\b[^>]*>(.*?)</{name}>", xml, re.S | re.I)
    if not m:
        return None
    v = m.group(1).replace("<![CDATA[", "").replace("]]>", "")
    return v.strip() or None


def parse_teamtailor(meta, body):
    doc = lib.decode(body, meta.get("content_type", ""))
    out = []
    for m in _RSS_ITEM.finditer(doc):
        x = m.group(1)
        desc = _tag(x, "description")
        locs = []
        for lm in re.finditer(r"<tt:location\b[^>]*>(.*?)</tt:location>", x, re.S):
            city, country = _tag(lm.group(1), "tt:city"), _tag(lm.group(1), "tt:country")
            name = _tag(lm.group(1), "tt:name")
            locs.append((html.unescape(city or name or ""), html.unescape(country or "")))
        link = _tag(x, "link")
        out.append({
            "key": _tag(x, "guid") or link,
            "text": lib.html_text(x),
            "title": plain(_tag(x, "title")) or None,
            "url": html.unescape(link) if link else None,
            "location": locs[0][0] or locs[0][1] if locs else None,
            "locations": [", ".join(p for p in l if p) for l in locs],
            "location_parts": [p for l in locs for p in l if p],
            "posted": _tag(x, "pubDate"),
            "employment": None,
            "remote": _tag(x, "remoteStatus"),
            "body": plain(desc),
        })
    return out


def parse_personio(meta, body):
    doc = lib.decode(body, meta.get("content_type", ""))
    out = []
    for m in re.finditer(r"<position\b[^>]*>(.*?)</position>", doc, re.S | re.I):
        x = m.group(1)
        pid = _tag(x, "id")
        base = urllib.parse.urlsplit(meta["url"])
        descs = [plain(v.group(1)) for v in re.finditer(r"<jobDescription>(.*?)</jobDescription>", x, re.S)]
        out.append({
            "key": pid,
            "text": lib.html_text(x),
            "title": plain(_tag(x, "name")) or None,
            # personio's feed has no posting URL; the public page is /job/<id> on the same host
            "url": f"{base.scheme}://{base.netloc}/job/{pid}",
            "url_built": True,
            "location": plain(_tag(x, "office")) or None,
            "posted": _tag(x, "createdAt"),
            "employment": _tag(x, "schedule"),
            "remote": None,
            "body": "\n\n".join(descs),
        })
    return out


_ORACLE_SKIP = ("ExternalContactName", "ExternalContactEmail", "HiringManager", "links", "media")


def parse_oracle(meta, body):
    """One posting from Oracle Recruiting's public job-requisition resource (the detail call). The
    public page is a script shell, so this JSON is the posting text."""
    d = _json(body) or {}
    u = urllib.parse.urlsplit(meta["url"])
    site = re.search(r"siteNumber=([\w-]+)", urllib.parse.unquote(u.query))
    out = []
    for j in d.get("items", []) if isinstance(d, dict) else []:
        if not isinstance(j, dict) or not j.get("Id") or not site:
            continue
        obj = {k: v for k, v in j.items() if k not in _ORACLE_SKIP}
        places = [w for w in (j.get("workLocation") or []) + (j.get("otherWorkLocations") or []) if isinstance(w, dict)]
        names = [w.get("TownOrCity") for w in places if w.get("Country") == "FI"] + [j.get("PrimaryLocation")]
        names += [s.get("Name") for s in j.get("secondaryLocations") or [] if isinstance(s, dict)]
        locs = list(dict.fromkeys(x.strip() for x in names if _s(x)))
        out.append(_item(j["Id"], obj, j.get("Title"),
                         f"{u.scheme}://{u.netloc}/hcmUI/CandidateExperience/en/sites/{site.group(1)}/job/{j['Id']}",
                         locs[0] if locs else None, j.get("ExternalPostedStartDate"), j.get("JobSchedule"),
                         _s(j.get("WorkplaceType")),
                         [j.get("ExternalDescriptionStr"), j.get("ExternalResponsibilitiesStr"),
                          j.get("ExternalQualificationsStr"), j.get("OrganizationDescriptionStr")]))
        out[-1]["locations"] = locs
        out[-1]["url_built"] = True  # the feed has no posting URL; the public page is /job/<Id> on the same site
    return out


PARSERS = {
    "oracle": parse_oracle,
    "greenhouse": parse_greenhouse,
    "lever": parse_lever,
    "ashby": parse_ashby,
    "recruitee": parse_recruitee,
    "workable": parse_workable,
    "teamtailor": parse_teamtailor,
    "personio": parse_personio,
}

# (ats type, regex on raw page html, feed url template or None). The first group is the slug or host.
_SLUG = r"([A-Za-z0-9][A-Za-z0-9_-]{1,60})"
PATTERNS = [
    ("greenhouse", rf"(?:job-boards|boards)(?:\.eu)?\.greenhouse\.io/(?:embed/job_board(?:/js)?\?for=)?{_SLUG}",
     "https://boards-api.greenhouse.io/v1/boards/{0}/jobs?content=true"),
    ("greenhouse", rf"boards-api\.greenhouse\.io/v1/boards/{_SLUG}",
     "https://boards-api.greenhouse.io/v1/boards/{0}/jobs?content=true"),
    ("lever", rf"jobs\.lever\.co/{_SLUG}", "https://api.lever.co/v0/postings/{0}?mode=json"),
    ("lever", rf"jobs\.eu\.lever\.co/{_SLUG}", "https://api.eu.lever.co/v0/postings/{0}?mode=json"),
    ("ashby", rf"jobs\.ashbyhq\.com/{_SLUG}", "https://api.ashbyhq.com/posting-api/job-board/{0}"),
    ("workable", rf"apply\.workable\.com/{_SLUG}", "https://apply.workable.com/api/v1/widget/accounts/{0}?details=true"),
    ("workable", rf"//{_SLUG}\.workable\.com", "https://apply.workable.com/api/v1/widget/accounts/{0}?details=true"),
    ("recruitee", rf"//{_SLUG}\.recruitee\.com", "https://{0}.recruitee.com/api/offers/"),
    ("teamtailor", rf"//{_SLUG}\.teamtailor\.com", "https://{0}.teamtailor.com/jobs.rss"),
    ("personio", rf"//{_SLUG}\.jobs\.personio\.(?:de|com)", "https://{0}.jobs.personio.de/xml"),
    ("smartrecruiters", rf"(?:jobs|careers)\.smartrecruiters\.com/{_SLUG}", None),
    ("workday", r"//([a-z0-9-]+\.wd\d+\.myworkdayjobs\.com)", None),
    ("successfactors", r"//([a-z0-9.-]*(?:successfactors\.(?:com|eu)|jobs2web\.com))", None),
    ("jobylon", r"//([a-z0-9.-]*jobylon\.com)", None),
    ("talentadore", r"//([a-z0-9.-]*talentadore\.com)", None),
    ("laura", r"//([a-z0-9.-]*(?:rekrytointi|laura)\.(?:com|fi))/", None),
    ("sympa", r"//([a-z0-9.-]*sympahr\.net)", None),
    ("jobvite", rf"jobs\.jobvite\.com/{_SLUG}", None),
    ("bamboohr", rf"//{_SLUG}\.bamboohr\.com", None),
    ("icims", r"//([a-z0-9.-]+\.icims\.com)", None),
    ("taleo", r"//([a-z0-9.-]+\.taleo\.net)", None),
    ("oracle", r"//([a-z0-9.-]+\.oraclecloud\.com)/hcmUI", None),
    ("varbi", r"//([a-z0-9.-]*varbi\.com)", None),
    ("reachmee", r"//([a-z0-9.-]*reachmee\.com)", None),
    ("hibob", r"//([a-z0-9.-]+\.careers\.hibob\.com)", None),
    ("rippling", rf"ats\.rippling\.com/{_SLUG}", None),
    ("pinpoint", r"//([a-z0-9-]+\.pinpointhq\.com)", None),
    ("breezy", r"//([a-z0-9-]+\.breezy\.hr)", None),
    ("join", rf"join\.com/companies/{_SLUG}", None),
]
_SKIP_SLUGS = {"embed", "www", "api", "app", "careers", "jobs", "support", "help", "blog", "cdn", "assets", "widget"}
# teamtailor and recruitee also run on the company's own domain; these markers give them away
_TT_MARK = re.compile(r"teamtailor-cdn\.com|assets-aws\.teamtailor-cdn|teamtailor\.com/|data-teamtailor|name=\"teamtailor", re.I)
_RECRUITEE_MARK = re.compile(r"recruitee(?:cdn)?\.com|d27i7n2isjbnbi\.cloudfront\.net/careers", re.I)


def detect(page_url, doc):
    """Find ATS references in a page. Returns a list of {type, quote, feed_url}; `quote` is the
    verbatim string from the page that gave the ATS away."""
    found = []
    seen = set()
    for typ, pat, tmpl in PATTERNS:
        for m in re.finditer(pat, doc, re.I):
            slug = m.group(1)
            if slug.lower() in _SKIP_SLUGS:
                continue
            feed = tmpl.format(slug) if tmpl else None
            if (typ, feed or slug.lower()) in seen:
                continue
            seen.add((typ, feed or slug.lower()))
            found.append({"type": typ, "quote": m.group(0), "feed_url": feed})
    host = urllib.parse.urlsplit(page_url)
    base = f"{host.scheme}://{host.netloc}"
    if not any(f["type"] == "teamtailor" for f in found):
        # a link to <other host>/jobs/<id>-<slug> is a teamtailor career site on the company's own domain
        m = re.search(r"(https://[\w.-]+)/jobs/\d{6,}(?:-[\w-]+)?", doc)
        if m and m.group(1) != base:
            found.append({"type": "teamtailor", "quote": m.group(0), "feed_url": m.group(1) + "/jobs.rss"})
        m = _TT_MARK.search(doc)
        if m:
            found.append({"type": "teamtailor", "quote": m.group(0), "feed_url": base + "/jobs.rss"})
            # the widget does not say where the career site is; <company>.teamtailor.com is the default
            label = host.netloc.split(":")[0].split(".")[-2] if host.netloc.count(".") else ""
            if label and label not in _SKIP_SLUGS and "teamtailor" not in host.netloc:
                found.append({"type": "teamtailor", "quote": m.group(0), "feed_url": f"https://{label}.teamtailor.com/jobs.rss"})
    if not any(f["type"] == "recruitee" for f in found):
        m = _RECRUITEE_MARK.search(doc)
        if m and "recruitee" in doc.lower():
            found.append({"type": "recruitee", "quote": m.group(0), "feed_url": base + "/api/offers/"})
    return found


def job_postings(doc):
    """schema.org JobPosting objects from a page's JSON-LD."""
    out = []

    def walk(x):
        if isinstance(x, dict):
            t = x.get("@type")
            if t == "JobPosting" or (isinstance(t, list) and "JobPosting" in t):
                out.append(x)
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)

    for ld in lib.ld_json(doc):
        walk(ld)
    return out
