"""Check that every quote of the shortlist is in the revision of Wikipedia it names.

    python3 demo/check_quotes.py [hero-findings.json] [--offline] [--write]

Prints pass or FAIL for each quote and exits 1 if any fails. --write also writes hero-findings.md
beside the JSON file, from the findings whose quotes all pass. A quote passes when it is an exact
substring of the plain text of the named revision: the text a reader sees at
https://<lang>.wikipedia.org/w/index.php?oldid=<rev>, which is the page as MediaWiki renders it
(action=parse) without footnote markers, edit links, styles and scripts. Runs of white space
(line breaks, no-break spaces) count as one space on both sides; nothing else is forgiven.

Each raw API response is kept under $HERO_REVISIONS (default
~/junction2026-data/mariadb/revisions/agent4)/<lang>/<rev>.parse.json and read from there the next
time; --offline fails a revision that is not there instead of fetching it. Requests go one at a
time with the project's User-Agent and wait on 429 and maxlag.
"""

import html.parser
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REVISIONS = Path(os.environ.get("HERO_REVISIONS", Path.home() / "junction2026-data/mariadb/revisions/agent4"))
USER_AGENT = "junction2026-gap-finder/0.1 (https://github.com/katalystsoftware/junction2026)"
OFFLINE = False


def api(lang, name, **params):
    """The JSON answer of one MediaWiki API request, cached on disk under name."""
    path = REVISIONS / lang / name
    if path.exists():
        return json.loads(path.read_text())
    if OFFLINE:
        raise LookupError(f"{path} is not on disk (offline)")
    url = f"https://{lang}.wikipedia.org/w/api.php?" + urllib.parse.urlencode(
        {**params, "format": "json", "formatversion": 2, "maxlag": 5}
    )
    for attempt in range(8):
        wait = min(60, 5 * 2**attempt)
        try:
            with urllib.request.urlopen(
                urllib.request.Request(url, headers={"User-Agent": USER_AGENT}), timeout=60
            ) as r:
                raw = r.read()
            data = json.loads(raw)
            if data.get("error", {}).get("code") != "maxlag":
                break
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504):
                raise
            wait = max(wait, int(e.headers.get("Retry-After") or 0))
        time.sleep(wait)
    else:
        raise RuntimeError(f"{url}: no answer after 8 tries")
    if "error" in data:
        raise RuntimeError(f"{url}: {data['error']}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    time.sleep(1)  # one request at a time, and not in a burst
    return data


class _Text(html.parser.HTMLParser):
    """The text of a rendered page as a reader sees it."""

    VOID = {"br", "img", "hr", "input", "meta", "link", "wbr", "area", "col", "source", "track", "embed"}
    BLOCK = {
        "p",
        "div",
        "li",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "tr",
        "td",
        "th",
        "br",
        "dd",
        "dt",
        "blockquote",
        "table",
        "ul",
        "ol",
        "section",
        "figcaption",
        "caption",
    }

    def __init__(self):
        super().__init__()
        self.out, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        cls = (dict(attrs).get("class") or "").split()
        if self.skip:
            self.skip += tag not in self.VOID
        elif tag in ("style", "script") or (tag == "sup" and "reference" in cls) or "mw-editsection" in cls:
            self.skip = 1
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_endtag(self, tag):
        if self.skip:
            self.skip -= tag not in self.VOID
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)


def squeeze(text):
    return " ".join(text.split())


def revision_text(lang, rev):
    """The plain text of revision rev of a page of <lang>.wikipedia.org."""
    data = api(lang, f"{rev}.parse.json", action="parse", oldid=rev, prop="text|revid", disablelimitreport=1)
    parser = _Text()
    parser.feed(data["parse"]["text"])
    return squeeze("".join(parser.out))


def revision_info(lang, rev):
    """ids, parentid, timestamp, user and comment of revision rev."""
    data = api(
        lang, f"{rev}.info.json", action="query", prop="revisions", revids=rev, rvprop="ids|timestamp|user|comment"
    )
    page = data["query"]["pages"][0]
    return {"title": page["title"], **page["revisions"][0]}


def check(quote):
    """(passed, note) for one {"lang", "rev", "text"} entry."""
    try:
        found = squeeze(quote["text"]) in revision_text(quote["lang"], quote["rev"])
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"
    return found, "" if found else "not in the revision"


def markdown(doc, findings):
    """The shortlist as Markdown: per topic the main list, then the findings a human should look at."""
    out = [f"# {doc['title']}", "", *doc["intro"], ""]
    for topic in doc["topics"]:
        out += [f"## {topic['title']} ({topic['qid']})", ""]
        for heading, wanted in ((None, "main"), ("Needs a human look", "human")):
            chosen = [f for f in findings if f["topic"] == topic["qid"] and f["list"] == wanted]
            if heading and chosen:
                out += [f"### {heading}", ""]
            for n, f in enumerate(chosen, 1):
                out += [f"**{n}. {f['statement']}**", ""]
                for q in f["quotes"]:
                    info = revision_info(q["lang"], q["rev"])
                    out.append(
                        f"- {q['lang']}, revision [{q['rev']}](https://{q['lang']}.wikipedia.org/w/index.php?oldid={q['rev']})"
                        f" of {info['timestamp'][:10]}: “{q['text']}”" + (f" ({q['note']})" if q.get("note") else "")
                    )
                out.append(f"- Category: Nemotron {f['nemotron']}, Haiku {f['haiku']}")
                out.append(f"- In the tool: {f['url']}")
                if f.get("note"):
                    out.append(f"- {f['note']}")
                out.append("")
    return "\n".join(out)


def main():
    global OFFLINE
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    OFFLINE = "--offline" in sys.argv[1:]
    source = Path(args[0]) if args else HERE / "hero-findings.json"
    doc = json.loads(source.read_text())
    failed = total = 0
    passing = []
    for f in doc["findings"]:
        ok_all = True
        for q in f["quotes"]:
            ok, note = check(q)
            total += 1
            failed += not ok
            ok_all &= ok
            print(
                f"{'pass' if ok else 'FAIL'}  {f['id']}  {q['lang']} {q['rev']}  {json.dumps(q['text'], ensure_ascii=False)}"
                + (f"  ({note})" if note else "")
            )
        if ok_all:
            passing.append(f)
    print(f"{total - failed} of {total} quotes pass")
    if "--write" in sys.argv[1:]:
        source.with_suffix(".md").write_text(markdown(doc, passing))
        print(f"{len(passing)} of {len(doc['findings'])} findings written to {source.with_suffix('.md')}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
