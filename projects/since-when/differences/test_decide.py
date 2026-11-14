"""Tests for decide.py that send no request: llm.decide is replaced.

python -m unittest differences.test_decide
"""

import unittest
from unittest import mock

from . import claims, decide
from .test_claims import EN, pair, row

ARTICLE = [
    {"wikidata_id": "Q1", "lang": "en", "as_of": "2026-11-14", "chunk_id": 30, "ord": 0, "section": "", "chunk_no": 0}
    | {"rev_id": 1, "text": EN},
    {"wikidata_id": "Q1", "lang": "en", "as_of": "2026-11-14", "chunk_id": 31, "ord": 1, "section": "After"}
    | {"chunk_no": 1, "rev_id": 1, "text": "The movement was banned in 1932."},
]


def answers(verdict, passage="passage_1", sentence="sentence_1"):
    """llm.decide that gives every verdict question `verdict` at 0.8 and picks the same passage and sentence."""

    def fake(text, questions):
        out = {}
        for key, q in questions.items():
            options = list(q["criteria"])
            choice = verdict if "supported" in options else passage if "passage_1" in options else sentence
            out[key] = {"choice": choice, "probabilities": {o: 0.8 if o == choice else 0.2 / 3 for o in options}}
        return out, {"total_input_tokens": 1}

    return fake


class Decide(unittest.TestCase):
    def setUp(self):
        self.claim = claims.row_claims(pair(), [row("missing_fact", "Marssiin osallistui 12 600 miestä", "", "en")])[0]
        cache = mock.patch.object(decide, "CACHE_DIR", decide.Path(self.enterContext(_tmp())))
        self.enterContext(cache)

    def judged(self, fake, read="article", threshold=0.5):
        with mock.patch.object(decide.llm, "decide", side_effect=fake) as sent:
            answer = decide.judge_article([self.claim], ARTICLE, read)[0]
        return decide.verdict(self.claim, answer, threshold), sent

    def test_a_supported_claim_gets_the_sentence_chosen_as_its_quote(self):
        v, sent = self.judged(answers("supported", sentence="sentence_2"))
        self.assertEqual((v["verdict"], v["quote"]), ("supported", "It ended at Senate Square."))
        self.assertEqual(v["passage"]["chunk_id"], 30)
        self.assertEqual(sent.call_count, 3)  # verdict, passage, sentence
        self.assertIn("Passage 2", sent.call_args_list[0].args[0])  # the whole article is the input

    def test_the_two_contradicted_answers_count_together_and_below_the_threshold_nothing_counts(self):
        v, _ = self.judged(answers("other_figure"))
        self.assertEqual((v["verdict"], v["difference"]), ("contradicted", "figure"))
        v, _ = self.judged(answers("other_figure"), threshold=0.9)
        self.assertEqual((v["verdict"], v["difference"], v["note"]), ("not_mentioned", "none", ""))

    def test_a_claim_not_mentioned_is_not_located_and_a_second_run_sends_nothing(self):
        v, sent = self.judged(answers("not_mentioned"))
        self.assertEqual((v["verdict"], v["quote"], v["passage"], sent.call_count), ("not_mentioned", "", None, 1))
        _, again = self.judged(answers("not_mentioned"))
        self.assertEqual(again.call_count, 0)

    def test_reading_passages_puts_the_claims_own_search_results_in_the_question(self):
        self.claim["evidence"] = {"searched": 2, "passages": [ARTICLE[1]], "sql": "", "ms": 0}
        v, sent = self.judged(answers("supported"), read="passages")
        text, questions = sent.call_args_list[0].args
        self.assertNotIn("banned in 1932", text)
        self.assertIn("banned in 1932", questions["c0"]["instructions"])
        self.assertEqual(v["passage"]["chunk_id"], 31)


def _tmp():
    import tempfile

    return tempfile.TemporaryDirectory()


if __name__ == "__main__":
    unittest.main()
