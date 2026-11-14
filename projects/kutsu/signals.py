"""Public-image signals: what the open web says about a company, with every claim quoted.

    sops exec-env ../../secrets/secrets.yaml 'python3 signals.py 2639822-1 Varjo wolt.com'

Each argument is a company id from companies.json, or the name or domain of any company. Context.dev
says who the company is (brand record by domain, or by name when we have no domain) and reads its
careers page; Exa searches the open web (news, funding and growth, the company's own site, talks
and interviews); then one small-model call turns all of those pages into signals. A signal is a
claim plus a quote that must appear character for character in the search result it cites;
signals that fail that check are dropped. So are signals that name a person, found by a second
small call that only looks for names. The talent outlook is inference and is stored apart, citing
the signals it rests on.

Every paid request is cached under api-cache/<service>/ (raw request and response, no keys), so a
rerun costs nothing and works without keys. The cache is in git so the whole team reuses it; it
holds third-party article text, people's names included, and has to go before this repository is
made public. signals.json holds claims, quotes and URLs only.
"""

import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

import lib

API_CACHE = lib.HERE / "api-cache"
EXA = "https://api.exa.ai/search"
ANTHROPIC = "https://api.anthropic.com/v1/messages"
CONTEXT = "https://api.context.dev/v1"
MODEL = "claude-haiku-5-5"
USD_PER_MTOK_IN, USD_PER_MTOK_OUT = 0.10, 0.50
SINCE = "2025-05-01T00:00:00.000Z"
# posts on social networks are mostly individuals speaking, and we keep claims about companies
SOCIAL = ["linkedin.com", "x.com", "twitter.com", "facebook.com", "instagram.com", "reddit.com"]
RESULTS = 6
TEXT_CHARS = 3000
CAREERS_CHARS = 6000
OUT = lib.HERE / "signals.json"
# a name next to a title or an appointment verb: the model's own list of people misses some
TITLE = (r"(?:CEO|CTO|CFO|COO|CPO|CMO|Chair(?:man|woman|person)?|President|Director|Head|VP|Founder|Co-founder|"
         r"Professor|Dr\.?|Partner|Manager|Officer|Lead|executive)")
NAME = r"[A-ZÅÄÖ][a-zåäöé-]+(?: [A-ZÅÄÖ][a-zåäöé-]+)+"
PERSON = re.compile(rf"\b(?:{TITLE}|appointed|welcomes|hired)\s+{NAME}"
                    rf"|{NAME}(?:,| as| joins| has joined)\s+(?:(?:the|a|an|our|its|new)\s+)*{TITLE}\b")

TYPES = ["funding", "growth", "product", "customers", "technology", "hiring", "partnership",
         "organisation", "risk", "other"]
SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["signals", "outlook"],
    "properties": {
        "signals": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["id", "type", "claim", "date", "source", "quote", "people"],
            "properties": {"id": {"type": "string"}, "type": {"type": "string", "enum": TYPES},
                           "claim": {"type": "string"},
                           "date": {"type": "string"}, "source": {"type": "integer"},
                           "quote": {"type": "string"},
                           "people": {"type": "array", "items": {"type": "string"}}}}},
        "outlook": {
            "type": "object", "additionalProperties": False,
            "required": ["momentum", "summary", "talent_needs"],
            "properties": {
                "momentum": {"type": "string", "enum": ["growing", "steady", "shrinking", "unclear"]},
                "summary": {"type": "string"},
                "talent_needs": {"type": "array", "items": {
                    "type": "object", "additionalProperties": False,
                    "required": ["need", "why", "signals", "roles"],
                    "properties": {"need": {"type": "string"}, "why": {"type": "string"},
                                   "signals": {"type": "array", "items": {"type": "string"}},
                                   "roles": {"type": "array", "items": {"type": "string"}}}}}}},
    },
}

