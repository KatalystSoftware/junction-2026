"""Wikitext to plain-text passages: one list of (section, chunk_no, text, cites) per revision.

Templates, references, tables, files and categories are dropped and links become their words,
so the text is what a reader sees in the article body. Sections that only list sources or links
are skipped. Each section is split into passages of about 120–300 words at paragraph ends.

`cites` keeps where the references were: [[offset, citation]], offset being the position in the
passage text right after which the <ref> stood, and citation a short rendering of it (author,
title, work, year, pages, URL). A quote is cited when a reference stands in it or right after it.
"""

import re

import mwparserfromhell

MIN_WORDS, TARGET_WORDS, MAX_WORDS = 40, 200, 300

# Sections that hold sources, links or navigation, not article content.
SKIP_SECTIONS = {
    "lähteet",
    "viitteet",
    "aiheesta muualla",
    "katso myös",
    "kirjallisuutta",
    "kirjallisuus",
    "lisätietoja",
    "huomautukset",
    "lähdeluettelo",
    "lähdekirjallisuus",
    "källor",
    "referenser",
    "noter",
    "se även",
    "externa länkar",
    "vidare läsning",
    "litteratur",
    "fotnoter",
    "källhänvisningar",
    "references",
    "notes",
    "see also",
    "external links",
    "further reading",
    "bibliography",
    "sources",
    "footnotes",
    "citations",
    "works cited",
    "notes and references",
    "general and cited references",
    "general references",
    "cited references",
    "selected bibliography",
    "lähdeteokset",
    "kirjallisuutta ja lähteitä",
    "tryckta källor",
    "webbkällor",
}
_FILE_PREFIXES = (
    "file:",
    "image:",
    "tiedosto:",
    "kuva:",
    "fil:",
    "bild:",
    "category:",
    "luokka:",
    "kategori:",
    "media:",
)
_HEADING = re.compile(r"^(={2,6})\s*(.+?)\s*\1\s*$", re.M)
_BLANKS = re.compile(r"\n\s*\n+")
_SPACES = re.compile(r"[ \t\u00a0]+")
_MARK = re.compile("\ue000([0-9]+)\ue001")
LIST, ITEM = "\ue002", "\ue003"
# A citation: a <ref> tag, or a short-footnote template that makes one ({{sfn|Wilson|2009|p=3}}).
_REF = re.compile(r"<ref[\s>/]|\{\{\s*(?:sfnp?|sfnm|harvnb|efn)\s*\|", re.I)
_QUALITY = [
    (re.compile(r"\{\{\s*(Suositeltu|Utmärkt|Featured article)\s*[|}]", re.I), "featured"),
    (re.compile(r"\{\{\s*(Hyvä artikkeli|Bra|Good article)\s*[|}]", re.I), "good"),
]
_CITE_KEYS = [
    ("author", "last", "last1", "tekijä", "sukunimi", "författare", "efternamn"),
    ("title", "nimeke", "titel", "otsikko"),
    ("work", "journal", "newspaper", "website", "julkaisu", "verk", "tidning"),
    ("publisher", "julkaisija", "utgivare", "förlag"),
    ("year", "date", "ajankohta", "vuosi", "år", "datum"),
    ("pages", "page", "sivu", "sivut", "sida", "sidor"),
    ("url", "www", "osoite"),
]


def stats(wikitext):
    """(number of citations, 'featured' | 'good' | None) for a revision."""
    quality = next((q for pattern, q in _QUALITY if pattern.search(wikitext)), None)
    return len(_REF.findall(wikitext)), quality


def _cite_text(contents):
    parts = []
    for t in contents.filter_templates(recursive=False):
        values = {str(p.name).strip().lower(): p.value.strip_code().strip() for p in t.params}
        for keys in _CITE_KEYS:
            value = next((values[k] for k in keys if values.get(k)), None)
            if value:
                parts.append(value)
    if not parts:  # a source template without the usual keys, such as {{BLF|3110|namn=…}}
        for t in contents.filter_templates(recursive=False):
            parts.append(" ".join([str(t.name).strip()] + [p.value.strip_code().strip() for p in t.params]))
    text = ", ".join(parts) or contents.strip_code().strip() or str(contents).strip()
    return " ".join(text.split())[:300]


def _ref_name(tag):
    return str(tag.get("name").value).strip().strip("\"'") if tag.has("name") else None


def _ref_names(code):
    names = {}
    for tag in code.ifilter_tags(recursive=True):
        if str(tag.tag).lower() == "ref" and tag.contents and str(tag.contents).strip():
            name = _ref_name(tag)
            if name and name not in names:
                names[name] = _cite_text(tag.contents)
    return names


