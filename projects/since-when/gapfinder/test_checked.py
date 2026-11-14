"""Tests for checked.py with a cursor that answers from memory: no database.

python -m unittest gapfinder.test_checked
"""

import json
import tempfile
import unittest
from pathlib import Path

from . import checked

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
        kept = [
            row("numbers", "12 600 miestä", "about 12,000 men", original=first, **written),
            row(
                "numbers",
                "Passage eleven",
                "It ended",
                **{**written, "claim": {**written["claim"], "origin": "extract"}},
            ),
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


if __name__ == "__main__":
    unittest.main()
