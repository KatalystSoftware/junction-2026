"""Discovery and extraction: seeds -> work/companies.raw.json, work/roles.raw.json, work/diag.json.

Per company: homepage -> careers links -> ATS feed (or JSON-LD / posting pages) -> tech roles in
Finland -> one small-model read per posting for the fields that need reading. Every field is
written as {value, quote, source_url, retrieved_at[, kind]}; validate.py decides what survives.

  python3 pipeline.py --limit 10
"""

import concurrent.futures as cf
import email.utils
import hashlib
import html
import json
import os
import re
import sys
from pathlib import Path
import urllib.parse

import ats
import lib
import llm

WORK = lib.HERE / "work"
MAX_CAREERS_PAGES = 7
MAX_POSTING_PAGES = 30
MAX_FEED_ROLES = 100

# never fetched: LinkedIn (terms), portals whose robots.txt or terms forbid it, social media
DENY = re.compile(r"(^|\.)(linkedin\.com|lnkd\.in|facebook\.com|instagram\.com|twitter\.com|x\.com|youtube\.com|"
                  r"youtu\.be|tiktok\.com|thehub\.io|duunitori\.fi|tyomarkkinatori\.fi|api\.smartrecruiters\.com|"
                  r"glassdoor\.[a-z.]+|indeed\.[a-z.]+|oikotie\.fi|monster\.fi|jobly\.fi|google\.com|apple\.com|"
                  r"github\.com|medium\.com|wikipedia\.org|vimeo\.com|spotify\.com)$", re.I)

TECH = re.compile(
    r"engineer|developer|software|\bdata\b|machine learning|\bml\b|\bai\b|artificial|cloud|devops|\bsre\b|"
    r"security|embedded|firmware|hardware|fpga|asic|\brf\b|\bqa\b|\btest|quality assurance|designer|\bux\b|\bui\b|"
    r"product manager|product owner|product lead|architect|\bit\b|sysadmin|system|scientist|programmer|"
    r"full.?stack|back.?end|front.?end|mobile|android|\bios\b|analyst|analytics|\bsap\b|\berp\b|\bcrm\b|salesforce|"
    r"network|infrastructure|platform|technical|tech lead|\bcto\b|scrum|project manager|program manager|"
    r"robotic|automation|electronic|quantum|algorithm|simulation|photonic|cyber|digital|web\b|coder|"
    r"kehittäjä|ohjelmisto|ohjelmoija|suunnittelija|arkkitehti|testaaja|testaus|tietoturva|insinööri|"
    r"järjestelmä|tekoäly|pilvi|sovellus|it-|tuotepäällikkö|projektipäällikkö|tuoteomistaja|konsultti|"
    r"analyytikko|elektroniikka|automaatio|verkko|devaaja|koodari|thesis|diplomityö|trainee|intern\b|"
    r"\bhpc\b|consultant|intune|r&d|technology|sysadmin|admin\b|ylläpit", re.I)
NOT_TECH = re.compile(
    r"\bsales\b|account executive|account manager|marketing|recruit|talent acquisition|\bhr\b|people partner|"
    r"finance|accountant|controller|legal|counsel|lawyer|customer success|office manager|assistant|"
    r"myyjä|myynti|markkinoin|talous|kirjanpit|siivo|varasto|warehouse|(?:truck|bus|taxi|delivery) driver|kuljettaja|hoitaja|nurse|"
    r"lääkäri|opettaja|teacher|cleaner|kokki|\bchef\b|asentaja|mechanic\b|welder|hitsaaja|business developer|"
    r"business development|communications|viestintä|procurement|purchas|osto|payroll|palkanlask", re.I)

ESPOO = re.compile(r"espoo|esbo|otaniemi|keilaniemi|leppävaara", re.I)
CAPITAL = re.compile(r"espoo|esbo|otaniemi|keilaniemi|leppävaara|helsinki|helsingfors|vantaa|vanda\b|kauniainen|"
                     r"grankulla|capital region|capital area|pääkaupunkiseu|uusimaa|helsinki metropolitan", re.I)
FINLAND = re.compile(r"finland|suomi\b|\bfi\b|tampere|oulu|turku|jyväskylä|kuopio|lahti|pori\b|vaasa|joensuu|"
                     r"lappeenranta|rovaniemi|hämeenlinna|salo\b|kotka|seinäjoki|" + CAPITAL.pattern, re.I)
REMOTE = re.compile(r"\bremote\b|etätyö|etänä|fully distributed|work from anywhere", re.I)
REGION_OK = re.compile(r"europe|\beu\b|emea|nordic|global|worldwide|anywhere", re.I)
# a remote role that names another country and not Finland is that country's role
ABROAD = re.compile(r"(?-i:\bUSA?\b|\bUK\b)|\b(germany|deutschland|romania|united states|united kingdom|sweden|norway|"
                    r"denmark|netherlands|poland|india|estonia|spain|france|portugal|italy|ireland|canada|switzerland|"
                    r"austria|belgium|china|japan|singapore|australia|ukraine|czech|hungary|lithuania|latvia|bulgaria|"
                    r"serbia|greece|turkey|brazil|mexico|israel)\b", re.I)

CAREERS = re.compile(
    r"career|\bjobs?\b|join[\s_-]?us|join our|join the team|rekry|(^|[/_\s-])(ura|urat|uralle|uramahdollisuudet)([/_\s-]|$)|"
    r"ty[oö]paikat|avoimet|t[oö]ihin|open[\s_-]?positions|open roles|work[\s_-]?(with|for|at)[\s_-]|vacanc|hiring|"
    r"positions|meille[\s_-]t|tule[\s_-]meille|ty[oö]nhaki", re.I)
OPENINGS = re.compile(r"open[\s_-]?(positions|roles|jobs)|\bjobs?\b|avoimet|vacanc|positions|ty[oö]paikat|rekry", re.I)
JOB_PATH = re.compile(r"/(jobs?|careers?|positions?|vacanc\w*|open-positions|open-roles|openings|rekry\w*|"
                      r"tyopaikat|avoimet-tyopaikat|ura|urat|o|p)/[^/?#]{4,}", re.I)
