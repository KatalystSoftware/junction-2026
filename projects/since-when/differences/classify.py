"""Labels the differences between two aligned passages from different language editions."""

import hashlib
import json
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import lexicon, llm

TYPES = ("missing_fact", "contradiction", "framing", "numbers")

# Suggested weights for the impact score: a reader is misled more by a contradiction or a
# loaded label than by a missing detail.
TYPE_WEIGHT = {"contradiction": 1.0, "framing": 1.0, "numbers": 0.8, "missing_fact": 0.5}

PROMPT_VERSION = 6
CACHE_DIR = Path(
    os.environ.get("DIFFERENCES_CACHE", Path(__file__).resolve().parent.parent / "data" / "differences" / "cache")
)
MAX_DIFFERENCES = 8

# Model differences whose quotes were found in the passages, and those dropped, in this process.
QUOTE_CHECK = {"kept": 0, "dropped": 0}
_stats_lock = threading.Lock()

SYSTEM = f"""You compare two passages about the same topic from two language editions of Wikipedia, for the editors who maintain them. Report the differences that matter most, at most {MAX_DIFFERENCES}. List every contradiction, numbers difference and framing difference first, and only then missing facts, in the slots that are left. Each difference has one type:

- missing_fact: one passage states a fact (an event, date, actor, cause, consequence or claim) that the other leaves out, although the other covers the same ground closely enough that the fact belongs there. missing_in is the passage that lacks it. Quote the fact from the passage that has it; quote the other passage only if one sentence there is where the fact belongs, else leave that quote empty.
- contradiction: both passages say something about the same point and both cannot be true: a different cause, actor, place, outcome or sequence.
- framing: both describe the same thing with different labels, names or judgements, such as "fascist" against "radical right-wing", "terror" against "political violence", "concentration camp" against "prison camp", "coup" against "rebellion", or one presenting as settled what the other presents as disputed. Only words that carry a judgement or a political or moral charge count. Neutral synonyms and different descriptions are not framing: "movement" against "organisation", "attempt" against "failed attempt", "paramilitary units" against "struggle organisation", or two ways of stating the same aim.
- numbers: both give a figure for the same quantity, such as a count, date, duration or percentage, and the figures differ.

Rules:
- Quotes are copied character for character from the passage, in its own language, never translated, one sentence or shorter.
- summary is one neutral English sentence that names the editions by language and says what differs.
- Keep the passage's hedges and attributions in the summary ("has been claimed", "according to", "most sources conclude"): never turn a reported claim into a statement of fact.
- For framing, the summary says the editions use different words, for example "The English lead calls the movement fascist; the Finnish lead calls it radical right-wing." A label can be a deliberate, sourced choice in each edition, so never suggest either one is an error.
- contradiction, numbers and framing need a statement about the same point in both passages, so both quotes are set. When one passage says nothing about the point, it is a missing_fact, never a contradiction or numbers. A passage that gives more detail (an exact date, a longer list) does not contradict one that gives less.
- You see one passage of each article, not the whole article: the other edition may cover the point elsewhere. Describe what the two passages say ("the Finnish passage does not mention ..."), never what an edition, article or lead as a whole says or lacks.
- Both quotes of a difference must be about the same subject. A sentence about a different person, organisation or event is not a match, even if it uses a similar word.
- Never say which edition is right, and never rate an edition's politics or bias.
- Ignore differences of translation, wording, word order, length or style that change no fact or label.
- A list of loaded words may be given. Report one as framing only when both passages describe the same thing.
- If nothing matters, return an empty list."""