def _plain(wikitext, refs=None, names=None, lists=False, edition="en"):
    """Plain text. With refs (a list), each <ref> becomes a marker indexing its citation in it.
    With lists, each bulleted or numbered list is a paragraph of its own that starts with LIST."""
    code = mwparserfromhell.parse(wikitext)
    for tag in list(code.ifilter_tags(recursive=True)):
        if refs is not None and str(tag.tag).lower() == "ref":
            text = (
                _cite_text(tag.contents)
                if tag.contents and str(tag.contents).strip()
                else (names or {}).get(_ref_name(tag), "")
            )
            refs.append(text)
            try:
                code.replace(tag, f"\ue000{len(refs) - 1}\ue001")
            except ValueError:
                pass
    # A list wrapped in a layout template is article text: {{Columns-list|* …}} holds the foreign
    # honours of Nicholas II, and dropping it raised a false coverage gap. Unwrap until none is left,
    # since an unwrapped body can hold another wrapper.
    while True:
        wrapped = [(t, _list_body(t)) for t in code.ifilter_templates(recursive=False)]
        wrapped = [(t, body) for t, body in wrapped if body is not None]
        if not wrapped:
            break
        for node, body in wrapped:
            try:
                code.replace(node, body)
            except ValueError:
                _remove(code, node)
    for node in list(code.ifilter_templates(recursive=False)):
        text = _inline(node, edition)
        if text is None:
            _remove(code, node)
        else:
            try:
                code.replace(node, text)
            except ValueError:
                pass
    for tag in list(code.ifilter_tags(recursive=True)):
        if str(tag.tag).lower() in (
            "ref",
            "table",
            "gallery",
            "math",
            "references",
            "score",
            "timeline",
            "imagemap",
            "syntaxhighlight",
            "graph",
        ):
            _remove(code, tag)
    for link in list(code.ifilter_wikilinks(recursive=True)):
        target = str(link.title).strip().lower().lstrip(":")
        if target.startswith(_FILE_PREFIXES) or re.match(r"^[a-z]{2,3}(-[a-z]+)?:", target):
            _remove(code, link)
    for tag in list(code.ifilter_tags(recursive=True)):  # "*" and "#" items, which strip_code drops
        if str(tag.tag).lower() == "li":
            try:
                code.replace(tag, ITEM)
            except ValueError:
                pass
    text = code.strip_code(normalize=True, collapse=True, keep_template_params=False)
    lines, in_list = [], False
    for line in text.split("\n"):
        line = line.strip()
        # Leftover table rows, list markers and magic words.
        if line.startswith(("{|", "|", "!", "__")):
            continue
        item = line.startswith(ITEM)
        if lists and item != in_list and line:  # a list is its own paragraph, marked for passages()
            lines += ["", LIST] if item else [""]
            in_list = item
        lines.append(line.lstrip(ITEM + "*#:; ").strip())
    text = "\n".join(lines).replace(LIST + "\n", LIST)
    text = _SPACES.sub(" ", text)
    text = re.sub(r" ([,.;:])", r"\1", text)
    text = re.sub(r"\(\s*[,;]?\s*\)", "", text)
    # What is left of a parenthesis whose language templates were removed: "( or Lapuan liike, )".
    # Real prose has no space after "(", so only those leftovers change.
    text = re.sub(r"\( +(?:(?:or|eller|tai) +)?([^()]*?)[ ,;]*\)", r"(\1)", text)
    text = re.sub(r" ?\(\)", "", text)
    return _BLANKS.sub("\n\n", text).strip()