# hosted job boards that serve readable posting pages; value is the job system name
BOARDS = {"talentadore.com": "talentadore", "jobylon.com": "jobylon", "haileyhr.app": "hailey", "rekrytointi.com": "laura",
          "laura.fi": "laura", "sympahr.net": "sympa", "reachmee.com": "reachmee", "varbi.com": "varbi",
          "hibob.com": "hibob", "pinpointhq.com": "pinpoint", "breezy.hr": "breezy", "bamboohr.com": "bamboohr",
          "jobvite.com": "jobvite", "teamtailor.com": "teamtailor", "recruitee.com": "recruitee",
          "workable.com": "workable", "lever.co": "lever", "greenhouse.io": "greenhouse", "ashbyhq.com": "ashby",
          "personio.de": "personio", "personio.com": "personio", "intelliplan.eu": "intelliplan", "myworkdayjobs.com": "workday"}
JOB_SUBDOMAIN = re.compile(r"^(careers?|jobs?|rekry\w*|ura|join|apply|tyopaikat|recruit\w*)\.", re.I)
POSTING_PATH = re.compile(r"/(apply|jobs?|o|p|positions?|vacanc\w*|openings)/[^/?#]{6,}", re.I)
LANGUAGE = re.compile(r"english|finnish|englan|suome|suomi|language|kieli|kiele|swedish|ruotsi|german|deutsch|saksa|norwegian|danish", re.I)
WORKDAY = re.compile(r"//([\w-]+\.wd\d+\.myworkdayjobs\.com)", re.I)
# sitemap URLs look like /<site>/job/<place>/<Title-With-Dashes>_<requisition id>
WORKDAY_JOB = re.compile(r"/job/[^/]*(?:espoo|helsinki|vantaa|finland|suomi|remote)[^/]*/([^/_]+)", re.I)
JOBYLON_ID =re.compile(r"jbl_company_id\s*=\s*(\d+)")
JOBYLON_JOB = re.compile(r"https://emp\.jobylon\.com/jobs/\d+-([a-z0-9-]+)/")
_A = re.compile(r"<a\b([^>]*)>(.*?)</a>", re.S | re.I)
_HREF = re.compile(r"\bhref\s*=\s*(\"[^\"]*\"|'[^']*')", re.I)
_H1 = re.compile(r"<h1\b[^>]*>(.*?)</h1>", re.S | re.I)
_JOB_H1 = re.compile(r"<h1\b[^>]*class=\"[^\"]*job-title[^\"]*\"[^>]*>(.*?)</h1>", re.S | re.I)
WORKPLACE = re.compile(r"remote|hybrid|on-?\s?site|office|etä|lähityö|toimisto|paikan päällä|from home|distans", re.I)
ORACLE_TITLE = re.compile(r"research|standardi[sz]ation|\bhw\b|develop", re.I)
WP_VALUES = ("hybrid", "fully", "remote", "telecommute", "on-site", "onsite")
# Large Espoo employers whose careers page does not reveal a listing that a plain GET can read. Found by
# hand, robots.txt checked. Seed name -> (kind, listing URL or Oracle host, Oracle site, Oracle facet).
KNOWN = {
    "Nokia Oyj": ("oracle", "fa-evmr-saasfaprod1.fa.ocs.oraclecloud.com", "CX_1", ",selectedLocationsFacet=300000000471640"),
    "Orion Oyj": ("oracle", "fa-esaq-saasfaprod1.fa.ocs.oraclecloud.com", "OrionCareers", ""),
    "Tieto Finland Oy": ("smartrecruiters", "https://careers.smartrecruiters.com/Tieto2?search=Finland"),
    "Varjo Technologies Oyj": ("workable", "https://apply.workable.com/api/v1/widget/accounts/659213?details=true"),
    "Futurice Oy": ("teamtailor", "https://careers.futurice.com/jobs.rss"),
    "Innofactor Oyj": ("teamtailor", "https://ura.innofactor.fi/jobs.rss"),
    "Solteq Oyj": ("teamtailor", "https://career.solteq.com/jobs.rss"),
    "Bluefors Oy": ("teamtailor", "https://careers.bluefors.com/jobs.rss"),
    "Granlund Oy": ("teamtailor", "https://careers.granlund.fi/jobs.rss"),
    "Citycon Oyj": ("teamtailor", "https://careers.citycon.com/jobs.rss"),
    "Nightingale Health Oyj": ("teamtailor", "https://nightingalehealth.teamtailor.com/jobs.rss"),
    "Ramboll Finland Oy": ("smartrecruiters", "https://careers.smartrecruiters.com/Ramboll3?search=Finland"),
    "ICEYE Oy": ("ashby", "https://api.ashbyhq.com/posting-api/job-board/iceye"),
    "Etteplan Oyj": ("nextdata", "https://www.etteplan.com/careers/open-positions/apply-now/", "jobylon"),
    "Basware Oy": ("links", "https://cdn.jobylon.com/jobs/company-groups/195/embed/v2/?target=jobylon-jobs-widget&page_size=100",
                   r"url:\s*'(/jobs/[0-9]+-[a-z0-9-]+/)'", "jobylon", "https://emp.jobylon.com/"),
    "Sofigate Oy": ("links", "https://www.sofigate.com/wp-admin/admin-ajax.php?action=sg_open_position_feed&per_page=100&page=1&lang=en",
                    r'"link"\s*:\s*"([^"]+)"', "teamtailor"),
    "Rovio Entertainment Oy": ("links", "https://www.rovio.com/open-positions/",
                               r"(https://www\.rovio\.com/open-positions/[a-z0-9-]+-[0-9a-f]{8}-[0-9a-f-]{27}/)", None),
    "GuideVision Suomi Oy": ("links", "https://www.guidevision.eu/career", r'href="(/career/[^"]+)"', None),
    "Taito United Oy": ("links", "https://www.taitounited.fi/tyopaikat/", r'href="(/tyopaikat/[a-z0-9-]+/)"', None),
    "Qevo Oy": ("links", "https://qevo.fi/avoimet-paikat", r'href="(https://qevo\.fi/avoimet-paikat/[^"]+/)"', None),
    "TrueMed Oy": ("links", "https://truemedinc.com/careers/", r'class="tm-job-card" href="(https://truemedinc\.com/careers/[^"]+)"', None),
    "KYOCERA Technologies Oy": ("page", "https://kyoceratechnologies.com/work-with-us/open-positions/"),
    "Gofore Oyj": ("links", "https://gofore.com/en/careers/",
                   r"(https://gofore\.com/en/careers/(?!feed/|open-application/)[a-z0-9-]+/)", None),
    # (links, listing URL, pattern whose group 1 is a posting URL, job system or None)
    "Qt Group Oyj": ("links", "https://www.qt.io/careers/open-positions",
                     r'href="(/careers/open-positions/[^"]*gh_jid=\d+)[^"]*"', "greenhouse"),
    "Rejlers Finland Oy": ("links", "https://www.rejlers.com/fi/wp-json/wp/v2/rls_openposition?per_page=100",
                           r'"link"\s*:\s*"(https://www\.rejlers\.com/[^"]+)"', None),
    "Elisa Oyj": ("talentadore", "https://ats.talentadore.com/positions/bdXi6SM/json?v=2&language=fi,en,sv"
                                 "&display_description=job_title&categories=tags_and_extras"),
    "Espoon kaupunki": ("kuntarekry", "https://www.kuntarekry.fi/fi/tyopaikat/?organisation=3"
                                      "&lang=fi_FI%2Csv_SE%2Cen_US&sort=-changetime&limit=100"),
}
_META = re.compile(r"<meta\b[^>]*>", re.I)
_SUFFIX = re.compile(r"\s+(oyj|oy|ab|abp|ltd|inc|plc|group|finland|holding|enterprises|entertainment|solutions|"
                     r"technologies|technology|software|services|international|corporation|oy ab)\.?$", re.I)