SYSTEM = """You read web search results about one company and report what they show about how \
the company is doing and what kind of people it will need. The reader is a job seeker or a city \
employment adviser. You are strict about evidence.

The results are numbered. Some are about another company with a similar name, or only mention \
this company in passing: ignore those. The company's website and line of business are given so \
you can tell.

signals: up to 12 facts about the company from the last two years, most telling first. For each:
- id: s1, s2, s3 and so on, in order.
- type: funding, growth (revenue, headcount, new offices, markets), product (launches, \
milestones), customers (contracts, deals), technology (what they build with or research), hiring \
(stated hiring plans), partnership, organisation (acquisitions, restructuring, layoffs), risk \
(losses, disputes, cuts), other.
- claim: one plain sentence stating the fact, with numbers when the source gives them.
- date: when it happened or was published, as YYYY-MM or YYYY, or "" if the result does not say.
- source: the number of the result the fact comes from.
- quote: copied character for character from that result's text: one short contiguous span (at \
most about 200 characters), no paraphrase, no ellipsis, nothing translated.
- people: reread your claim and your quote word by word and list the name of every individual \
that appears in either; normally empty.
Report each fact once, from the best source. Report bad news as readily as good news, but only \
what a result states: never write a signal to say that something was not found. Claims are about \
the company, never about individuals: write "a new chairman from the defence industry", not who, \
and pick a quote span without the name. A signal that still names someone is discarded.

outlook: your own reading, clearly inference.
- momentum: growing, steady, shrinking, or unclear when the signals do not support a call.
- summary: two or three sentences on where the company is heading, resting on the signals and \
the open roles.
- talent_needs: up to 5 kinds of people the company is likely to need over the next year. `need` \
is a short label, `why` one sentence of reasoning, `signals` the ids of the signals that support \
it (only those that really bear on this need), `roles` the open role titles that show the company \
already hiring for it, copied exactly from the list, or empty. Leave out any need you cannot tie \
to at least one signal or open role."""


def post(service, url, body, headers, optional=False, method="POST"):
    """Send a JSON body and return the parsed response, from api-cache/ when it has been asked before.

    With optional, a request the service turns down (not found, unreadable page) comes back as
    {"error": status}, and is cached like an answer, instead of stopping the run. With method GET
    the body goes into the query string.
    """
    h = hashlib.sha256((url + "\x00" + json.dumps(body, sort_keys=True)).encode()).hexdigest()
    path = API_CACHE / service / f"{h[:24]}.json"
    if path.exists():
        return json.loads(path.read_text())["response"]
    get = method == "GET"
    req = urllib.request.Request(url + ("?" + urllib.parse.urlencode(body) if get else ""), method=method,
                                 data=None if get else json.dumps(body).encode(),
                                 headers={"content-type": "application/json", "user-agent": lib.UA, **headers()})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                resp = json.loads(r.read())
            break
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 529) and attempt < 3:
                time.sleep(float(e.headers.get("retry-after") or 2 ** attempt * 2))
                continue
            if optional and e.code in (400, 404, 408, 422):
                resp = {"error": e.code, "message": e.read(300).decode("utf-8", "replace")}
                break
            raise SystemExit(f"{service}: http {e.code} {e.read(300).decode('utf-8', 'replace')}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"url": url, "request": body, "fetched_at": lib.now_iso(), "response": resp},
                               ensure_ascii=False, indent=1))
    return resp


def short_name(name):
    return re.sub(r"\s+(Oyj Abp|Oyj|Oy Ab|Oy|Ab|sr)$", "", name, flags=re.I).strip()


def searches(name, domain):
    """The Exa requests for one company. The domain is in the query to keep namesakes out."""
    who = f"{name} ({domain})" if domain else name
    contents = {"text": {"maxCharacters": TEXT_CHARS}}
    out = [
        {"query": f"{who} company news", "category": "news", "startPublishedDate": SINCE},
        {"query": f"{who} funding round, investors, revenue, growth, new customers", "startPublishedDate": SINCE},
        {"query": f"{who} interview, podcast or conference talk about their technology and team",
         "startPublishedDate": SINCE},
    ]
    out = [{**q, "excludeDomains": SOCIAL} for q in out]
    if domain:
        out.append({"query": f"{name} engineering, technology and company updates", "includeDomains": [domain]})
    return [{**q, "numResults": RESULTS, "contents": contents} for q in out]