_DASHES = {
    "spaced en dash space": " – ",
    "spaced en dash": " –",
    "snd": " – ",
    "spaced ndash": " – ",
    "ndash": "–",
    "mdash": "—",
    "nbsp": " ",
    "en dash": "–",
    "–": "–",
    "sndash": " – ",
}
_FIRST = (
    "nowrap",
    "nobr",
    "small",
    "lang",
    "transl",
    "sic",
    "abbr",
    "sortname",
    "date",
    "oldstyledate",
    "oldstyledateny",
    "oldstyledatedy",
    "frac",
)
# Language names as each edition writes them in "{{langx|ru|…}}": "Russian: …", "ryska: …".
_LANG_NAMES = {
    "en": {
        "fi": "Finnish",
        "sv": "Swedish",
        "en": "English",
        "ru": "Russian",
        "de": "German",
        "fr": "French",
        "la": "Latin",
        "et": "Estonian",
        "se": "Northern Sami",
        "no": "Norwegian",
        "da": "Danish",
        "pl": "Polish",
        "uk": "Ukrainian",
        "krl": "Karelian",
    },
    "sv": {
        "fi": "finska",
        "sv": "svenska",
        "en": "engelska",
        "ru": "ryska",
        "de": "tyska",
        "fr": "franska",
        "la": "latin",
        "et": "estniska",
        "se": "nordsamiska",
        "no": "norska",
        "da": "danska",
        "pl": "polska",
        "uk": "ukrainska",
        "krl": "karelska",
    },
    "fi": {
        "fi": "suomeksi",
        "sv": "ruotsiksi",
        "en": "englanniksi",
        "ru": "venäjäksi",
        "de": "saksaksi",
        "fr": "ranskaksi",
        "la": "latinaksi",
        "et": "viroksi",
        "se": "pohjoissaameksi",
        "no": "norjaksi",
        "da": "tanskaksi",
        "pl": "puolaksi",
        "uk": "ukrainaksi",
        "krl": "karjalaksi",
    },
}
# A hand-written hatnote on the first lines of a section: ":''För det finländska fartyget, se …''".
_HATNOTES = re.compile(r"\A(?:[ \t]*\n|:+[ \t]*''[^\n]*''[ \t]*(?:\n|\Z))+")
_DATES = (
    "birth date",
    "death date",
    "birth date and age",
    "death date and age",
    "start date",
    "end date",
    "syntymäaika ja ikä",
    "kuolinaika ja ikä",
    "födelsedatum och ålder",
)


# Layout templates whose content parameter is wikitext readers see, usually a bulleted list.
_WRAPPERS = (
    "columns-list",
    "columns list",
    "colist",
    "col-list",
    "div col",
    "plainlist",
    "plain list",
    "flatlist",
    "flat list",
)
# Templates whose unnamed parameters are list items readers see.
_ITEMS = (
    "ubl",
    "unbulleted list",
    "ubil",
    "bulleted list",
    "blist",
    "hlist",
    "flowlist",
    "ordered list",
    "collapsible list",
)


def _list_body(t):
    """Wikitext of the list a layout template shows, or None when `t` is not one."""
    name = str(t.name).strip().lower().replace("_", " ")
    if name in _WRAPPERS:
        for key in ("content", "1"):
            if t.has(key):
                return "\n" + str(t.get(key).value).strip() + "\n"
        return ""
    if name in _ITEMS:
        items = [str(p.value).strip() for p in t.params if not p.showkey and str(p.value).strip()]
        return "\n" + "\n".join("* " + x for x in items) + "\n"
    return None


def _inline(t, edition="en"):
    """Text for a few inline templates readers see as words, or None to drop the template."""
    name = str(t.name).strip().lower().replace("_", " ")
    pos = [p.value.strip_code().strip() for p in t.params if not p.showkey]
    names = _LANG_NAMES.get(edition, _LANG_NAMES["en"])
    if name in _DASHES:
        return _DASHES[name]
    if name in ("lang", "transl") and len(pos) >= 2:
        return pos[1]
    if name == "langx" and len(pos) >= 2:  # {{langx|fi|Lapuanliike}}: "Finnish: Lapuanliike"
        return f"{names.get(pos[0].lower(), pos[0])}: {pos[1]}"
    if name.startswith("lang-") and pos:  # {{lang-fi|…}}, the older form
        return f"{names.get(name[5:], name[5:])}: {pos[0]}"
    if name in ("ill", "interlanguage link", "link-interwiki") and pos:
        return pos[0]
    if (name in _FIRST or name.startswith("oldstyledate")) and pos:
        return pos[0]
    if name in ("convert", "cvt") and len(pos) >= 2:
        return f"{pos[0]} {pos[1]}"
    if name in ("circa", "c."):
        return "c. " + pos[0] if pos else "c."
    if name in _DATES and len(pos) >= 3 and all(x.isdigit() for x in pos[:3]):
        return "-".join(pos[:3])
    if name in _DATES and pos and pos[0].isdigit():
        return pos[0]
    return None


def _remove(code, node):
    try:
        code.remove(node)
    except ValueError:
        pass


