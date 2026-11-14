"""Tests for checked.py with a cursor that answers from memory: no database.

python -m unittest gapfinder.test_checked
"""

import json
import tempfile
import unittest
from pathlib import Path

from . import api, checked

FACT = "Marssiin osallistui 12 600 miestä."
PAIR = "Q1:2026-11-14:fi:10:en:30"


class Cursor:
    """One topic: a Finnish article of two passages and an English one of one, and two findings."""

    def execute(self, sql, params=()):
        if "FROM chunk" in sql:
            self.rows = [
                (10, "fi", "Marssi › Helsinki", "Passage ten. " + FACT),
                (11, "fi", "Loppu", "Passage eleven."),
                (30, "en", "", "The march gathered about 12,000 men. It ended."),
            ]
        elif "FROM article" in sql:
            self.rows = [("fi", 111, 59), ("en", 333, 9)]
        else:  # the findings: a missing fact keyed by its top section and quote, and a numbers row
            self.rows = [
                (7, f"Q1:en:fi:missing_fact::{FACT}", "missing_fact", "en", "fi", None, FACT),
                (8, "Q1:en:fi:numbers::about 12,000 men", "numbers", "en", "fi", "about 12,000 men", "12 600 miestä"),
            ]

    def fetchall(self):
        return self.rows


def row(type_, quote_a, quote_b, missing_in=None, **more):
    base = {"pair_id": PAIR, "wikidata_id": "Q1", "as_of": "2026-11-14", "type": type_, "missing_in": missing_in}
    return {**base, "quote_a": quote_a, "quote_b": quote_b, "summary": "s", "model": "classifier", **more}


def check(verdict, quote="", chunk=30, lang="en", origin="classifier"):
    evidence = {"lang": lang, "chunk_id": chunk, "section": "", "quote": quote, "distance": 0.3} if quote else None
    return {
        "verdict": verdict,
        "claim": {"lang": "fi" if lang == "en" else "en", "quote": FACT, "about": "the march", "origin": origin},
        "checked": {"lang": lang, "searched": 1, "read": 1, "sql": "SELECT 1"},
        "evidence": evidence,
    }


class Records(unittest.TestCase):
    def load(self, kept, aside):
        with tempfile.TemporaryDirectory() as run:
            (Path(run) / "run.json").write_text(json.dumps({"judge": "judge-model"}))
            rows, merged = checked.records(Cursor(), kept, aside, run)
        return {(r["finding_id"], r["outcome"], r["reason"]): r for r in rows}, merged

    def test_a_kept_missing_fact_is_linked_by_the_key_the_classifier_named(self):
        # The classifier named no edition and the check names the one it searched: still finding 7.
        kept = [row("missing_fact", FACT, "", "en", classifier_missing_in=None, **check("not_mentioned"))]
        rows, _ = self.load(kept, [])
        r = rows[(7, "kept", None)]
        self.assertEqual((r["lang"], r["other_lang"], r["quote"], r["other_quote"]), ("en", "fi", None, FACT))
        self.assertEqual(
            (r["rev_id"], r["other_rev_id"], r["other_section"], r["judge"]),
            (333, 111, "Marssi › Helsinki", "judge-model"),
        )

    def test_a_fact_stated_elsewhere_is_set_aside_with_the_passage(self):
        aside = [row("missing_fact", FACT, "", "en", **check("supported", "about 12,000 men"))]
        rows, _ = self.load([], aside)
        r = rows[(7, "set_aside", "stated_elsewhere")]
        self.assertEqual(
            (r["evidence_lang"], r["evidence_rev_id"], r["evidence_quote"]), ("en", 333, "about 12,000 men")
        )
        self.assertEqual(r["evidence_passage"], "The march gathered about 12,000 men. It ended.")

    def test_a_rewritten_row_changes_its_finding_and_a_listed_figure_is_new(self):
        first = {"pair_id": PAIR, "type": "missing_fact", "missing_in": "en", "quote_a": FACT, "quote_b": ""}
        written = {"from_pair": PAIR, **check("contradicted", "about 12,000 men")}
        listed = {"from_pair": PAIR, **check("contradicted", "about 12,000 men", origin="extract")}
        kept = [
            row("numbers", "12 600 miestä", "about 12,000 men", original=first, **written),
            row("numbers", "Passage eleven", "It ended", **listed),
        ]
        rows, _ = self.load(kept, [])
        self.assertEqual(rows[(7, "changed", None)]["type"], "numbers")
        new = rows[(None, "new", None)]
        self.assertEqual((new["lang"], new["quote"], new["other_quote"]), ("en", "It ended", "Passage eleven"))

    def test_one_row_per_finding_and_the_one_that_found_something_wins(self):
        kept = [row("missing_fact", FACT, "", "en", **check("not_mentioned"))]
        aside = [row("missing_fact", FACT, "", "en", **check("supported", "about 12,000 men"))]
        rows, merged = self.load(kept, aside)
        self.assertEqual((list(rows), merged), ([(7, "set_aside", "stated_elsewhere")], 1))

    def test_framing_is_unchecked_and_found_by_its_quotes(self):
        cursor = Cursor()
        execute = cursor.execute

        def with_framing(sql, params=()):
            execute(sql, params)
            if "FROM finding" in sql:
                cursor.rows = [(9, "Q1:en:fi:framing::en=fascist", "framing", "en", "fi", "fascist", "kansanliike")]

        cursor.execute = with_framing
        with tempfile.TemporaryDirectory() as run:
            (Path(run) / "run.json").write_text(json.dumps({"judge": "j"}))
            rows, _ = checked.records(cursor, [row("framing", "kansanliike", "fascist")], [], run)
        self.assertEqual([(r["finding_id"], r["outcome"], r["verdict"]) for r in rows], [(9, "unchecked", None)])