NAMES_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["lines"], "properties": {
    "lines": {"type": "array", "items": {
        "type": "object", "additionalProperties": False, "required": ["line", "names"],
        "properties": {"line": {"type": "integer"}, "names": {"type": "array", "items": {"type": "string"}}}}}}}
NAMES_SYSTEM = """You get numbered lines of text. Answer for every line, in order: the names of the individual \
human beings that the line mentions, written exactly as they appear in it, or an empty list. \
Companies, products, places and institutions are not people."""


def ask(system, schema, content):
    """One model call with a JSON answer. Returns (answer, usd) or (None, usd)."""
    resp = post("anthropic", ANTHROPIC, {
        "model": MODEL, "max_tokens": 5000, "thinking": {"type": "disabled"},
        "output_config": {"effort": "low", "format": {"type": "json_schema", "schema": schema}},
        "system": system, "messages": [{"role": "user", "content": content}],
    }, lambda: {"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01"})
    u = resp.get("usage") or {}
    tin = u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0) + u.get("cache_read_input_tokens", 0)
    usd = tin * USD_PER_MTOK_IN / 1e6 + u.get("output_tokens", 0) * USD_PER_MTOK_OUT / 1e6
    if resp.get("stop_reason") != "end_turn":
        return None, usd
    return json.loads(next(b["text"] for b in resp["content"] if b["type"] == "text")), usd


def context(path, body, method="POST"):
    """One Context.dev request. Returns (response, credits used)."""
    resp = post("context", f"{CONTEXT}/{path}", body,
                lambda: {"authorization": f"Bearer {os.environ['CONTEXT_DEV_API_KEY']}"}, optional=True, method=method)
    return resp, (resp.get("key_metadata") or {}).get("credits_consumed", 0)


def find(name):
    """The brand Context.dev knows by this name, as [{name, domain, country, description}] best first.

    Its lookup by name misses companies its name search finds (Nitor), so a typed name goes through
    the search and the brand record is then fetched by domain. The search matches on any word, so
    "hamina wireless" returns only other wireless companies: a result counts only when its name or
    domain has the first word typed, and when the full phrase finds none the first word is searched
    alone. The best is the one with most of the typed words in its name, domain or description,
    then a Finnish one, then an exact name.
    """
    words = re.findall(r"\w+", name.lower())
    found, credits = [], 0
    for query in dict.fromkeys([name, words[0]] if words else []):
        resp, used = context("brand/search", {"query": query[:100]}, method="GET")
        credits += used
        found = [r for r in resp.get("results") or []
                 if r.get("domain") and words[0] in f"{r.get('name') or ''} {r['domain']}".lower()]
        if found:
            break
    text = lambda r: f"{r.get('name') or ''} {r['domain']} {r.get('description') or ''}".lower()
    return sorted(found, key=lambda r: (-sum(w in text(r) for w in words), r.get("country") != "FI",
                                        (r.get("name") or "").lower() != name.lower())), credits


def identity(domain, name):
    """Who the company is, from Context.dev's brand record: by domain when we have one, else by name."""
    body = ({"type": "by_domain", "domain": domain} if domain
            else {"type": "by_name", "name": name[:30], "country_gl": "fi"})
    resp, credits = context("brand/retrieve", body)
    b = resp.get("brand")
    if resp.get("status") != "ok" or not b or not b.get("domain"):  # a 200 can still carry a failed lookup
        return None, credits
    logos = b.get("logos") or []
    # a site's own logo is usually an SVG; the first raster "logo" can be a customer's (Cisco on hamina.com)
    marks = [x for x in logos if x.get("type") == "logo"]
    logo = next((x for x in marks if x.get("url", "").endswith(".svg")), (marks or logos or [{}])[0])
    icon = next((x for x in logos if x.get("type") == "icon"), logo)  # square, for small sizes
    address, links = b.get("address") or {}, b.get("links") or {}
    return {"source": "context.dev brand/retrieve", "retrieved_at": lib.now_iso(), "domain": b["domain"],
            "name": b.get("title"), "slogan": b.get("slogan"), "description": b.get("description"),
            "logo": logo.get("url"), "logo_on": "dark" if logo.get("mode") == "dark" else "light",
            "icon": icon.get("url"), "icon_on": "dark" if icon.get("mode") == "dark" else "light",
            "colors": [c["hex"] for c in (b.get("colors") or [])[:3]],
            "industries": [f"{i['industry']}: {i['subindustry']}" for i in (b.get("industries") or {}).get("eic") or []],
            "employees": (b.get("employees") or {}).get("range"),
            "city": address.get("city"), "country": address.get("country"),
            "careers": links.get("careers"), "blog": links.get("blog"),
            "socials": {x["type"]: x["url"] for x in b.get("socials") or []}}, credits