def get(url, accept=None):
    host = urllib.parse.urlsplit(url).netloc.lower().split(":")[0]
    if not host or DENY.search(host):
        return {"url": url, "status": -2, "error": "denylist"}, b""
    try:
        return lib.fetch(url, accept)
    except Exception as e:  # a broken URL must not stop the batch
        return {"url": url, "status": 0, "error": type(e).__name__}, b""


def page(url):
    """Fetch an HTML page. Returns (source_url, retrieved_at, doc) or None. source_url is the
    final URL after redirects, which the cache also holds under its own key."""
    meta, body = get(url)
    if not lib.ok(meta) or not body:
        return None
    ct = (meta.get("content_type") or "").lower()
    if ct and not any(x in ct for x in ("html", "xml", "text")):
        return None
    src = meta.get("final_url") or url
    if lib.cached(src) is None:
        src = url
    return src, meta["retrieved_at"], lib.decode(body, meta.get("content_type", ""))


def links(src, doc):
    """(absolute url, href as written, anchor text) for every <a> in a page."""
    out = []
    for m in _A.finditer(lib._DROP.sub(" ", doc)):
        h = _HREF.search(m.group(1))
        if not h:
            continue
        href = html.unescape(h.group(1)[1:-1]).strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        try:
            url = urllib.parse.urldefrag(urllib.parse.urljoin(src, href))[0]
        except ValueError:
            continue
        if url.startswith("http"):
            out.append((url, href, ats.plain(m.group(2))[:200]))
    return out


def board(url):
    """Job system name if the URL is on a hosted job board, else None."""
    host = urllib.parse.urlsplit(url).netloc.lower().split(":")[0]
    return next((v for k, v in BOARDS.items() if host == k or host.endswith("." + k)), None)


def field(value, quote, src, at, kind=None, **extra):
    f = {"value": value, "quote": quote, "source_url": src, "retrieved_at": at}
    if quote is None:
        del f["quote"]
    if kind:
        f["kind"] = kind
    f.update(extra)
    return f


ABSENT = {"value": "not_stated", "kind": "absent"}


def short_name(name):
    s = name or ""
    for _ in range(3):
        s = _SUFFIX.sub("", s).strip()
    return s


def iso_date(s):
    if not s:
        return None
    m = re.match(r"\d{4}-\d{2}-\d{2}", s)
    if m:
        return m.group()
    try:
        return email.utils.parsedate_to_datetime(s).date().isoformat()
    except Exception:
        return None


def is_tech_title(t):
    return bool(t and TECH.search(t) and not NOT_TECH.search(t))


def in_scope(loc_text, finnish_company):
    """Finland, or remote with a region that includes Finland."""
    if FINLAND.search(loc_text):
        return True
    if REMOTE.search(loc_text):
        return bool(REGION_OK.search(loc_text)) or (finnish_company and len(loc_text) < 30)
    return False


# --- company ------------------------------------------------------------------------------------

