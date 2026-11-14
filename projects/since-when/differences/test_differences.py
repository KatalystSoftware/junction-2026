"""python -m unittest differences.test_differences"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from differences import classify, classify_pair, lexicon

PAIRS = {
    p["pair_id"]: p for p in map(json.loads, (Path(__file__).parent / "eval" / "pairs.jsonl").read_text().splitlines())
}
LAPUA_FI_EN = PAIRS["Q1412941:2026-11-13:fi:0:en:0"]


class WordList(unittest.TestCase):
    def test_lapua_first_sentences_differ_although_both_leads_say_fascism(self):
        hints = lexicon.compare(LAPUA_FI_EN["a"], LAPUA_FI_EN["b"])
        terms = {t for h in hints for t in h["terms"]}
        self.assertTrue(
            {"fascist", "pro-Nazi", "radical right"} <= terms
        )  # fi says fascism only at the end of its lead
        self.assertNotIn("far right", terms)  # "oikeistoradikaali" is right-wing radical, not far right
        for h in hints:
            self.assertIn(h["quote_a"], LAPUA_FI_EN["a"]["text"])
            self.assertIn(h["quote_b"], LAPUA_FI_EN["b"]["text"])

    def test_a_capitalised_name_is_not_the_word(self):
        self.assertNotIn(
            "name of the 1918 war", lexicon.find_concepts("Hän johti Vapaussodan Rintamamiesten Liittoa.", "fi")
        )
        self.assertIn(
            "name of the 1918 war", lexicon.find_concepts("Hän taisteli vapaussodassa. Vapaussota päättyi 1918.", "fi")
        )

    def test_without_a_model_no_rows(self):
        self.assertEqual(classify_pair(LAPUA_FI_EN, cfg=False), [])


class Model(unittest.TestCase):
    def run_with_answer(self, differences):
        cfg = ("http://model.invalid/v1", "key", "test-model")
        with (
            tempfile.TemporaryDirectory() as cache,
            mock.patch.object(classify, "CACHE_DIR", Path(cache)),
            mock.patch.object(classify.llm, "chat_json", return_value=json.dumps({"differences": differences})) as chat,
        ):
            rows = classify_pair(LAPUA_FI_EN, cfg)
            again = classify_pair(LAPUA_FI_EN, cfg)
        self.assertEqual(chat.call_count, 1, "the second run should come from the cache")
        self.assertEqual(rows, again)
        return rows

    def test_quotes_are_exact_and_invented_ones_are_dropped(self):
        rows = self.run_with_answer(
            [
                # Typographic quote marks, a dash and spaces changed by the model, and a trailing "...".
                {
                    "type": "framing",
                    "missing_in": "none",
                    "quote_a": "Lapuanliike tai Lapuan liike oli Suomessa vuosina 1929-1932  toiminut vaikutusvaltainen antikommunistinen ja oikeistoradikaali kansanliike...",
                    "quote_b": "was a radical Finnish nationalist, fascist, pro-Nazi and anti-communist political movement",
                    "summary": "The English first sentence calls the movement fascist and pro-Nazi; the Finnish one calls it radical right-wing.",
                },
                {
                    "type": "contradiction",
                    "missing_in": "none",
                    "quote_a": "Lapuanliike oli kommunistinen puolue.",
                    "quote_b": "founded in and named after the town of Lapua",
                    "summary": "Invented quote.",
                },
                {
                    "type": "missing_fact",
                    "missing_in": "B",
                    "quote_a": "Liikkeen asiaa ajettiin muun muassa kansalaiskokouksilla",
                    "quote_b": "",
                    "summary": "Only the Finnish passage lists the movement's methods.",
                },
                # Real quotes but no summary: nothing to show on a card.
                {
                    "type": "missing_fact",
                    "missing_in": "A",
                    "quote_a": "",
                    "quote_b": "founded in and named after the town of Lapua",
                    "summary": " ",
                },
                # A figure only one edition gives is a missing fact, not a numbers difference.
                {
                    "type": "numbers",
                    "missing_in": "none",
                    "quote_a": "",
                    "quote_b": "was banned after a failed coup d'etat attempt in 1932",
                    "summary": "Only the English passage gives the year of the ban.",
                },
            ]
        )
        self.assertEqual([r["type"] for r in rows], ["framing", "missing_fact", "missing_fact"])
        framing, missing, relabelled = rows
        self.assertEqual(relabelled["missing_in"], "fi")
        self.assertIn(framing["quote_a"], LAPUA_FI_EN["a"]["text"])
        self.assertTrue(framing["quote_a"].endswith("kansanliike"))
        self.assertIn("1929–1932", framing["quote_a"])
        self.assertEqual(framing["source"], "both")
        self.assertIn("fascist", framing["terms"])
        self.assertEqual((missing["missing_in"], missing["source"], missing["model"]), ("en", "llm", "test-model"))
        self.assertEqual(framing["pair_id"], LAPUA_FI_EN["pair_id"])


if __name__ == "__main__":
    unittest.main()