def careers_page(url):
    """The company's careers page as one more result to quote from: what it tells candidates itself."""
    resp, credits = context("web/scrape", {"url": url, "formats": {"markdown": True},
                                           "markdownParams": {"includeLinks": False}})
    markdown = resp.get("markdown") or {}  # a 200 can still carry a failed output: success says which
    text = lib.norm(markdown.get("data") or "")[:CAREERS_CHARS] if markdown.get("success") else ""
    if len(text) < 200:
        return None, credits
    title = (resp.get("metadata") or {}).get("title") or "Careers"
    return {"url": url, "title": f"{title} (the company's own careers page)", "published": "", "text": text}, credits


FAMILIES = ["Software", "AI and data", "Embedded and electronics", "Semiconductors and photonics", "Quantum",
            "Space and RF", "Mechanical and manufacturing", "Research and science", "Security", "Product and design",
            "Sales and business", "Operations and support", "Leadership"]
SENIORITY = ["Early career", "Experienced", "Senior", "Lead"]
CARD_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["pitch", "momentum", "needs", "also"],
    "properties": {
        "pitch": {"type": "string"},
        "also": {"type": "array", "items": {"type": "string"}},
        "momentum": {"type": "string", "enum": ["growing", "steady", "shrinking", "unclear"]},
        "needs": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["title", "family", "why", "can_do", "skills", "seniority", "signals", "roles"],
            "properties": {"title": {"type": "string"}, "family": {"type": "string", "enum": FAMILIES},
                           "why": {"type": "string"}, "can_do": {"type": "array", "items": {"type": "string"}},
                           "skills": {"type": "array", "items": {"type": "string"}},
                           "seniority": {"type": "string", "enum": SENIORITY},
                           "signals": {"type": "array", "items": {"type": "string"}},
                           "roles": {"type": "array", "items": {"type": "string"}}}}}}}
CARD_SYSTEM = """You draft the short card a city talent office shows job seekers about one employer at a \
recruitment event. You get the company, its open roles if we know them, and numbered statements. \
Every statement was checked against a public source; use nothing else.

pitch: one sentence, at most 18 words, plain words: what the company is doing right now that a \
candidate would care about. No praise words such as leading, innovative or cutting-edge.

momentum: growing, steady or shrinking by what the statements show; unclear when they do not say.

needs: the talent the company most plausibly needs now, strongest first, at most 4. Many needs are \
never posted as a job, so read them from funding, growth, new sites, new products and new customers \
as well as from open roles. Fewer is better than weak: with thin statements give one, or none. Each:
- title: 2 to 5 words naming a kind of person in the plural, in sentence case, such as "RF and \
antenna engineers" or "Enterprise sales leads". No slash, no company or product name.
- family: the closest one from the list.
- why: one sentence, at most 16 words: the fact in the statements that creates this need. Say what \
happened, not that it "suggests" or "implies" something, and do not repeat the title.
- can_do: 2 or 3 things this person must be able to do in the job, each a line of 5 to 10 words \
that starts with a verb and names the real work, such as "Design RF front ends for small \
satellites" or "Run ISO 27001 audits across cloud services". Something that can be shown in a \
work sample or a conversation. Take them from an open role's must-haves when there is one.
- skills: 3 to 5 tools, methods or fields this person knows, one to three words each, such as \
"GaN epitaxy", "Embedded C", "ISO 13485". Hard skills only: no soft skills, no traits of character.
- seniority: the level most of the need sits at.
- signals: the ids of the one to three statements it rests on.
- roles: open role titles, copied exactly, that are this need; empty when there are none.
A need must rest on at least one statement or one open role. Never name a person.

also: up to 4 further kinds of people a company like this one often needs and you did not list, \
as titles of the same form. These are guesses to offer, not claims, so they need no statement."""