def discover(seed):
    """Network phase for one company. Returns {company, candidates, diag}."""
    bid = seed.get("business_id")
    name = seed.get("name") or seed.get("name_hint")
    dom = seed["website"]
    cid = bid or lib.norm(dom).lower()
    c = {"id": cid, "seed_list": seed["seed_list"]}
    d = {"id": cid, "name": name, "site": False, "careers": False, "ats": None, "feed": False,
         "source": None, "candidates": 0}
    if bid:
        src, at = seed["prh_url"], seed["prh_retrieved_at"]
        c["name"] = field(name, None, src, at, "registry")
        c["business_id"] = field(bid, None, src, at, "registry")
        if seed.get("municipality") and seed["municipality"].get("city"):
            c["municipality"] = field(seed["municipality"]["city"], None, src, at, "registry")
            c["espoo_registered"] = {"value": bool(seed.get("espoo_registered")), "kind": "derived",
                                     "derived_from": "municipality"}
        if seed.get("industry"):
            ind = seed["industry"]
            c["industry"] = field({"code": ind["code"], "label": ind["label"]}, None, src, at, "registry")
        if seed.get("website_registered"):
            c["website_registered"] = field(seed["website_registered"], None, src, at, "registry")

    start = dom if dom.startswith("http") else "https://" + dom.strip("/")
    home = page(start)
    if home is None:
        host = urllib.parse.urlsplit(start).netloc
        if not host.startswith("www."):
            start = start.replace("://", "://www.", 1)
            home = page(start)
    out = {"company": c, "candidates": [], "diag": d, "seed": seed}
    known = KNOWN.get(name)
    if known and known[0] == "oracle":
        out["candidates"] = oracle_known(known[1], known[2], known[3], d, c)
    from_listing = home is None and bool(known) and known[0] == "links"
    if from_listing:  # own site unreachable: start from the known job listing
        home = page(known[1])
    if home is None:
        d["candidates"] = len(out["candidates"])
        return out
    hsrc, hat, hdoc = home
    d["site"] = True
    if from_listing:
        d["site"] = False
    else:
        c["website"] = field(hsrc, None, hsrc, hat, "fetched")
    htext = lib.html_text(hdoc)
    sn = short_name(name)
    m = re.search(re.escape(sn), htext, re.I) if sn and len(sn) >= 3 else None
    if m:
        # the company's name as written on its own site ties the domain to the company
        c["name_on_site"] = field(m.group(), m.group(), hsrc, hat)
        if not bid:
            c["name"] = field(m.group(), m.group(), hsrc, hat)
    for tag in _META.findall(hdoc):
        if re.search(r"(name|property)\s*=\s*[\"'](description|og:description)[\"']", tag, re.I):
            cm = re.search(r"\bcontent\s*=\s*(\"[^\"]*\"|'[^']*')", tag, re.I)
            desc = lib.norm(html.unescape(cm.group(1)[1:-1])) if cm else ""
            if len(desc) >= 40 and not re.search(r"cookie|evästei|404|not found", desc, re.I):
                first = re.split(r"(?<=[.!?])\s+(?=[A-ZÅÄÖ])", desc)[0]
                first = first if len(first) >= 40 else desc
                if not lib.has_personal_data(first):
                    c["what_they_do"] = field(first[:400], first[:400], hsrc, hat)
                    break

    # careers pages: links on the homepage, then "open positions" style links one level down
    pages = [(hsrc, hat, hdoc)]
    seen = {hsrc, start}
    cands = [l for l in links(hsrc, hdoc) if CAREERS.search(urllib.parse.urlsplit(l[0]).path + " " + l[2])
             or JOB_SUBDOMAIN.match(urllib.parse.urlsplit(l[0]).netloc)]
    cands = [l for l in cands if not (board(l[0]) and POSTING_PATH.search(urllib.parse.urlsplit(l[0]).path))]
    cands.sort(key=lambda l: (0 if OPENINGS.search(l[0] + " " + l[2]) else 1, len(l[0])))
    queue = [(l, hsrc, hat, 1) for l in cands[:4]]
    level2 = 0
    while queue and len(pages) <= MAX_CAREERS_PAGES:
        (url, href, text), psrc, pat, depth = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        got = page(url)
        if got is None:
            continue
        seen.add(got[0])
        pages.append(got)
        if "careers_url" not in c:
            c["careers_url"] = field(url, href, psrc, pat, "url")
            d["careers"] = True
        if depth == 1 and level2 < 3:
            # one level down: the company's job board on another host (careers.x.com, a hosted
            # board), then "open positions" style pages on the same site
            ghost = urllib.parse.urlsplit(got[0]).netloc
            ext, own = [], []
            for l in links(got[0], got[2]):
                u = urllib.parse.urlsplit(l[0])
                if l[0] in seen or DENY.search(u.netloc.split(":")[0]):
                    continue
                listing = OPENINGS.search(u.path.rstrip("/").rsplit("/", 1)[-1])
                if u.netloc != ghost and (JOB_SUBDOMAIN.match(u.netloc) or board(l[0])):
                    if listing or not POSTING_PATH.search(u.path):
                        ext.append(l)
                elif OPENINGS.search(u.path + " " + l[2]) and (listing or not JOB_PATH.search(u.path.rstrip("/") + "/")):
                    own.append(l)
            ext.sort(key=lambda l: len(l[0]))
            own.sort(key=lambda l: len(l[0]))
            more = (ext[:1] + own[:2])[:3 - level2]
            level2 += len(more)
            queue = [(l, got[0], got[1], 2) for l in more] + queue

    # ATS: any reference on the pages we hold
    feeds = []
    for psrc, pat, pdoc in pages:
        for f in ats.detect(psrc, pdoc):
            if d["ats"] is None or (f["feed_url"] and not feeds):
                d["ats"] = f["type"]
                c["ats_type"] = field(f["type"], f["quote"], psrc, pat)
            if f["feed_url"] and f["feed_url"] not in [x[1] for x in feeds]:
                feeds.append((f["type"], f["feed_url"], psrc, pat, f["quote"]))
    if known and known[0] in ("workable", "teamtailor", "ashby") and known[1] not in [x[1] for x in feeds]:
        feeds.insert(0, (known[0], known[1], None, None, None))
    fin = bool(bid)
    for typ, furl, psrc, pat, quote in feeds[:4]:
        meta, body = get(furl)
        if not lib.ok(meta):
            continue
        items = ats.PARSERS[typ](meta, body)
        if not items and (typ != "teamtailor" or b"<rss" not in body[:600].lower()):
            continue
        d["ats"], d["feed"], d["source"] = typ, True, "ats_feed"
        d["careers"] = True
        if quote:
            c["ats_type"] = field(typ, quote, psrc, pat)
        c["ats_feed_url"] = field(furl, None, furl, meta["retrieved_at"], "fetched")
        d["feed_jobs"] = len(items)
        n = 0
        for it in items:
            loc_text = " | ".join(x for x in [it.get("location"), it.get("location2"), *(it.get("locations") or []),
                                              it.get("remote") if isinstance(it.get("remote"), str) else None] if x)
            if not it.get("title") or not it.get("url") or not in_scope(loc_text, fin):
                continue
            d["feed_jobs_finland"] = d.get("feed_jobs_finland", 0) + 1
            if not is_tech_title(it["title"]) or n >= MAX_FEED_ROLES:
                d.setdefault("feed_titles_skipped", []).append(it["title"][:80])
                continue
            n += 1
            out["candidates"].append({"kind": "feed", "ats": typ, "feed_url": furl, "at": meta["retrieved_at"], "it": it})
        break
    if out["candidates"] or d["feed"]:
        d["candidates"] = len(out["candidates"])
        return out

    # no parseable feed: JSON-LD on the careers pages, then posting pages linked from them
    posting_urls = []
    # links that are also on the homepage are site navigation, not postings
    nav = {l[0] for l in links(hsrc, hdoc)}
    for psrc, pat, pdoc in pages[1:] or []:
        for jp in ats.job_postings(pdoc):
            out["candidates"].append({"kind": "ld", "src": psrc, "at": pat, "ld": jp, "doc": None})
        phost = urllib.parse.urlsplit(psrc).netloc
        for url, href, text in links(psrc, pdoc):
            u = urllib.parse.urlsplit(url)
            hosted = board(url) and POSTING_PATH.search(u.path)
            if url in seen or url in posting_urls or (url in nav and not hosted) or DENY.search(u.netloc.split(":")[0]):
                continue
            if re.search(r"\.(pdf|png|jpe?g|docx?|zip)$", u.path, re.I):
                continue
            same = u.netloc == phost or u.netloc.split(".")[-2:] == phost.split(".")[-2:]
            job_path = JOB_PATH.search(u.path.rstrip("/") + "/") and len(u.path) > len(urllib.parse.urlsplit(psrc).path) + 3
            if (5 <= len(text) <= 140 and is_tech_title(text) and (same or job_path or hosted)) or (job_path and not same and CAREERS.search(u.netloc)):
                posting_urls.append(url)
            elif hosted and is_tech_title(re.sub(r"[-_/]+", " ", u.path)):
                # hosted boards put the title in the path; the link text is often just "apply"
                posting_urls.append(url)
    # postings listed by a job system come before links guessed from the careers pages
    ats_urls = []
    # Jobylon widget: the embed script lists the postings
    for psrc, pat, pdoc in pages:
        m = JOBYLON_ID.search(pdoc)
        if m:
            meta, body = get(f"https://cdn.jobylon.com/jobs/companies/{m.group(1)}/embed/v1/?target=jobylon-jobs-widget&page_size=100")
            if lib.ok(meta):
                d["ats"] = "jobylon"
                for jm in JOBYLON_JOB.finditer(body.decode("utf-8", "replace")):
                    if jm.group() not in ats_urls and is_tech_title(jm.group(1).replace("-", " ")):
                        ats_urls.append(jm.group())
            break
    # Workday: the tenant's robots.txt names a sitemap of posting pages, each with JSON-LD
    for psrc, pat, pdoc in pages:
        m = WORKDAY.search(pdoc) or WORKDAY.search(psrc or "")
        if m:
            meta, body = get(f"https://{m.group(1).lower()}/robots.txt")
            for sm in re.findall(r"(?im)^sitemap:\s*(\S+)", body.decode("utf-8", "replace"))[:4] if lib.ok(meta) else []:
                meta, body = get(sm)
                for url in re.findall(r"<loc>\s*([^<\s]+)", body.decode("utf-8", "replace")) if lib.ok(meta) else []:
                    jm = WORKDAY_JOB.search(url)
                    if jm and url not in ats_urls and is_tech_title(re.sub(r"[-_]+", " ", jm.group(1))):
                        ats_urls.append(url)
            break
    # listings of large employers that the careers page does not reveal (KNOWN)
    if known and known[0] == "smartrecruiters":
        base, q = known[1].split("?")
        for lurl in [known[1]] + [f"{base}/api/more?{q}&page={n}" for n in (1, 2, 3)]:
            meta, body = get(lurl)
            if lib.ok(meta):
                d["ats"], d["careers"] = "smartrecruiters", True
                for jm in re.finditer(r"https://jobs\.smartrecruiters\.com/[\w-]+/\d+-([a-z0-9-]+)", body.decode("utf-8", "replace")):
                    if jm.group() not in ats_urls and is_tech_title(jm.group(1).replace("-", " ")):
                        ats_urls.append(jm.group())
    if known and known[0] == "links":
        meta, body = get(known[1])
        if lib.ok(meta):
            d["careers"], d["ats"] = True, known[3] or d["ats"]
            for jm in re.finditer(known[2], body.decode("utf-8", "replace").replace("\\/", "/")):
                url = urllib.parse.urljoin(known[4] if len(known) > 4 else known[1], html.unescape(jm.group(1)))
                if url not in ats_urls:
                    ats_urls.append(url)
    if known and known[0] == "page":  # the careers page carries its one posting itself
        d["careers"] = True
        ats_urls.append(known[1])
    if known and known[0] == "nextdata":  # Etteplan: the listing is JSON inside the page, each position with its country
        meta, body = get(known[1])
        m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', body.decode("utf-8", "replace"), re.S) if lib.ok(meta) else None
        try:
            positions = json.loads(m.group(1))["props"]["pageProps"]["post"]["siteContent"]["en"]["openPositions"] if m else []
        except (KeyError, TypeError, ValueError):
            positions = []
        if positions:
            d["careers"], d["ats"] = True, known[2]
        for pos in positions:
            url = (pos.get("openPositionMeta") or {}).get("advertisementUrl")
            places = ((pos.get("openPositionLocations") or {}).get("nodes") or [])
            if url and url not in ats_urls and any(((n.get("parent") or {}).get("node") or {}).get("slug") == "finland" for n in places):
                ats_urls.append(url)
    ta = [known[1]] if known and known[0] == "talentadore" else []
    for psrc, pat, pdoc in pages:  # TalentAdore's embed: the page names the positions list, which also comes as JSON
        for m in re.finditer(r"ats\.talentadore\.com/positions/(\w+)/", pdoc):
            u = f"https://ats.talentadore.com/positions/{m.group(1)}/json?v=2"
            if not ta or (not known and u not in ta and len(ta) < 2):
                ta.append(u)
    for lurl in ta:
        meta, body = get(lurl)
        for j in (ats._json(body) or {}).get("jobs") or [] if lib.ok(meta) else []:
            d["ats"], d["careers"] = "talentadore", True
            if ats._s(j.get("link")) and j["link"] not in ats_urls and is_tech_title(j.get("name") or ""):
                ats_urls.append(j["link"])
    if known and known[0] == "kuntarekry":
        meta, body = get(known[1])
        for jm in re.finditer(r"<basic-job-card\b[^>]*>", body.decode("utf-8", "replace")) if lib.ok(meta) else []:
            d["careers"] = True
            u, t = re.search(r'\burl="([^"]+)"', jm.group()), re.search(r'\btitle="([^"]+)"', jm.group())
            if u and t and is_tech_title(html.unescape(t.group(1))):
                url = urllib.parse.urljoin(known[1], html.unescape(u.group(1)))
                if url not in ats_urls:
                    ats_urls.append(url)
    posting_urls = ats_urls[:MAX_FEED_ROLES] + [u for u in posting_urls if u not in ats_urls][:MAX_POSTING_PAGES]
    for url in posting_urls:
        got = page(url)
        if got is None:
            continue
        psrc, pat, pdoc = got
        lds = ats.job_postings(pdoc)
        if lds:
            out["candidates"].append({"kind": "ld", "src": psrc, "at": pat, "ld": lds[0], "doc": pdoc})
            continue
        h1 = _JOB_H1.search(pdoc) or _H1.search(pdoc)
        title = ats.plain(h1.group(1)) if h1 else None
        if known and known[0] in ("links", "page") and url in ats_urls and not (title and is_tech_title(title)):
            # a hand-checked listing: the job title may sit in a later heading than the first h1
            heads = [ats.plain(m.group(1)) for m in re.finditer(r"<h[12]\b[^>]*>(.*?)</h[12]>", pdoc, re.S | re.I)]
            title = next((t for t in heads if 4 <= len(t) <= 140 and is_tech_title(t)), title)
        if title and 4 <= len(title) <= 140 and is_tech_title(title):
            out["candidates"].append({"kind": "page", "src": psrc, "at": pat, "title": title, "doc": pdoc})
    if out["candidates"]:
        d["source"] = "json_ld" if any(x["kind"] == "ld" for x in out["candidates"]) else "careers_page"
    d["candidates"] = len(out["candidates"])
    return out


