"""Build the seed list of companies to check -> work/seeds.json.

Seed lists, recorded per company in `seed_list`:
  curated      well-known Espoo and capital-region tech employers (name + domain typed in below),
               identity looked up from PRH by name
  prh:<tol>    PRH/YTJ companies located in Espoo in a tech-heavy TOL 2025 class that have a
               website in the register, are an Oy/Oyj and have no bankruptcy or liquidation entry
               (PRH has no size field; a registered website is our stand-in for "big enough to hire")
  listing:<x>  companies linked from an Espoo startup listing page (see LISTINGS)

  python3 seeds.py
"""

import html
import json
import re
import urllib.parse

import lib

PRH = "https://avoindata.prh.fi/opendata-ytj-api/v3/companies"

# TOL 2025 classes (the register switched code sets in 2026; old 62010 etc. are nearly empty)
TOL = ["62100", "62200", "62900", "63100", "58210", "58290", "26110", "26200", "26300", "26400",
       "26510", "27900", "30310", "61900", "72100", "71129"]

# (official name as in the trade register, domain). Order = crawl order.
CURATED = [
    ("ICEYE Oy", "iceye.com"), ("IQM Finland Oy", "iqm.tech"), ("Remedy Entertainment Oyj", "remedygames.com"),
    ("Rovio Entertainment Oy", "rovio.com"), ("Enfuce Financial Services Oy", "enfuce.com"),
    ("Basware Oy", "basware.com"), ("Kuva Space Oy", "kuvaspace.com"), ("Efecte Oyj", "efecte.com"),
    ("Teknologian tutkimuskeskus VTT Oy", "vttresearch.com"), ("Tuxera Oy", "tuxera.com"),
    ("Nokia Oyj", "nokia.com"), ("KONE Oyj", "kone.com"), ("Fortum Oyj", "fortum.com"), ("Neste Oyj", "neste.com"),
    ("Tietoevry Oyj", "tietoevry.com"), ("Orion Oyj", "orion.fi"), ("Metso Oyj", "metso.com"),
    ("Valmet Oyj", "valmet.com"), ("Aalto-korkeakoulusäätiö sr", "aalto.fi"),
    ("CSC-Tieteen tietotekniikan keskus Oy", "csc.fi"), ("Trimble Solutions Oy", "tekla.com"),
    ("Nixu Oyj", "nixu.com"), ("Innofactor Oyj", "innofactor.com"), ("Tecnotree Oyj", "tecnotree.com"),
    ("SemiQon Technologies Oy", "semiqon.tech"), ("Dispelix Oy", "dispelix.com"), ("Picosun Oy", "picosun.com"),
    ("Beneq Oy", "beneq.com"), ("Caruna Oy", "caruna.fi"), ("Fiskars Oyj Abp", "fiskarsgroup.com"),
    ("HMD Global Oy", "hmd.com"), ("Huld Oy", "huld.io"), ("Sofigate Oy", "sofigate.com"),
    ("Xiphera Oy", "xiphera.com"), ("Emberion Oy", "emberion.com"), ("Advacam Oy", "advacam.com"),
    ("PiBond Oy", "pibond.com"), ("Aurora Propulsion Technologies Oy", "aurorapt.space"),
    ("Infinited Fiber Company Oy", "infinitedfiber.com"), ("Paptic Oy", "paptic.com"),
    ("QMill Oy", "qmill.com"), ("EKE-Electronics Oy", "eke-electronics.com"),
    ("Etteplan Oyj", "etteplan.com"), ("Ramboll Finland Oy", "ramboll.com"), ("Accountor Holding Oy", "accountor.com"),
    ("Samlink Oy", "samlink.fi"), ("OpusCapita Solutions Oy", "opuscapita.com"), ("Gasgrid Finland Oy", "gasgrid.fi"),
    ("Gasum Oy", "gasum.com"), ("Geologian tutkimuskeskus", "gtk.fi"), ("Huhtamäki Oyj", "huhtamaki.com"),
    ("Qt Group Oyj", "qt.io"), ("BC Platforms Oy", "bcplatforms.com"), ("Blueprint Genetics Oy", "blueprintgenetics.com"),
    ("Micro Analog Systems Oy", "mas-oy.com"), ("LähiTapiola Keskinäinen Vakuutusyhtiö", "lahitapiola.fi"),
    ("Bayer Oy", "bayer.fi"), ("Citycon Oyj", "citycon.com"), ("Espoon kaupunki", "espoo.fi"),
    ("Varjo Technologies Oy", "varjo.com"), ("Bluefors Oy", "bluefors.com"), ("Canatu Oyj", "canatu.com"),
    ("Vaisala Oyj", "vaisala.com"), ("Okmetic Oy", "okmetic.com"), ("Algorithmiq Oy", "algorithmiq.fi"),
    ("Quanscient Oy", "quanscient.com"), ("Solar Foods Oyj", "solarfoods.com"),
    ("WithSecure Oyj", "withsecure.com"), ("F-Secure Oyj", "f-secure.com"), ("SSH Communications Security Oyj", "ssh.com"),
    ("Elisa Oyj", "elisa.fi"), ("Telia Finland Oyj", "telia.fi"), ("DNA Oyj", "dna.fi"),
    ("Wärtsilä Oyj Abp", "wartsila.com"), ("Kemira Oyj", "kemira.com"), ("Digia Oyj", "digia.com"),
    ("Siili Solutions Oyj", "siili.com"), ("Gofore Oyj", "gofore.com"), ("Vincit Oyj", "vincit.com"),
    ("Nitor Creations Oy", "nitor.com"), ("Solita Oy", "solita.fi"), ("Loihde Oyj", "loihde.com"),
    ("Eficode Oy", "eficode.com"), ("Reaktor Innovations Oy", "reaktor.com"), ("Futurice Oy", "futurice.com"),
    ("Nordcloud Oy", "nordcloud.com"), ("Relex Oy", "relexsolutions.com"), ("Wolt Enterprises Oy", "wolt.com"),
    ("Supercell Oy", "supercell.com"), ("Aiven Oy", "aiven.io"), ("Smartly.io Solutions Oy", "smartly.io"),
    ("Oura Health Oy", "ouraring.com"), ("Swappie Oy", "swappie.com"), ("Silo AI Oy", "silo.ai"),
    ("Yousician Oy", "yousician.com"), ("Small Giant Games Oy", "smallgiantgames.com"),
    ("Metacore Games Oy", "metacoregames.com"), ("Housemarque Oy", "housemarque.com"),
    ("Supermetrics Oy", "supermetrics.com"), ("Sievo Oy", "sievo.com"), ("Unikie Oy", "unikie.com"),
    ("Bittium Oyj", "bittium.com"), ("Insta Group Oy", "insta.fi"), ("Patria Oyj", "patriagroup.com"),
    ("Kempower Oyj", "kempower.com"), ("Liikennevirta Oy", "virta.global"), ("Planmeca Oy", "planmeca.com"),
    ("Granlund Oy", "granlund.fi"), ("Elomatic Oy", "elomatic.com"), ("Sweco Finland Oy", "sweco.fi"),
    ("Rejlers Finland Oy", "rejlers.fi"), ("Ensto Oy", "ensto.com"), ("Helvar Oy Ab", "helvar.com"),
    ("M-Files Oy", "m-files.com"), ("QPR Software Oyj", "qpr.com"), ("Cinia Oy", "cinia.fi"),
    ("Nightingale Health Oyj", "nightingalehealth.com"), ("Hoxhunt Oy", "hoxhunt.com"),
    ("Rightware Oy", "rightware.com"), ("Basemark Oy", "basemark.com"), ("Knowit Solutions Oy", "knowit.fi"),
    ("Visma Solutions Oy", "vismasolutions.com"), ("Murata Electronics Oy", "murata.com"),
]

