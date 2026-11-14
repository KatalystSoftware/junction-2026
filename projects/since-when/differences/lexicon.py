"""Loaded words: one edition names or judges something with a word the other edition avoids.

Each concept belongs to a family of competing words for the same thing, such as "fascist" and
"radical right" for a movement. A loaded concept found in one passage counts as a framing
difference only when the other passage uses a different word of the same family, so the two
passages talk about the same thing in different words. A passage that never characterises the
thing at all is left to the model.
"""

import re

LANG_NAME = {"fi": "Finnish", "sv": "Swedish", "en": "English"}

# family -> concept -> (loaded, {lang: regex}). Loaded concepts are reported; the others only show
# that a passage names the same thing in a more neutral way.
FAMILIES = {
    "political label": {
        "fascist": (True, {
            "fi": r"(?<!anti-)\bfasis[mt]\w*",
            "sv": r"(?<!anti-)\bfascis[mt]\w*",
            "en": r"(?<!anti-)\b(?:proto-)?fascis[mt]\w*",
        }),
        "pro-Nazi": (True, {
            "fi": r"\bnatsimielis\w*|\bnatsimyönteis\w*",
            "sv": r"\bnazistvänlig\w*|\bpronazis\w*",
            "en": r"\bpro-nazi\w*",
        }),
        "far right": (True, {
            "fi": r"\bäärioikeisto\w*|\boikeistoäärimmäis\w*|\bäärinationalis\w*|\bultranationalis\w*",
            "sv": r"\bhögerextrem\w*|\bextremt? höger\w*|\bultranationalis\w*",
            "en": r"\bfar[- ]right\b|\bextreme[- ]right\w*|\bright-wing extrem\w*|\bultranationalis\w*",
        }),
        # Not the same as far right: Finnish "oikeistoradikaali" is "right-wing radical".
        "radical right": (True, {
            "fi": r"\boikeistoradikaal\w*|\bradikaalioikeisto\w*",
            "sv": r"\bhögerradikal\w*|\bradikal höger\w*",
            "en": r"\bradical[- ]right\w*|\bright-wing radical\w*",
        }),
        "nationalist": (False, {
            "fi": r"\bkansallismielis\w*|\bnationalis\w*",
            "sv": r"\bnationalis\w*",
            "en": r"\bnationalis\w*",
        }),
        "anti-communist": (False, {
            "fi": r"\bantikommunis\w*|\bkommunisminvastai\w*",
            "sv": r"\bantikommunis\w*",
            "en": r"\banti-?communis\w*",
        }),
    },
    "name of the 1918 war": {
        "War of Liberation": (True, {
            "fi": r"\bvapaussod\w*|\bvapaussota\w*",
            "sv": r"\bfrihetskrig\w*",
            "en": r"\bwar of liberation\b|\bliberation war\b",
        }),
        "class war": (True, {"fi": r"\bluokkasod\w*|\bluokkasota\w*", "sv": r"\bklasskrig\w*", "en": r"\bclass war\b"}),
        "Red Rebellion": (True, {"fi": r"\bpunakapina\w*", "sv": r"\bröda upproret\b", "en": r"\bred rebellion\b"}),
        "civil war": (False, {
            "fi": r"\bsisällisso\w*|\bkansalaisso\w*",
            "sv": r"\binbördeskrig\w*|\bmedborgarkrig\w*",
            "en": r"\bcivil war\b",
        }),
    },
    "name of the camps": {
        "concentration camp": (True, {
            "fi": r"\bkeskitysleir\w*",
            "sv": r"\bkoncentrationsläger\w*",
            "en": r"\bconcentration camps?\b",
        }),
        "prison camp": (False, {
            "fi": r"\bvankileir\w*",
            "sv": r"\bfångläger\w*",
            "en": r"\bprison(?:er)?(?:[- ]of[- ]war)? camps?\b|\bpow camps?\b",
        }),
    },
    "name of the violence": {
        "terror": (True, {"fi": r"\bterror\w*", "sv": r"\bterror\w*", "en": r"\bterror\b|\bterrori[sz]\w*"}),
        "political violence": (False, {
            "fi": r"\bpoliittis\w* väkivalt\w*",
            "sv": r"\bpolitiskt? våld\w*",
            "en": r"\bpolitical violence\b",
        }),
    },
    "name of the uprising": {
        "coup": (True, {
            "fi": r"\bvallankaappau\w*|\bkaappausyrity\w*",
            "sv": r"\bstatskupp\w*|\bkupp(?:en|försök\w*)?\b",
            "en": r"\bcoup\b",
        }),
        # Not the February or October revolutions, which are names of other events.
        "revolution": (True, {
            "fi": r"(?<!helmikuun )(?<!lokakuun )\bvallankumou\w*",
            "sv": r"(?<!februari)(?<!oktober)\brevolution\w*",
            "en": r"(?<!February )(?<!October )\brevolution\w*",
        }),
        "rebellion": (False, {"fi": r"kapina\w*|\bkapino\w*", "sv": r"uppror\w*", "en": r"\brebellion\b|\brevolt\b|\buprising\b"}),
    },
}