# --- roles --------------------------------------------------------------------------------------

def _working_time(v):  # feeds spell it FullTime, FULL_TIME, full-time: one spelling, or nothing
    low = (v or "").lower()
    return "full_time" if "full" in low else "part_time" if "part" in low else None


def _ld_str(v):
    if isinstance(v, list):
        v = v[0] if v else None
    return v.strip() if isinstance(v, str) and v.strip() else None


def _ld_locations(jp):
    out = []
    locs = jp.get("jobLocation")
    for loc in locs if isinstance(locs, list) else [locs]:
        if not isinstance(loc, dict):
            continue
        a = loc.get("address")
        if isinstance(a, dict):
            for k in ("addressLocality", "addressRegion", "addressCountry"):
                v = a.get(k)
                v = v.get("name") if isinstance(v, dict) else v
                if _ld_str(v):
                    out.append(_ld_str(v))
        elif _ld_str(a):
            out.append(_ld_str(a))
        elif _ld_str(loc.get("name")):
            out.append(_ld_str(loc.get("name")))
    return out


def prepare(cand, company_name):
    """Code-extracted fields of one candidate, plus the text the model reads."""
    k = cand["kind"]
    r = {"source": {"feed": "ats_feed", "ld": "json_ld", "page": "careers_page"}[k]}
    at = cand["at"]
    msrc = mat = None  # where the model's text came from, when it is not the feed or page itself
    if k == "feed":
        it, src = cand["it"], cand["feed_url"]
        r["ats"] = cand["ats"]
        r["item"] = {"url": src, "parser": cand["ats"], "key": it["key"]}
        r["title"] = field(it["title"], it["title"], src, at)
        if it.get("url_built"):
            got = page(it["url"])
            if got:
                r["url"] = field(got[0], None, got[0], got[1], "fetched")
        else:
            r["url"] = field(it["url"], it["url"], src, at, "url")
        locs = it.get("locations") or [x for x in [it.get("location"), it.get("location2")] if x]
        parts = it.get("location_parts") or locs
        if locs:
            q = next((p for p in parts if FINLAND.search(p)), parts[0])
            r["location"] = field("; ".join(dict.fromkeys(locs)), q, src, at)
        if isinstance(it.get("remote"), str) and it["remote"].strip():
            r["workplace"] = field(it["remote"].strip().lower(), it["remote"], src, at)
        if iso_date(it.get("posted")):
            r["posted"] = field(iso_date(it["posted"]), it["posted"], src, at)
        if _working_time(it.get("employment")):
            r["working_time"] = field(_working_time(it["employment"]), it["employment"], src, at)
        body, url = it["body"], it["url"]
        if len(body) < 200 and it.get("url_built") and got:
            # some Personio feeds carry no description: read the posting page and cite that instead
            body, msrc, mat = lib.norm(lib.strip_tags(got[2])), got[0], got[1]
    else:
        src = cand["src"]
        if board(src):
            r["ats"] = board(src)
        r["url"] = field(src, None, src, at, "fetched")
        url = src
        if k == "ld":
            jp = cand["ld"]
            title = _ld_str(jp.get("title")) or _ld_str(jp.get("name"))
            if title:
                r["title"] = field(ats.plain(title), title, src, at)
            locs = _ld_locations(jp)
            if locs:
                q = next((p for p in locs if FINLAND.search(p)), locs[0])
                r["location"] = field(", ".join(dict.fromkeys(locs)), q, src, at)
            if _ld_str(jp.get("jobLocationType")):
                r["workplace"] = field(_ld_str(jp["jobLocationType"]).lower(), _ld_str(jp["jobLocationType"]), src, at)
            if iso_date(_ld_str(jp.get("datePosted"))):
                r["posted"] = field(iso_date(_ld_str(jp["datePosted"])), _ld_str(jp["datePosted"]), src, at)
            if iso_date(_ld_str(jp.get("validThrough"))):
                r["deadline"] = field(iso_date(_ld_str(jp["validThrough"])), _ld_str(jp["validThrough"]), src, at)
            if _working_time(_ld_str(jp.get("employmentType"))):
                r["working_time"] = field(_working_time(_ld_str(jp["employmentType"])), _ld_str(jp["employmentType"]), src, at)
            body = ats.plain(jp.get("description") if isinstance(jp.get("description"), str) else "")
            if len(body) < 200 and cand.get("doc"):
                body = lib.norm(lib.strip_tags(cand["doc"]))
        else:
            r["title"] = field(cand["title"], cand["title"], src, at)
            body = lib.norm(lib.strip_tags(cand["doc"]))
            m = re.search(r'<spl-job-location[^>]*\bformattedAddress="([^"]+)"', cand["doc"])
            if m and lib.norm(html.unescape(m.group(1))) in (lib.source_text(src) or ""):
                # SmartRecruiters posting pages carry the place in an attribute; kept when the page text repeats it
                place = lib.norm(html.unescape(m.group(1)))
                r["location"], r["_page_place"] = field(place, place, src, at), True
            i = body.find(lib.norm(cand["title"]))
            body = body[max(i, 0):]
    title = r.get("title", {}).get("value")
    r["_body"], r["_src"], r["_at"], r["_url"] = body, msrc or src, mat or at, url
    r["_read"] = bool(title and len(body) >= 200)
    return r