def sections(wikitext, cites=False, edition="en"):
    """[(section path, plain text, anchors)], the lead first with section "". With cites, anchors
    are [(the 40 characters of text before a <ref>, its citation)]; otherwise []. `edition` is
    the Wikipedia the text comes from, for the language names it writes."""
    names = _ref_names(mwparserfromhell.parse(wikitext)) if cites else None
    parts, path = [], []
    pos, title = 0, ""
    for m in _HEADING.finditer(wikitext):
        parts.append((title, wikitext[pos : m.start()]))
        level = len(m.group(1))
        heading = _plain(m.group(2)) or m.group(2)
        path = [p for p in path if p[0] < level] + [(level, heading)]
        title = " › ".join(h for _, h in path)
        pos = m.end()
    parts.append((title, wikitext[pos:]))
    out = []
    for title, body in parts:
        if any(h.strip().lower().rstrip(":").strip() in SKIP_SECTIONS for h in title.split(" › ")):
            continue
        body = _HATNOTES.sub("", body)
        text = _plain(body, lists=True, edition=edition)
        if not text.replace(LIST, "").strip():
            continue
        anchors = []
        if cites and "<ref" in body.lower():
            refs = []
            marked = _plain(body, refs, names, edition=edition)
            for m in _MARK.finditer(marked):
                before = " ".join(_MARK.sub("", marked[max(0, m.start() - 200) : m.start()]).split())
                if before and refs[int(m[1])]:
                    anchors.append((before[-40:], refs[int(m[1])]))
        out.append((title, text, anchors))
    return out


def _locate(chunks, anchors):
    """[[offset, citation]] per chunk: where each anchor's text ends, searched in order."""
    out = [[] for _ in chunks]
    i, pos = 0, 0
    for frag, cite in anchors:
        pattern = re.compile(r"\s+".join(map(re.escape, frag.split())))
        for j in range(i, len(chunks)):
            # Anchors of nearby refs overlap, so a match may start before the previous one ended.
            floor = pos if j == i else 0
            m = next((m for m in pattern.finditer(chunks[j], max(0, floor - len(frag) - 10)) if m.end() >= floor), None)
            if m:
                out[j].append([m.end(), cite])
                i, pos = j, m.end()
                break
    return out


def passages(wikitext, cites=False, edition="en"):
    """[(section, chunk_no, text, cites)] in article order; cites is [] unless asked for."""
    out = []
    for section, text, anchors in sections(wikitext, cites, edition):
        chunks, cur, cur_list = [], [], False
        for para in text.split("\n\n"):
            is_list = para.startswith(LIST)
            words = para.replace(LIST, "").split()
            if not words:
                continue
            # Prose and a list each long enough to stand alone go to separate passages, so a list
            # (orders, works, offices) is compared with lists and not diluted by the prose around it.
            if cur and is_list != cur_list and len(cur) >= MIN_WORDS and len(words) >= MIN_WORDS:
                chunks.append(cur)
                cur = []
            if not cur:
                cur_list = is_list
            while len(words) > MAX_WORDS:
                cut = _sentence_cut(words, TARGET_WORDS, MAX_WORDS)
                if cur:
                    chunks.append(cur)
                    cur = []
                chunks.append(words[:cut])
                words = words[cut:]
            if cur and len(cur) + len(words) > MAX_WORDS:
                chunks.append(cur)
                cur = []
            cur = cur + ([("\n\n")] if cur else []) + words
            if len(cur) >= TARGET_WORDS:
                chunks.append(cur)
                cur = []
        if cur:
            if chunks and len(cur) < MIN_WORDS and len(chunks[-1]) + len(cur) <= MAX_WORDS + MIN_WORDS:
                chunks[-1] = chunks[-1] + ["\n\n"] + cur
            else:
                chunks.append(cur)
        texts = [" ".join(words).replace(" \n\n ", "\n\n") for words in chunks]
        located = _locate(texts, anchors)
        for i, text in enumerate(texts):
            if len(text) >= 20:
                out.append((section, i, text, located[i]))
    return out


def cited(text, cites, quote):
    """The citation of the first reference in or right after `quote` within `text`, or None."""
    start = text.find(quote) if quote else -1
    if start < 0:
        return None
    end = start + len(quote)
    return next((c for off, c in cites if start < off <= end + 2), None)


def paragraph_cited(text, cites, quote):
    """The citation of the reference at the end of the paragraph holding `quote`, or None when
    that paragraph does not end in one. A passage ending mid-paragraph counts as its end."""
    start = text.find(quote) if quote else -1
    if start < 0:
        return None
    end = text.find("\n\n", start + len(quote))
    end = len(text) if end < 0 else end
    at_end = [c for off, c in cites if start < off and end - 2 <= off <= end]
    return at_end[-1] if at_end else None


def _sentence_cut(words, target, limit):
    for i in range(target, limit):
        if words[i - 1].endswith((".", "!", "?")):
            return i
    for i in range(target, 0, -1):
        if words[i - 1].endswith((".", "!", "?")):
            return i
    return limit