LANGUAGE = {"english_enough": "English is enough", "finnish_required": "Finnish needed"}
WORKPLACE = {"onsite": "On site", "hybrid": "Hybrid", "remote": "Remote"}


def from_posts(titles, posts):
    """Working language, workplace and place for a need, read off the job posts it covers.

    Each comes with the sentence and page it was read from. What no post states is left out, for
    the company to answer; whether it hires from abroad is never in a post, so that is always theirs.
    """
    mine = [p for p in posts if p["title"]["value"] in titles]
    out, sources = {}, {}
    for key, field, labels in (("language", "language_requirement", LANGUAGE), ("workplace", "workplace", WORKPLACE),
                               ("where", "location", None)):
        stated = [p[field] for p in mine if p.get(field) and (p[field].get("value") in labels if labels else p[field].get("value"))]
        if not stated:
            continue
        values = [f["value"] for f in stated]
        best = max(set(values), key=values.count)
        first = next(f for f in stated if f["value"] == best)
        out[key] = labels[best] if labels else best
        if first.get("quote"):
            sources[key] = {"quote": first["quote"], "url": first.get("source_url")}
    return {**out, "sources": sources}


def card(company, posts, signals, named):
    """The needs and pitch, written from the statements that passed the checks. Returns (card, usd)."""
    roles = [p["title"]["value"] for p in posts]
    must = lambda p: "; ".join(m["value"] for m in p.get("must_have") or [])[:300]
    listed = "\n".join(f"- {p['title']['value']}" + (f" (must have: {must(p)})" if must(p) else "") for p in posts)
    lines = [f"Company: {company['name']}", f"What it does: {company['what_they_do'] or 'unknown'}",
             "Open tech roles:" + (f"\n{listed}" if posts else f" {company['no_roles']}"), ""]
    lines += [f"{x['id']} [{x['type']}{', ' + x['date'] if x['date'] else ''}] {x['claim']}" for x in signals]
    answer, usd = ask(CARD_SYSTEM, CARD_SCHEMA, "\n".join(lines)) if signals or roles else (None, 0.0)
    answer = answer or {"pitch": "", "momentum": "unclear", "needs": [], "also": []}
    ids = {x["id"] for x in signals}
    clean = lambda t: not PERSON.search(t) and not any(p in t for p in named)
    needs = [{**n, "can_do": [k.strip() for k in n["can_do"] if k.strip()][:3],
              "skills": [k.strip() for k in n["skills"] if k.strip()][:5],
              "signals": [i for i in n["signals"] if i in ids][:3], "roles": [t for t in n["roles"] if t in roles]}
             for n in answer["needs"][:4]]
    needs = [{**n, **from_posts(n["roles"], posts)} for n in needs]
    return {"kind": "inferred", "method": f"{MODEL} reading of the checked statements and open roles",
            "pitch": answer["pitch"] if clean(answer["pitch"]) else "", "momentum": answer["momentum"],
            "also": [t.strip() for t in answer["also"] if t.strip() and clean(t)][:4],
            "needs": [n for n in needs if (n["signals"] or n["roles"])
                      and clean(" ".join([n["title"], n["why"], *n["can_do"]]))]}, usd


POSTING_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["headline", "intro", "you_will", "you_bring", "why_now"],
    "properties": {"headline": {"type": "string"}, "intro": {"type": "string"}, "why_now": {"type": "string"},
                   "you_will": {"type": "array", "items": {"type": "string"}},
                   "you_bring": {"type": "array", "items": {"type": "string"}}}}
POSTING_SYSTEM = """You draft a short job posting for one role at one company, for the company to edit before \
it is used. Use only the facts given: the company's description, the role, and the numbered \
statements, each checked against a public source.
headline: the role in the singular, sentence case.
intro: two sentences: what the company does, then why this role exists now, with a fact.
you_will: four lines of 6 to 12 words, each starting with a verb.
you_bring: four lines of 4 to 10 words, built on what the person must be able to do, knows, and the level.
State the working language and workplace only when they are given.
why_now: one sentence with one concrete recent fact from the statements, and not one the intro used.
Describe the company's products only in the words the description and statements use.
No praise words, nothing about salary, benefits or culture, and no names of people."""