VENDOR_LABELS = ("ashbyhq", "teamtailor", "oraclecloud", "smartrecruiters", "talentadore", "greenhouse", "jobylon", "recruitee",
                 "personio", "myworkdayjobs", "lever", "workable", "breezy", "reachmee", "pinpointhq", "successfactors", "laura")


def _label(u):  # 'https://careers.frends.com/jobs/1' -> 'frends'
    parts = (urllib.parse.urlsplit(u).hostname or "").split(".")
    return parts[-2] if len(parts) > 1 else ""


def someone_elses(c, url):
    """A posting on another company's own domain (a recruiter's job board) is not this company's job."""
    site = (c.get("website") or {}).get("value")
    name = (c.get("name") or {}).get("value")
    return bool(site) and name not in KNOWN and _label(url) not in (_label(site), *VENDOR_LABELS)


def finish(r, ans, cid, finnish_company, espoo_registered):
    """Merge the model's reading into a role record; a short reason string if the role is out of scope."""
    src, at, k = r.pop("_src"), r.pop("_at"), r["source"]
    body, url = r.pop("_body"), r.pop("_url")
    r.pop("_read")
    if "title" not in r or "url" not in r:
        return "no title or url"
    r["title"]["value"] = re.sub(r"\s+", " ", r["title"]["value"].replace("\xad", "")).strip()
    if r.get("workplace", {}).get("value") not in WP_VALUES:
        r.pop("workplace", None)  # a header tag such as 'none' says nothing; the model's reading is used instead
        a = (ans or {}).get("workplace") or {}
        if a.get("value") in ("remote", "hybrid", "onsite") and WORKPLACE.search(a.get("quote") or ""):
            r["workplace"] = field(a["value"], a["quote"], src, at)
    if ans:
        if k != "ats_feed" and not ans.get("is_job_posting"):
            return "model: not a job posting"
        if not ans.get("is_tech_role"):
            return "model: not a tech role"
    elif k == "careers_page":
        return "unread plain page"  # nothing confirms that a plain page is one job posting
    if not ans and not is_tech_title(r["title"]["value"]):
        return "title not tech"  # the title filter only stands in when the model has not read the posting
    page_place = r.pop("_page_place", False)
    if ans:
        said = f"{ans['location']['value']} | {ans['location']['quote']}"
        # the page's one place gives way when the posting text itself lists the capital region
        if page_place and CAPITAL.search(said) and not CAPITAL.search(r["location"]["value"]):
            del r["location"]
        have = r.get("location", {}).get("value", "").split(",")[0].strip().lower()
        # the job system names one office; the posting text lists that office and others
        if have and have in ans["location"]["value"].lower() and len(re.split(r"[,;/]| or | tai ", ans["location"]["value"])) > \
                len(re.split(r"[,;/]", r["location"]["value"])) and ans["location"]["quote"].strip():
            del r["location"]
        if "location" not in r and ans["location"]["value"].strip() and ans["location"]["quote"].strip():
            r["location"] = field(ans["location"]["value"].strip(), ans["location"]["quote"], src, at)
        wt = ans["working_time"]
        if "working_time" not in r and wt["value"] != "not_stated" and wt["quote"].strip():
            r["working_time"] = field(wt["value"], wt["quote"], src, at)
        for name in ("language_requirement", "seniority", "employment_type"):
            a = ans[name]
            if name == "language_requirement" and not LANGUAGE.search(a["quote"]):
                a = {"value": "not_stated", "quote": ""}  # the quote must itself be about language
            r[name] = field(a["value"], a["quote"], src, at) if a["value"] != "not_stated" and a["quote"].strip() else dict(ABSENT)
        dl = ans["deadline"]
        if "deadline" not in r and re.fullmatch(r"\d{4}-\d{2}-\d{2}", dl["value"].strip()) and dl["quote"].strip():
            r["deadline"] = field(dl["value"].strip(), dl["quote"], src, at)
        for name in ("must_have", "nice_to_have"):
            items = []
            for x in ans[name][:8]:
                if x["skill"].strip() and x["quote"].strip():
                    f = field(x["skill"].strip(), x["quote"], src, at)
                    if x["skill_id"] in llm.SKILL_IDS:
                        f["skill_id"] = x["skill_id"]
                    items.append(f)
            if items:
                r[name] = items
        if ans["role_family"] != "other":
            r["role_family"] = {"value": ans["role_family"], "kind": "derived", "derived_from": "title", "method": "model reading of the posting"}
    loc = r.get("location")
    if "workplace" in r:  # one spelling per mode; the quote keeps the job system's own word
        r["workplace"]["value"] = {"fully": "remote", "telecommute": "remote", "on-site": "onsite"}.get(r["workplace"]["value"], r["workplace"]["value"])
    wp = r.get("workplace", {}).get("value", "")
    if loc:
        text = f"{loc['value']} | {loc['quote']}"
        remote = bool(REMOTE.search(text) or wp in ("remote", "fully", "telecommute"))
        if not (FINLAND.search(text) or (remote and (REGION_OK.search(text) or finnish_company))):
            return "location outside Finland"
        if ABROAD.search(text) and not FINLAND.search(text):
            return "location outside Finland"
        capital = bool(CAPITAL.search(text))
        if not (capital or remote):
            return "elsewhere in Finland"  # out of scope for an Espoo event
        r["is_espoo"] = {"value": bool(ESPOO.search(text)), "kind": "derived", "derived_from": "location"}
        r["is_capital_region"] = {"value": capital, "kind": "derived", "derived_from": "location"}
        r["is_remote"] = {"value": remote, "kind": "derived", "derived_from": "workplace" if wp and not REMOTE.search(text) else "location"}
    elif not espoo_registered:
        return "no location, company not in Espoo"
    fi = len(re.findall(r"\b(ja|on|sekä|meillä|olet|tai|että|työ\w*|haemme|sinulla)\b", body[:3000], re.I))
    en = len(re.findall(r"\b(and|the|you|with|our|for|are|will|team|experience)\b", body[:3000], re.I))
    if fi + en >= 20:
        r["posting_language"] = {"value": "fi" if fi > en else "en", "kind": "derived", "derived_from": "url", "method": "stop-word count over the posting text"}
    r["id"] = f"{cid}:{hashlib.sha1(url.encode()).hexdigest()[:10]}"
    r["company_id"] = cid
    return r