# Espoo startup and campus listings: every external link on the page becomes a seed.
LISTINGS = {
    "agrid": "https://agrid.fi/community",
    "aalto-startup-center": "https://startupcenter.aalto.fi/startups/",
    "kiuas": "https://www.kiuas.com/portfolio",
    "espoo-innovation-garden": "https://www.espooinnovationgarden.fi/en/espoo-innovation-garden/",
}
_NOT_COMPANY = re.compile(
    r"(linkedin|facebook|twitter|x|instagram|youtube|youtu|tiktok|google|apple|github|medium|vimeo|"
    r"goo|bit|wa|t|typeform|airtable|notion|hubspot|mailchi|eepurl|cookiebot|wordpress|wix|squarespace|"
    r"webflow|aalto|espoo|businessespoo|slush|junction|w3|schema|gstatic|cloudflare|addtoany|spotify|"
    r"calendly|eventbrite|lu|ma)\.(com|fi|org|io|co|me|be|gl|ly|mp|so|net)$", re.I)


def _name(c):
    for n in c.get("names", []):
        if str(n.get("type")) == "1" and not n.get("endDate"):
            return n["name"]
    return None


def _desc(c, lang="3"):
    for d in (c.get("mainBusinessLine") or {}).get("descriptions", []):
        if d.get("languageCode") == lang:
            return d.get("description")
    return None


def _espoo_address(c):
    for a in c.get("addresses", []):
        for p in a.get("postOffices", []):
            if p.get("municipalityCode") == "049" and p.get("languageCode") == "1":
                return {"city": p["city"], "municipality_code": "049"}
    return None


