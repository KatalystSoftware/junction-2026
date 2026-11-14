"""Tests for claims.py that need no model and no database.

    python -m unittest differences.test_claims
"""
import unittest
from unittest import mock

from . import claims

FI = ("Presidentti Relander ja kenraali C. G. E. Mannerheim ottivat marssin vastaan. "
      "Marssiin osallistui 12 600 miestä 7. heinäkuuta 1930.\nSe päättyi Senaatintorille.")
EN = "The march gathered about 12,000 men. It ended at Senate Square."


def pair():
    side = lambda lang, chunk, text: {"lang": lang, "title": lang.upper(), "section": "", "chunk_no": 0,
                                      "chunk_id": chunk, "rev_id": 1, "text": text}
    return {"pair_id": "Q1:2026-11-14:fi:10:en:30", "wikidata_id": "Q1", "as_of": "2026-11-14",
            "a": side("fi", 10, FI), "b": side("en", 30, EN)}


def row(type_, quote_a, quote_b, missing_in=None):
    return {"pair_id": "Q1:2026-11-14:fi:10:en:30", "wikidata_id": "Q1", "as_of": "2026-11-14", "type": type_,
            "missing_in": missing_in, "quote_a": quote_a, "quote_b": quote_b, "summary": "s", "terms": [],
            "source": "llm", "model": "m"}


def searched(claim, *texts):
    """The claim with evidence passages of the other edition, as gapfinder.evidence.search adds them."""
    passages = [{"chunk_id": 30 + n, "ord": n, "section": "", "chunk_no": n, "rev_id": 2, "text": text,
                 "sentence": text, "distance": 0.3, "term_hits": 0, "by_vector": n + 1, "by_terms": n + 1}
                for n, text in enumerate(texts)]
    return dict(claim, evidence={"sql": "SELECT 1", "ms": 1.0, "terms": [], "searched": 9, "passages": passages})


def verdict(v, quote="", passage=None, difference="none"):
    return {"verdict": v, "difference": difference, "about": "a", "evidence_about": "e", "note": "The note.",
            "quote": quote, "passage": passage}


class Sentences(unittest.TestCase):
    def test_initials_and_finnish_dates_do_not_end_a_sentence(self):
        self.assertEqual([FI[s:e] for s, e in claims.sentences(FI)],
                         ["Presidentti Relander ja kenraali C. G. E. Mannerheim ottivat marssin vastaan.",
                          "Marssiin osallistui 12 600 miestä 7. heinäkuuta 1930.", "Se päättyi Senaatintorille."])

    def test_a_quote_grows_to_its_sentence(self):
        self.assertEqual(claims.sentence("12 600 miestä", FI), "Marssiin osallistui 12 600 miestä 7. heinäkuuta 1930.")
        self.assertEqual(claims.sentence("not there", FI), "not there")


class RowClaims(unittest.TestCase):
    def test_a_missing_fact_is_looked_up_in_the_edition_said_to_lack_it(self):
        got = claims.row_claims(pair(), [row("missing_fact", "Se päättyi Senaatintorille", "It ended", "en")])
        self.assertEqual([(c["lang"], c["target_lang"], c["quote"], c["always"]) for c in got],
                         [("fi", "en", "Se päättyi Senaatintorille", [30])])

    def test_both_quotes_of_a_numbers_row_are_claims_and_framing_has_none(self):
        got = claims.row_claims(pair(), [row("framing", "x", "y"), row("numbers", "12 600 miestä", "about 12,000 men")])
        self.assertEqual([(c["lang"], c["target_lang"], c["row"]) for c in got], [("fi", "en", 1), ("en", "fi", 1)])
        self.assertEqual(got[0]["text"], "Marssiin osallistui 12 600 miestä 7. heinäkuuta 1930.")