def oracle_known(host, site, facet, d, c):
    """Candidates from Oracle Recruiting's public resource: the list, then one detail call for each
    tech-looking job with a place in Finland."""
    base = f"https://{host}/hcmRestApi/resources/latest/recruitingCEJobRequisition"
    cands, seen = [], set()
    for off in ("", ",offset=25", ",offset=50", ",offset=75"):
        lurl = (f"{base}s?onlyData=true&expand=requisitionList.secondaryLocations&finder=findReqs;"
                f"siteNumber={site}{facet},limit=25{off},sortBy=POSTING_DATES_DESC")
        meta, body = get(lurl)
        top = ((ats._json(body) or {}).get("items") or [{}])[0] if lib.ok(meta) else {}
        rl = top.get("requisitionList") or []
        if not off and rl:
            d["ats"], d["feed"], d["source"], d["careers"] = "oracle", True, "ats_feed", True
            c["ats_feed_url"] = field(lurl, None, lurl, meta["retrieved_at"], "fetched")
        d["feed_jobs"] = d.get("feed_jobs", 0) + len(rl)
        for j in rl:
            fi = j.get("PrimaryLocationCountry") == "FI" or any(s.get("CountryCode") == "FI" for s in j.get("secondaryLocations") or [])
            if not fi or not j.get("Id") or j["Id"] in seen:
                continue
            seen.add(j["Id"])
            d["feed_jobs_finland"] = d.get("feed_jobs_finland", 0) + 1
            # the list is short, so a wider net than is_tech_title; the model decides what is a tech role
            if not (TECH.search(j.get("Title") or "") or ORACLE_TITLE.search(j.get("Title") or "")) or len(cands) >= MAX_FEED_ROLES:
                d.setdefault("feed_titles_skipped", []).append((j.get("Title") or "")[:80])
                continue
            durl = f"{base}Details?expand=all&onlyData=true&finder=ById;Id=%22{j['Id']}%22,siteNumber={site}"
            dm, db = get(durl)
            for it in ats.parse_oracle(dm, db) if lib.ok(dm) else []:
                cands.append({"kind": "feed", "ats": "oracle", "feed_url": durl, "at": dm["retrieved_at"], "it": it})
        if len(rl) < 25:
            break
    return cands