def _city(c):
    for a in sorted(c.get("addresses", []), key=lambda a: a.get("type", 9)):
        for p in a.get("postOffices", []):
            if p.get("languageCode") == "1":
                return {"city": p["city"], "municipality_code": p.get("municipalityCode")}
    return None


def prh_record(c, url, meta):
    """The registry part of a seed. Everything here is checked as `registry` by validate.py."""
    bl = c.get("mainBusinessLine") or {}
    return {
        "business_id": c["businessId"]["value"],
        "name": _name(c),
        "municipality": _espoo_address(c) or _city(c),
        "espoo_registered": bool(_espoo_address(c)),
        "industry": {"code": bl.get("type"), "label": _desc(c), "label_fi": _desc(c, "1")} if bl.get("type") else None,
        "website_registered": (c.get("website") or {}).get("url"),
        "prh_url": url,
        "prh_retrieved_at": meta["retrieved_at"],
    }


def _get(url):
    meta, body = lib.fetch(url)
    if not lib.ok(meta):
        return meta, {}
    try:
        return meta, json.loads(body)
    except Exception:
        return meta, {}


def domain(url):
    u = url if "//" in url else "//" + url
    h = urllib.parse.urlsplit(u).netloc.lower().split(":")[0]
    return h[4:] if h.startswith("www.") else h


def prh_seeds():
    out = []
    for tol in TOL:
        page = 1
        while True:
            url = f"{PRH}?location=Espoo&mainBusinessLine={tol}&page={page}"
            meta, d = _get(url)
            comps = d.get("companies", [])
            for c in comps:
                site = (c.get("website") or {}).get("url")
                forms = {str(f.get("type")) for f in c.get("companyForms", []) if not f.get("endDate")}
                if not site or "." not in site or c.get("companySituations") or not forms & {"16", "17"}:
                    continue
                if not _name(c) or c.get("endDate"):
                    continue
                rec = prh_record(c, url, meta)
                rec.update(seed_list=[f"prh:{tol}"], website=site)
                out.append(rec)
            if not comps or page * 100 >= d.get("totalResults", 0):
                break
            page += 1
    return out


def curated_seeds():
    out = []
    for name, dom in CURATED:
        url = f"{PRH}?name={urllib.parse.quote(name)}"
        meta, d = _get(url)
        comps = [c for c in d.get("companies", []) if _name(c)]
        hit = [c for c in comps if _name(c).casefold() == name.casefold()]
        if not hit:
            hit = [c for c in comps if (c.get("website") or {}).get("url") and domain(c["website"]["url"]) == dom]
        rec = prh_record(hit[0], url, meta) if len(hit) == 1 else {"name_hint": name}
        rec.update(seed_list=["curated"], website=dom)
        out.append(rec)
    return out


_A = re.compile(r"<a\b[^>]*?href\s*=\s*[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", re.S | re.I)


def listing_seeds():
    out = []
    for key, url in LISTINGS.items():
        meta, body = lib.fetch(url)
        if not lib.ok(meta):
            continue
        own = domain(meta["final_url"])
        doc = lib.decode(body, meta.get("content_type", ""))
        seen = set()
        for m in _A.finditer(doc):
            href = html.unescape(m.group(1)).strip()
            if not href.startswith("http"):
                continue
            dom = domain(href)
            if not dom or dom == own or dom.endswith("." + own) or dom in seen or _NOT_COMPANY.search(dom):
                continue
            seen.add(dom)
            text = lib.norm(lib.strip_tags(m.group(2)))[:80]
            out.append({"name_hint": text or None, "seed_list": [f"listing:{key}"], "website": dom,
                        "listing_url": meta["final_url"], "listing_quote": href,
                        "listing_retrieved_at": meta["retrieved_at"]})
    return out


def main():
    seeds, by_dom, by_id = [], {}, {}
    for s in curated_seeds() + listing_seeds() + prh_seeds():
        dom = domain(s["website"])
        prev = by_id.get(s.get("business_id")) or by_dom.get(dom)
        if prev:
            prev["seed_list"] += [x for x in s["seed_list"] if x not in prev["seed_list"]]
            if s.get("business_id") and not prev.get("business_id"):
                prev.update({k: v for k, v in s.items() if k not in ("seed_list", "website")})
            continue
        seeds.append(s)
        by_dom[dom] = s
        if s.get("business_id"):
            by_id[s["business_id"]] = s
    (lib.HERE / "work").mkdir(exist_ok=True)
    (lib.HERE / "work" / "seeds.json").write_text(json.dumps(seeds, ensure_ascii=False, indent=1))
    n = {}
    for s in seeds:
        for x in s["seed_list"]:
            n[x] = n.get(x, 0) + 1
    print(f"{len(seeds)} seeds", n, "with business id", sum(1 for s in seeds if s.get("business_id")))
    print("fetch stats", lib.stats)


if __name__ == "__main__":
    main()