def _row(**over):
    """A checked_finding row as the topic endpoint reads it."""
    row = dict.fromkeys(
        [
            "id",
            "finding_id",
            "outcome",
            "reason",
            "as_of",
            "type",
            "lang",
            "other_lang",
            "section",
            "other_section",
            "quote",
            "other_quote",
            "rev_id",
            "other_rev_id",
            "summary",
            "verdict",
            "claim_lang",
            "claim_quote",
            "claim_about",
            "searched",
            "read_passages",
            "evidence_lang",
            "evidence_rev_id",
            "evidence_section",
            "evidence_quote",
            "evidence_passage",
            "claim_figure",
            "evidence_figure",
            "judge",
            "model",
        ]
    )
    return {**row, "status": "open", "judge": "judge-1", "as_of": "2026-11-14", **over}


class Applied(unittest.TestCase):
    """api.apply_checks: what the topic endpoint makes of the findings and their checked rows."""

    FINDINGS = (
        {"id": 1, "type": "numbers", "lang": "sv", "other_lang": "en", "summary": "old", "quotes": {"sv": "a"}},
        {"id": 2, "type": "numbers", "lang": "sv", "other_lang": "en", "summary": "aside", "quotes": {"sv": "b"}},
        {"id": 3, "type": "framing", "lang": "fi", "other_lang": "sv", "summary": "word list", "quotes": {"sv": "c"}},
    )

    def test_without_checked_rows_every_finding_is_unchecked(self):
        findings, totals = api.apply_checks(self.FINDINGS, [])
        self.assertIsNone(totals)
        self.assertEqual([f["check"] for f in findings], [None, None, None])

    def test_a_changed_finding_is_shown_as_the_check_rewrote_it(self):
        k = _row(id=7, finding_id=1, outcome="changed", type="contradiction", lang="en", other_lang="sv")
        k.update(summary="new", quote="x", other_quote="y", rev_id=11, other_rev_id=12, verdict="contradicted")
        findings, totals = api.apply_checks(self.FINDINGS, [k])
        self.assertEqual(findings[0]["id"], 1)
        self.assertEqual((findings[0]["type"], findings[0]["summary"]), ("contradiction", "new"))
        self.assertEqual(findings[0]["quotes"], {"en": "x", "sv": "y"})
        self.assertEqual(findings[0]["rev_ids"], {"en": 11, "sv": 12})
        self.assertEqual(findings[0]["check"]["judge"], "judge-1")
        self.assertIsNone(findings[2]["check"])
        self.assertEqual(totals["changed"], 1)

    def test_a_changed_finding_keeps_the_source_of_a_quote_it_kept(self):
        f = dict(self.FINDINGS[0], quotes={"sv": "a b c", "en": "x"}, citations={"sv": "Book", "en": None})
        f["paragraph_citations"] = {"sv": "Book 2", "en": "Paper"}
        k = _row(id=7, finding_id=1, outcome="changed", type="numbers", lang="sv", other_lang="en")
        k.update(quote="b", other_quote="y")  # the Swedish quote cut down, the English one another sentence
        findings, _ = api.apply_checks([f], [k])
        self.assertEqual(findings[0]["citations"], {"sv": "Book"})
        self.assertEqual(findings[0]["paragraph_citations"], {"sv": "Book 2"})

    def test_a_set_aside_finding_keeps_its_text_and_carries_the_passage(self):
        k = _row(id=8, finding_id=2, outcome="set_aside", reason="stated_elsewhere", verdict="supported")
        k.update(
            evidence_lang="en", evidence_rev_id=5, evidence_quote="it is here", evidence_passage="Look, it is here."
        )
        findings, totals = api.apply_checks(self.FINDINGS, [k])
        self.assertEqual(findings[1]["summary"], "aside")
        self.assertEqual(findings[1]["check"]["outcome"], "set_aside")
        self.assertEqual(findings[1]["check"]["evidence"]["passage"], "Look, it is here.")
        self.assertEqual(totals["set_aside"], {"stated_elsewhere": 1})

    def test_a_difference_the_check_found_is_added_without_history(self):
        k = _row(id=9, outcome="new", type="numbers", lang="fi", other_lang="en", summary="found", quote="3 000")
        findings, totals = api.apply_checks(self.FINDINGS, [k])
        self.assertEqual(len(findings), 4)
        self.assertEqual((findings[3]["id"], findings[3]["history"], findings[3]["status"]), (-9, False, "open"))
        self.assertEqual(totals["new"], 1)

    def test_a_found_difference_a_person_closed_is_closed(self):
        k = _row(
            id=9, outcome="new", type="numbers", lang="fi", other_lang="en", summary="same", status="not_a_difference"
        )
        findings, _ = api.apply_checks(self.FINDINGS, [k])
        self.assertEqual((findings[3]["status"], findings[3]["outcome"]), ("closed", "not_real"))