def safe_discover(seed):
    try:
        return discover(seed)
    except Exception as e:  # one broken site must not stop the batch
        cid = seed.get("business_id") or lib.norm(seed["website"]).lower()
        return {"company": {"id": cid, "seed_list": seed["seed_list"]}, "candidates": [], "seed": seed,
                "diag": {"id": cid, "name": seed.get("name") or seed.get("name_hint"), "site": False, "careers": False,
                         "ats": None, "feed": False, "source": None, "candidates": 0, "error": f"discover: {type(e).__name__}"}}


def main():
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
    seeds = [s for s in json.loads((WORK / "seeds.json").read_text()) if s.get("business_id") or "curated" in s["seed_list"]]
    seeds = [s for s in seeds if s.get("website") and (s.get("name") or s.get("name_hint"))][:limit]
    with cf.ThreadPoolExecutor(24) as ex:
        found = list(ex.map(safe_discover, seeds))
    print(f"discovered {len(found)} companies, fetch stats {lib.stats}", flush=True)

    jobs = []
    for f in found:
        name = f["diag"]["name"]
        for cand in f["candidates"]:
            try:
                jobs.append((f, prepare(cand, name)))
            except Exception as e:
                f["diag"]["error"] = f"prepare: {type(e).__name__}"

    def read(job):
        f, r = job
        return llm.read_posting(f["diag"]["name"], r["title"]["value"], r["_body"]) if r["_read"] else None

    with cf.ThreadPoolExecutor(8) as ex:
        answers = list(ex.map(read, jobs))
    print(f"read {sum(a is not None for a in answers)}/{len(jobs)} postings, spend {llm.spend()}", flush=True)

    roles, by_company = [], {}
    for (f, r), ans in zip(jobs, answers):
        c = f["company"]
        fin = "business_id" in c
        role = finish(r, ans, c["id"], fin, bool(c.get("espoo_registered", {}).get("value")))
        if not isinstance(role, str) and someone_elses(c, role["url"]["value"]):
            role = "posted on another company's job board"
        f["diag"]["read"] = f["diag"].get("read", 0) + (ans is not None)
        if isinstance(role, str):
            drops = f["diag"].setdefault("drops", {})
            drops[role] = drops.get(role, 0) + 1
        elif role["id"] not in by_company.setdefault(c["id"], {}):
            by_company[c["id"]][role["id"]] = role
    companies = []
    for f in found:
        c, d = f["company"], f["diag"]
        rs = list(by_company.get(c["id"], {}).values())
        espoo = bool(c.get("espoo_registered", {}).get("value"))
        d["espoo_registered"] = espoo
        d["tech_roles_capital_or_remote"] = len(rs)
        d["espoo_roles"] = sum(1 for r in rs if r.get("is_espoo", {}).get("value"))
        # a company counts if it is registered in Espoo or has a role located in Espoo
        d["counts"] = espoo or d["espoo_roles"] > 0
        if not d["counts"]:
            continue
        companies.append(c)
        roles += rs
    dump = lambda p, x: p.write_text(json.dumps(x, ensure_ascii=False, indent=1) + "\n")
    out = Path(os.environ.get("ESPOO_OUT") or WORK)  # ESPOO_OUT: a scratch dir for offline re-runs
    out.mkdir(exist_ok=True)
    dump(out / "companies.raw.json", companies)
    dump(out / "roles.raw.json", roles)
    dump(out / "diag.json", {"companies": [f["diag"] for f in found], "fetch": lib.stats, "llm": llm.spend()})
    print(f"wrote {len(companies)} companies, {len(roles)} roles")


if __name__ == "__main__":
    main()