class Judge(unittest.TestCase):
    def claim(self):
        c = claims.row_claims(pair(), [row("missing_fact", "12 600 miestä", "", "en")])[0]
        return searched(c, "Another passage.", EN)

    def ask(self, answer):
        return mock.patch.object(claims, "_ask", lambda kind, messages, schema, cfg, valid: answer)

    def test_the_quote_is_found_in_another_passage_than_the_one_named(self):
        with self.ask({"verdict": "contradicted", "difference": "figure", "passage": 1, "quote": "about 12,000 men",
                       "about": "a", "evidence_about": "e", "note": "n"}):
            v = claims.judge(self.claim(), ("url", "key", "m"))
        self.assertEqual((v["verdict"], v["quote"], v["passage"]["chunk_id"]), ("contradicted", "about 12,000 men", 31))

    def test_a_verdict_without_a_quote_in_the_passages_is_unchecked(self):
        with self.ask({"verdict": "supported", "difference": "none", "passage": 2, "quote": "12,600 men marched",
                       "about": "a", "evidence_about": "e", "note": "n"}):
            self.assertEqual(claims.judge(self.claim(), ("url", "key", "m"))["verdict"], "unchecked")

    def test_not_mentioned_needs_no_quote(self):
        with self.ask({"verdict": "not_mentioned", "difference": "none", "passage": 0, "quote": "",
                       "about": "a", "evidence_about": "", "note": "n"}):
            v = claims.judge(self.claim(), ("url", "key", "m"))
        self.assertEqual((v["verdict"], v["quote"], v["passage"]), ("not_mentioned", "", None))


class Findings(unittest.TestCase):
    def run_rows(self, rows, verdicts):
        cs = [searched(c, "Another passage.", EN if c["target_lang"] == "en" else FI)
              for c in claims.row_claims(pair(), rows)]
        vs = [verdict(v, q, c["evidence"]["passages"][1] if q else None, d) for c, (v, q, d) in zip(cs, verdicts)]
        return claims.findings([pair()], {pair()["pair_id"]: rows}, cs, vs, "m")

    def test_a_missing_fact_stated_elsewhere_is_set_aside_with_its_evidence(self):
        kept, aside = self.run_rows([row("missing_fact", "Se päättyi Senaatintorille", "", "en")],
                                    [("supported", "It ended at Senate Square", "none")])
        self.assertEqual(kept, [])
        self.assertEqual((aside[0]["verdict"], aside[0]["evidence"]["chunk_id"], aside[0]["evidence"]["quote"]),
                         ("supported", 31, "It ended at Senate Square"))

    def test_a_missing_fact_not_mentioned_stays_and_says_what_was_searched(self):
        kept, aside = self.run_rows([row("missing_fact", "Presidentti Relander", "", "en")], [("not_mentioned", "", "none")])
        self.assertEqual(aside, [])
        self.assertEqual((kept[0]["type"], kept[0]["verdict"], kept[0]["checked"]["searched"], kept[0]["evidence"]),
                         ("missing_fact", "not_mentioned", 9, None))

    def test_a_contradicted_claim_is_one_numbers_row_between_the_two_quotes(self):
        kept, aside = self.run_rows([row("numbers", "12 600 miestä", "about 12,000 men")],
                                    [("contradicted", "about 12,000 men", "figure"), ("contradicted", "12 600 miestä", "figure")])
        self.assertEqual(aside, [])
        self.assertEqual(len(kept), 1)   # the row is reached from both editions
        self.assertEqual((kept[0]["type"], kept[0]["pair_id"], kept[0]["quote_a"], kept[0]["quote_b"], kept[0]["summary"]),
                         ("numbers", "Q1:2026-11-14:fi:10:en:31", "12 600 miestä", "about 12,000 men", "The note."))
        self.assertEqual((kept[0]["evidence"]["lang"], kept[0]["evidence"]["quote"], kept[0]["claim"]["lang"]),
                         ("en", "about 12,000 men", "fi"))

    def test_a_numbers_row_with_no_contradicted_claim_is_set_aside_and_framing_is_untouched(self):
        framing = row("framing", "x", "y")
        kept, aside = self.run_rows([framing, row("numbers", "12 600 miestä", "about 12,000 men")],
                                    [("not_mentioned", "", "none"), ("supported", "about 12,000 men", "none")])
        self.assertEqual(kept, [framing])
        self.assertEqual((aside[0]["type"], aside[0]["verdict"], aside[0]["checks"][0]["verdict"]),
                         ("numbers", "not_mentioned", "supported"))


if __name__ == "__main__":
    unittest.main()