class Began(unittest.TestCase):
    """api._norm: an older version of a passage holds a quote when it has the same words, whatever the
    case, punctuation or wiki markup around them."""

    def holds(self, passage, quote):
        return api._norm(quote) in api._norm(passage)

    def test_a_change_of_case_or_markup_does_not_start_a_quote(self):
        quote = "Neljä päivää myöhemmin Venäjä sai suuren poliittisen voiton, kun se valloitti Turun"
        self.assertTrue(
            self.holds("Neljä päivää myöhemmin venäjä sai suuren poliittisen voiton, kun se valloitti ”Turun”.", quote)
        )

    def test_a_new_figure_starts_a_quote(self):
        self.assertFalse(
            self.holds("The march gathered 12,000 men to Helsinki.", "The march gathered 12,600 men to Helsinki")
        )

    def test_a_reworded_sentence_starts_a_quote(self):
        older = "on 21 March Russian army took Åbo while a small detachment was sent to Åland."
        self.assertFalse(
            self.holds(older, "on the same day the Russian army took Turku while a small detachment was sent to Åland")
        )


class BeganRun(unittest.TestCase):
    """api.began: the run of revisions that hold a quote goes on past vandalism and its revert."""

    def test_a_short_gap_does_not_start_the_run(self):
        from datetime import datetime as dt

        quote = "Den svenska fältarmén räknade ca 17 000 man"
        versions = [  # (start, end, rev, text): the words, a vandal blanking them, the rollback
            (dt(2009, 12, 26), dt(2021, 10, 26, 12, 46, 19), 1, quote + "."),
            (dt(2021, 10, 26, 12, 46, 19), dt(2021, 10, 26, 12, 46, 42), 2, "hej hej"),
            (dt(2021, 10, 26, 12, 46, 42), dt(2106, 2, 7), 3, quote + "."),
        ]

        def r(label, sql):
            return [{"lang": "sv", "rev_id": v[2], "row_start": v[0], "row_end": v[1], "text": v[3]} for v in versions]

        f = {"id": 1, "status": "open", "type": "numbers", "summary": "x", "quotes": {"sv": quote}}
        api._BEGAN.pop("QTEST", None)
        api.began(r, "QTEST", [f])
        self.assertEqual(f["began"]["sv"]["at"], dt(2009, 12, 26))


if __name__ == "__main__":
    unittest.main()