SCHEMA = {
    "type": "object",
    "properties": {
        "differences": {
            "type": "array",
            "maxItems": MAX_DIFFERENCES,
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": list(TYPES)},
                    "missing_in": {"type": "string", "enum": ["A", "B", "none"]},
                    "quote_a": {"type": "string"},
                    "quote_b": {"type": "string"},
                    "summary": {"type": "string"},
                },
                "required": ["type", "missing_in", "quote_a", "quote_b", "summary"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["differences"],
    "additionalProperties": False,
}


def _describe(label, p):
    where = f'section "{p["section"]}"' if p.get("section") else "lead"
    if p.get("chunk_no"):
        where += f", part {p['chunk_no'] + 1}"
    return f'Passage {label} ({lexicon.LANG_NAME.get(p["lang"], p["lang"])} Wikipedia, "{p.get("title", "")}", {where}):\n<<<\n{p["text"]}\n>>>'


def _messages(pair, hints):
    user = _describe("A", pair["a"]) + "\n\n" + _describe("B", pair["b"])
    if hints:
        user += "\n\nLoaded words found by a word list:\n" + "\n".join(f"- {h['summary']}" for h in hints)
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


_FOLD = str.maketrans(
    {"“": '"', "”": '"', "„": '"', "«": '"', "»": '"', "‘": "'", "’": "'", "–": "-", "—": "-", "\u00a0": " "}
)


def _normalise(text):
    """text with quotes, dashes and runs of white space folded, and each kept character's index."""
    chars, index = [], []
    for i, ch in enumerate(text.translate(_FOLD)):
        if ch.isspace():
            if chars and chars[-1] == " ":
                continue
            ch = " "
        chars.append(ch)
        index.append(i)
    return "".join(chars), index


def locate(quote, text):
    """The exact substring of text that quote copies, "" for an empty quote, None if not found.

    Models often change white space, quote marks or dashes, or end a quote with "..." or a period
    the passage does not have; those are forgiven. Any other change means the quote is not there.
    """
    quote = quote.strip().strip("\"'").rstrip(".…").removesuffix("...").strip()
    if not quote:
        return ""
    if quote in text:
        return quote
    norm_text, index = _normalise(text)
    norm_quote, _ = _normalise(quote)
    norm_quote = norm_quote.strip()
    at = norm_text.find(norm_quote)
    if at < 0:
        at = norm_text.lower().find(norm_quote.lower())
    if at < 0:
        return None
    return text[index[at] : index[at + len(norm_quote) - 1] + 1]


def _parse(content):
    """The differences in a JSON answer, also when the model wraps it in a code fence or prose."""
    content = content.strip()
    start, end = content.find("{"), content.rfind("}")
    data = json.loads(content[start : end + 1] if start >= 0 and end > start else content)
    return data.get("differences", []) if isinstance(data, dict) else data


def _cached_chat(messages, cfg):
    key = hashlib.sha256(
        json.dumps(
            [PROMPT_VERSION, cfg[0], cfg[2], {k: v for k, v in llm.options().items() if k != "max_tokens"}, messages],
            ensure_ascii=False,
        ).encode()
    ).hexdigest()
    path = CACHE_DIR / f"{key}.json"
    if path.exists():
        return json.loads(path.read_text())["content"]
    for attempt in range(3):
        content = llm.chat_json(messages, SCHEMA, cfg)
        try:
            _parse(content)  # only answers that parse are cached; a broken one is asked again
            break
        except ValueError:
            if attempt == 2:
                raise
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"model": cfg[2], "content": content}, ensure_ascii=False))
    return content


def _row(pair, d, source, model):
    return {
        "pair_id": pair.get("pair_id"),
        "wikidata_id": pair.get("wikidata_id"),
        "as_of": pair.get("as_of"),
        "type": d["type"],
        "missing_in": d.get("missing_in"),
        "quote_a": d["quote_a"],
        "quote_b": d["quote_b"],
        "summary": d["summary"],
        "terms": d.get("terms", []),
        "source": source,
        "model": model,
    }


def _overlaps(q1, q2):
    return bool(q1 and q2) and (q1 in q2 or q2 in q1)


def classify_pair(pair, cfg=None):
    """The differences between pair["a"] and pair["b"], as rows for the finding table.

    cfg is llm.config() by default. Without a model there are no rows: the word list only gives
    the model hints.
    """
    cfg = cfg if cfg is not None else llm.config()
    hints = lexicon.compare(pair["a"], pair["b"])
    if not cfg:
        return []  # the word list only gives the model hints: on its own it matched unrelated sentences

    lang = {"A": pair["a"]["lang"], "B": pair["b"]["lang"]}
    rows = []
    for d in _parse(_cached_chat(_messages(pair, hints), cfg)):
        if d.get("type") not in TYPES or not str(d.get("summary") or "").strip():
            continue  # a card without a summary says nothing; empty summaries came in whole broken answers
        qa, qb = locate(d.get("quote_a", ""), pair["a"]["text"]), locate(d.get("quote_b", ""), pair["b"]["text"])
        kept = qa is not None and qb is not None and bool(qa or qb)
        with _stats_lock:
            QUOTE_CHECK["kept" if kept else "dropped"] += 1
        if not kept:
            continue  # a quote the passage does not contain, or no quote at all
        if d["type"] != "missing_fact" and not (qa and qb):
            # A comparison with nothing to compare against: one edition only lacks the point.
            d = {**d, "type": "missing_fact", "missing_in": "B" if qa else "A"}
        d = {
            **d,
            "quote_a": qa,
            "quote_b": qb,
            "missing_in": lang.get(d.get("missing_in")) if d["type"] == "missing_fact" else None,
        }
        terms = [
            t
            for h in hints
            if d["type"] == "framing" and (_overlaps(qa, h["quote_a"]) or _overlaps(qb, h["quote_b"]))
            for t in h["terms"]
        ]
        d["terms"] = list(dict.fromkeys(terms))
        rows.append(_row(pair, d, "both" if terms else "llm", cfg[2]))
    return rows


def classify_pairs(pairs, workers=8, cfg=None):
    """classify_pair over many pairs in parallel, yielding each pair's rows in input order.

    A pair whose model call fails gets no rows and a warning on stderr; a re-run retries it.
    """
    cfg = cfg if cfg is not None else llm.config()

    def one(pair):
        try:
            return classify_pair(pair, cfg)
        except Exception as e:  # noqa: BLE001  one bad call should not stop a run over thousands of pairs
            print(
                f"differences: {pair.get('pair_id')}: {e}; model call failed, no rows, a re-run retries it",
                file=sys.stderr,
            )
            return []

    with ThreadPoolExecutor(max_workers=workers) as pool:
        yield from pool.map(one, pairs)
