"""Builds eval/pairs.jsonl: the leads of 16 Finnish history topics in fi, sv and en, paired up.

python differences/eval/fetch.py

Each pair compares the leads of two editions (fi-en, fi-sv, sv-en) as plain text from the
MediaWiki API's extracts, cut to whole sentences of at most 450 words. Re-running fetches the
current revisions, so the hand labels in labels.json may stop matching; keep the committed file.
Wikipedia text is CC BY-SA 4.0; each passage carries its title and rev_id for attribution.
"""

import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

TOPICS = [  # English titles
    "Lapua Movement",
    "Finnish Civil War",
    "Mäntsälä rebellion",
    "Patriotic People's Movement (Finland)",
    "Winter War",
    "Continuation War",
    "Carl Gustaf Emil Mannerheim",
    "Jäger Movement",
    "Pehr Evind Svinhufvud",
    "Finnish Civil War prison camps",
    "Academic Karelia Society",
    "Greater Finland",
    "Kingdom of Finland (1918)",
    "White Guard (Finland)",
    "Red Guards (Finland)",
    "Kyösti Kallio",
]
AS_OF = time.strftime("%Y-%m-%d")
MAX_WORDS = 450
UA = {"User-Agent": "junction2026-gap-finder/0.1 (https://github.com/katalystsoftware/junction2026)"}


def api(lang, **params):
    url = f"https://{lang}.wikipedia.org/w/api.php?" + urllib.parse.urlencode(
        {**params, "format": "json", "formatversion": "2"}
    )
    for attempt in range(5):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30))
        except OSError:
            if attempt == 4:
                raise
            time.sleep(2 + 3 * attempt)


def lead(text):
    text = re.split(r"\n==", text, maxsplit=1)[0]
    text = re.sub(r"\s+", " ", text.replace("\ufeff", "")).strip()
    out = []
    for s in re.split(r"(?<=[.!?])\s+(?=[A-ZÅÄÖ\"”])", text):
        if out and len(" ".join(out + [s]).split()) > MAX_WORDS:
            break
        out.append(s)
    return " ".join(out)


def main():
    pairs = []
    for title in TOPICS:
        page = api("en", action="query", titles=title, prop="langlinks|pageprops", lllimit="500", redirects="1")[
            "query"
        ]["pages"][0]
        qid = page["pageprops"]["wikibase_item"]
        titles = {
            "en": page["title"],
            **{l["lang"]: l["title"] for l in page.get("langlinks", []) if l["lang"] in ("fi", "sv")},
        }
        eds = {}
        for lang, t in titles.items():
            p = api(lang, action="query", titles=t, prop="extracts|revisions", explaintext="1", rvprop="ids")["query"][
                "pages"
            ][0]
            eds[lang] = {
                "lang": lang,
                "title": p["title"],
                "section": "",
                "chunk_no": 0,
                "rev_id": p["revisions"][0]["revid"],
                "text": lead(p["extract"]),
            }
            time.sleep(0.3)
        for a, b in (("fi", "en"), ("fi", "sv"), ("sv", "en")):
            if a in eds and b in eds:
                pairs.append(
                    {
                        "pair_id": f"{qid}:{AS_OF}:{a}:0:{b}:0",
                        "wikidata_id": qid,
                        "as_of": AS_OF,
                        "a": eds[a],
                        "b": eds[b],
                    }
                )
        print(title, qid, sorted(eds))
    out = Path(__file__).with_name("pairs.jsonl")
    out.write_text("".join(json.dumps(p, ensure_ascii=False) + "\n" for p in pairs), encoding="utf-8")
    print(len(pairs), "pairs written to", out)


if __name__ == "__main__":
    main()