_COMPILED = {
    family: {concept: (loaded, {lang: re.compile(rx, re.I) for lang, rx in rxs.items()}) for concept, (loaded, rxs) in concepts.items()}
    for family, concepts in FAMILIES.items()
}

# A sentence ends at . ! or ? followed by a capital, but not after an initial such as "C. G. E.".
_SENTENCE_END = re.compile(r"(?<!\b[A-ZÅÄÖ])[.!?](?=\s+[\"”(]?[A-ZÅÄÖ0-9])")


def sentence_at(text, pos):
    """The sentence of text that contains position pos, as an exact substring."""
    start = 0
    for m in _SENTENCE_END.finditer(text):
        if m.end() > pos:
            return text[start:m.end()].strip()
        start = m.end()
    return text[start:].strip()


def _in_proper_name(text, m, lang):
    """A Finnish or Swedish match that starts with a capital mid-sentence is part of a name, such as
    "Vapaussodan Rintamamiesten Liitto", not the word itself: both languages write these words in
    lower case."""
    if lang not in ("fi", "sv") or not m.group(0)[:1].isupper():
        return False
    before = text[:m.start()].rstrip()
    return bool(before) and before[-1] not in ".!?:\"”(«"


def find_concepts(text, lang):
    """{family: {concept: first match}} for every concept found in text."""
    found = {}
    for family, concepts in _COMPILED.items():
        for concept, (_, rxs) in concepts.items():
            for m in rxs[lang].finditer(text) if lang in rxs else ():
                if _in_proper_name(text, m, lang):
                    continue
                found.setdefault(family, {})[concept] = m
                break
    return found


def is_lead_start(passage):
    return passage.get("section", "") == "" and passage.get("chunk_no", 0) == 0


def compare(a, b):
    """Framing differences from loaded words, as dicts with type, quote_a, quote_b, summary, terms.

    When both passages open their article's lead, the first sentences are compared on their own
    first: that sentence defines the subject, so a label there weighs more than the same label
    further down. A concept reported for the first sentence is not reported again for the passage.
    """
    side = {"a": a, "b": b}
    scopes = []
    if is_lead_start(a) and is_lead_start(b):
        firsts = {k: sentence_at(p["text"], 0) for k, p in side.items()}
        scopes.append(("first sentence", firsts))
    scopes.append(("passage", {k: p["text"] for k, p in side.items()}))
    out, seen = [], set()
    for scope, texts in scopes:
        found = {k: find_concepts(texts[k], side[k]["lang"]) for k in side}
        for family, concepts in _COMPILED.items():
            for this, other in (("a", "b"), ("b", "a")):
                mine, theirs = found[this].get(family, {}), found[other].get(family, {})
                if not theirs:
                    continue
                only_here = [c for c in mine if concepts[c][0] and c not in theirs and (this, c) not in seen]
                if not only_here:
                    continue
                seen.update((this, c) for c in only_here)
                quote_here = sentence_at(texts[this], mine[only_here[0]].start())
                first_there = min(theirs.values(), key=lambda m: m.start())
                quote_there = sentence_at(texts[other], first_there.start())
                words = ", ".join(f"'{c}'" for c in only_here)
                out.append({
                    "type": "framing",
                    "missing_in": None,
                    "quote_a": quote_here if this == "a" else quote_there,
                    "quote_b": quote_here if this == "b" else quote_there,
                    "summary": f"The {LANG_NAME[side[this]['lang']]} {scope} uses {words} ({family}); "
                               f"the {LANG_NAME[side[other]['lang']]} {scope} uses other words for the same thing.",
                    "terms": only_here,
                })
    return out