def posting(brief, need):
    """A drafted job posting for one need of a stored brief. Returns the posting, or None."""
    lines = [f"Company: {brief['name']}", f"What it does: {brief['card']['pitch'] or (brief['identity'] or {}).get('description') or 'unknown'}",
             f"Role: {need['title']}", f"Level: {need['seniority']}", f"Must be able to: {'; '.join(need.get('can_do') or [])}",
             f"Knows: {', '.join(need['skills'])}",
             f"Working language: {need.get('language') or 'not said'}. Workplace: {need.get('workplace') or 'not said'}"
             f"{', ' + need['where'] if need.get('where') else ''}.",
             f"Why the company needs it: {need['why']}", ""]
    lines += [f"{x['id']} [{x['type']}{', ' + x['date'] if x['date'] else ''}] {x['claim']}" for x in brief["signals"]]
    answer, _ = ask(POSTING_SYSTEM, POSTING_SCHEMA, "\n".join(lines))
    return answer


ROLE_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["title", "why", "can_do", "skills", "seniority", "family"],
    "properties": {"title": {"type": "string"}, "why": {"type": "string"}, "family": {"type": "string", "enum": FAMILIES},
                   "can_do": {"type": "array", "items": {"type": "string"}},
                   "skills": {"type": "array", "items": {"type": "string"}},
                   "seniority": {"type": "string", "enum": SENIORITY}}}
ROLE_SYSTEM = """A company signing up for a recruitment event describes, in one line, a kind of person it wants \
to meet. Turn that line into a role for the company to correct. You also get what the company does \
and numbered statements about it, each checked against a public source.
- title: 2 to 5 words naming the kind of person in the plural, in sentence case.
- why: one sentence, at most 16 words, when a statement explains the need; otherwise an empty string. \
Do not invent a reason.
- can_do: 2 or 3 things this person must be able to do, each 5 to 10 words starting with a verb, \
fitted to what this company does.
- skills: 3 to 5 tools, methods or fields this person knows, one to three words each. Hard skills only.
- seniority and family: the closest of the choices, by what the line says.
Never name a person."""


def role(brief, line):
    """A need drafted from one line a company typed about who else it wants to meet, or None."""
    lines = [f"Company: {brief['name']}", f"What it does: {brief['card']['pitch'] or (brief['identity'] or {}).get('description') or 'unknown'}",
             f"The line: {line}", ""]
    lines += [f"{x['id']} [{x['type']}{', ' + x['date'] if x['date'] else ''}] {x['claim']}" for x in brief["signals"]]
    answer, _ = ask(ROLE_SYSTEM, ROLE_SCHEMA, "\n".join(lines))
    if not answer or PERSON.search(" ".join([answer["title"], answer["why"], *answer["can_do"]])):
        return None
    return {**answer, "can_do": answer["can_do"][:3], "skills": answer["skills"][:5], "signals": [], "roles": []}


def gather(name, domain, step):
    """Run the searches and return the distinct results, each with the text quotes are checked against."""
    seen, results, usd = set(), [], 0.0
    asked = searches(name, domain)
    for i, body in enumerate(asked):
        step("search", {"done": i, "of": len(asked), "pages": len(results), "query": body["query"]})
        resp = post("exa", EXA, body, lambda: {"x-api-key": os.environ["EXA_API_KEY"]})
        usd += (resp.get("costDollars") or {}).get("total", 0)
        for r in resp.get("results", []):
            text = lib.norm(r.get("text") or "")
            if r["url"] in seen or len(text) < 200:
                continue
            seen.add(r["url"])
            results.append({"url": r["url"], "title": r.get("title") or "",
                            "published": (r.get("publishedDate") or "")[:10], "text": text})
    return results, usd


def read(company, roles, results):
    """One model call over the search results. Returns (answer, usd) or (None, usd)."""
    lines = [f"Company: {company['name']}", f"Website: {company['website'] or 'unknown'}",
             f"Line of business: {company['industry'] or 'unknown'}",
             f"In its own words: {company['what_they_do'] or 'unknown'}",
             "Open tech roles on its own job feed: " + ("; ".join(roles) or company["no_roles"]), ""]
    for i, r in enumerate(results):
        lines += [f"[{i}] {r['title']}", f"URL: {r['url']}", f"Published: {r['published'] or 'unknown'}", r["text"], ""]
    return ask(SYSTEM, SCHEMA, "\n".join(lines))


def people(answer, company_name):
    """A second, single-purpose pass for names of people: the first call's own list misses some.

    Returns the full names and their surnames (a later mention is often the surname alone), leaving
    out the company's name and any word of it, which for a family firm is a surname too.
    """
    out = answer["outlook"]
    texts = [t for s in answer["signals"] for t in (s["claim"], s["quote"])] + [out["summary"]]
    texts += [t for n in out["talent_needs"] for t in (n["need"], n["why"])]
    found, usd = ask(NAMES_SYSTEM, NAMES_SCHEMA, "\n".join(f"{i}: {t}" for i, t in enumerate(texts)))
    full = {lib.norm(n) for x in (found or {"lines": []})["lines"] for n in x["names"]}
    full |= {p for s in answer["signals"] for p in s["people"]}
    full = {n for n in full if len(n) > 3 and n.lower() not in company_name.lower()}
    surnames = {n.split()[-1] for n in full if " " in n and len(n.split()[-1]) > 3}
    return (full | surnames) - set(company_name.split()), usd


NOTHING = re.compile(r"\b(no|not any|little|lack of) (reliable |public |clear )*(evidence|information|record)\b"
                     r"|\bsearch results\b|\bplaceholder page\b", re.I)


def check(answer, results, named):
    """Keep the signals whose quote is in the cited result and that say something about the company."""
    kept, dropped = [], 0
    for s in answer["signals"]:
        quote = lib.norm(s["quote"])
        ok = 0 <= s["source"] < len(results) and len(quote) >= 15 and quote in results[s["source"]]["text"]
        person = (s["people"] or any(p in quote or p in s["claim"] for p in named)
                  or PERSON.search(quote) or PERSON.search(s["claim"]))
        if (not ok or person or NOTHING.search(s["claim"])
                or lib.has_personal_data(quote) or lib.has_personal_data(s["claim"])):
            dropped += 1
            continue
        r = results[s["source"]]
        kept.append({"id": f"s{len(kept) + 1}", "type": s["type"], "claim": s["claim"], "date": s["date"],
                     "quote": quote, "source_url": r["url"], "source_title": r["title"], "published": r["published"]})
    return kept, dropped


def brief(key, companies, all_roles, step=lambda stage, facts: None):
    """The brief for a company id from companies.json, or for any company name or domain.

    step(stage, facts) is called as the work moves on, so a page can show it happening.
    """
    c = next((c for c in companies if c["id"] == key), None)
    if c:
        name, site = short_name(c["name"]["value"]), (c.get("website") or {}).get("value")
        domain = urllib.parse.urlsplit(site).hostname.removeprefix("www.") if site else None
    else:
        name, site, domain = key, None, key.lower() if re.fullmatch(r"[\w-]+(\.[\w-]+)+", key) else None
    found, searched = ([], 0) if c or domain else find(name)
    domain = domain or (found[0]["domain"] if found else None)
    ident, credits = identity(domain, name)
    ident, credits = ident or {}, credits + searched
    domain = domain or ident.get("domain")
    step("identity", {k: ident.get(k) for k in ("name", "domain", "logo", "logo_on", "colors", "slogan")})
    name = name if c or name != name.lower() else name.title()  # a typed name nothing recognised
    company = {"name": name if c or not ident.get("name") else ident["name"],
               "website": site or (f"https://{domain}" if domain else None),
               "industry": ((c.get("industry") or {}).get("value") or {}).get("label") if c
               else "; ".join(ident.get("industries") or []),
               "what_they_do": (c.get("what_they_do") or {}).get("value") if c else ident.get("description"),
               "no_roles": "none found" if c else "not checked, so say nothing about open roles"}
    posts = [r for r in all_roles if r["company_id"] == key]
    roles = [r["title"]["value"] for r in posts]
    results, exa_usd = gather(company["name"], domain, step)
    careers = ident.get("careers") or (c and (c.get("careers_url") or {}).get("value"))
    if careers and careers not in {r["url"] for r in results}:
        step("careers", {"url": careers, "pages": len(results)})
        page, used = careers_page(careers)
        credits += used
        results += [page] if page else []
    step("read", {"pages": len(results)})
    answer, llm_usd = read(company, roles, results)
    for half in (results[::2], results[1::2]):  # the model refuses when one page sets it off: try without it
        if answer is None:
            answer, usd = read(company, roles, half)
            results, llm_usd = half if answer else results, llm_usd + usd
    if answer is None:
        return None
    step("check", {"pages": len(results), "statements": len(answer["signals"])})
    named, names_usd = people(answer, company["name"])
    signals, dropped = check(answer, results, named)
    step("card", {"statements": len(signals)})
    needs, card_usd = card(company, posts, signals, named)
    return {"id": key if c else domain or key, "name": c["name"]["value"] if c else company["name"],
            "website": company["website"], "in_espoo_data": bool(c), "open_roles": len(roles),
            "identity": ident or None, "signals": signals, "card": needs, "generated_at": lib.now_iso(),
            "stats": {"results_read": len(results), "signals_dropped": dropped, "exa_usd": round(exa_usd, 4),
                      "llm_usd": round(llm_usd + names_usd + card_usd, 4), "context_credits": credits}}


def markdown(b):
    o = b["card"]
    i = b["identity"] or {}
    roles = f"open tech roles in our data: {b['open_roles']}" if b["in_espoo_data"] else "not in our Espoo job data"
    lines = [f"## {b['name']}", "", f"{b['website'] or ''} · {roles}", ""]
    if i:
        logo = f'<img src="{i["logo"]}" height="28"> ' if i["logo"] else ""
        facts = [i["slogan"], (i["industries"] or [None])[0], i["employees"] and f"{i['employees']} employees"]
        lines += [f"{logo}{' · '.join(f for f in facts if f)} (identity: Context.dev)", ""]
    lines += ["**Stated in public sources**", ""]
    for s in b["signals"]:
        lines.append(f"- `{s['id']}` [{s['type']}{', ' + s['date'] if s['date'] else ''}] {s['claim']}  \n"
                     f"  > \"{s['quote']}\" ([source]({s['source_url']}))")
    lines += ["", f"**Likely needs (inferred): {o['momentum']}**", "", o["pitch"], ""]
    for n in o["needs"]:
        cites = n["signals"] + [f"hiring now: {t}" for t in n["roles"]]
        lines.append(f"- **{n['title']}** ({n['seniority']}; {', '.join(n['skills'])}): {n['why']} ({', '.join(cites)})")
        lines += [f"  - can do: {x}" for x in n["can_do"]]
    return "\n".join(lines) + "\n"


def data():
    return (json.loads((lib.HERE / "companies.json").read_text()), json.loads((lib.HERE / "roles.json").read_text()))


def save(new):
    """Merge briefs into signals.json by id and rewrite signals.md."""
    briefs = {b["id"]: b for b in json.loads(OUT.read_text())} if OUT.exists() else {}
    briefs.update({b["id"]: b for b in new})
    out = sorted(briefs.values(), key=lambda b: b["name"].lower())
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
    (lib.HERE / "signals.md").write_text(
        "# Company signals\n\nWritten by `signals.py`. Quotes are verbatim from the linked source; "
        "the reading under each company is inference.\n\n" + "\n".join(markdown(b) for b in out))


def main(keys):
    companies, roles = data()
    done = []
    for key in keys:
        b = brief(key, companies, roles)
        if b is None:
            print(f"{key}: no answer", file=sys.stderr)
            continue
        done.append(b)
        s = b["stats"]
        print(f"{b['name']}: {len(b['signals'])} signals kept, {s['signals_dropped']} dropped, "
              f"{s['results_read']} results, ${s['exa_usd'] + s['llm_usd']:.3f}, "
              f"{s['context_credits']} context.dev credits", file=sys.stderr)
    save(done)


if __name__ == "__main__":
    main(sys.argv[1:])
