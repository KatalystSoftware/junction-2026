"""Tests for evidence.py that need no database: the search terms, the sentences and the statement.

python -m unittest gapfinder.test_evidence
"""

import re
import unittest

from . import evidence


def matches(quote, text):
    """How many of the quote's search terms match text, as MariaDB's case-blind REGEXP would."""
    return sum(bool(re.search(t, text, re.IGNORECASE)) for t in evidence.terms(quote))


class Terms(unittest.TestCase):
    def test_a_date_matches_the_same_day_in_the_other_languages(self):
        quote = "After a trial, the movement was banned on 21 November 1932"
        self.assertEqual(matches(quote, "Liike kiellettiin 21. marraskuuta 1932."), 2)
        self.assertEqual(matches(quote, "Rörelsen förbjöds den 21 november 1932."), 2)
        self.assertEqual(matches(quote, "Liike kiellettiin 12. marraskuuta 1931."), 0)
        self.assertEqual(matches("On April 4th the men came forward", "Miehet ilmoittautuivat 4. huhtikuuta."), 1)

    def test_a_verb_that_starts_like_a_month_is_no_date(self):
        self.assertEqual(len(evidence.terms("SAJ julisti 16. marraskuuta 1929 yleislakon")), 2)  # the date and the year

    def test_a_number_matches_whatever_separates_its_thousands(self):
        for text in ("12 600 miestä", "12,600 men", "12.600 man", "12\u00a0600 miestä", "12600"):
            self.assertEqual(matches("samla omkring 12 600 utvalda män", text), 1, text)
        self.assertEqual(matches("samla omkring 12 600 utvalda män", "112 600 or 12 6000"), 0)
        self.assertEqual(matches("noin 8000 miehen", "about 8,000 men"), 1)

    def test_a_name_matches_by_its_first_letters_and_a_sentence_opener_is_no_name(self):
        self.assertEqual(
            matches("Presidentti kutsui Svinhufvudin ja Kosolan Helsinkiin", "Svinhufvud met Kosola in Helsingfors"), 2
        )
        self.assertEqual(evidence.terms("After the trial nothing happened"), [])


class Sentences(unittest.TestCase):
    def test_a_short_sentence_joins_its_neighbour(self):
        self.assertEqual(
            evidence.split("Se alkoi 7. heinäkuuta 1930 Helsingissä. Niin. Marssi päättyi Senaatintorille illalla."),
            ["Se alkoi 7. heinäkuuta 1930 Helsingissä. Niin.", "Marssi päättyi Senaatintorille illalla."],
        )


class Statement(unittest.TestCase):
    def test_the_statement_travels_in_time_and_measures_distance(self):
        sql = evidence.search_sql("Q1412941", "fi", "2026-10-22", "ab" * 20, [r"(?<![0-9])12[ .,]?600(?![0-9])"], [7])
        for part in (
            "FOR SYSTEM_TIME AS OF TIMESTAMP '2026-10-22 00:00:00'",
            "VEC_DISTANCE_COSINE(s.embedding, q.embedding)",
            "JOIN passage_sentence AS s ON s.sha = c.sha",
            "c.wikidata_id = 'Q1412941' AND c.lang = 'fi'",
            r"(p.text REGEXP '(?<![0-9])12[ .,]?600(?![0-9])')",
            "OR id = 7",
        ):
            self.assertIn(part, sql)
        self.assertIn("FOR SYSTEM_TIME AS OF NOW(6)", evidence.search_sql("Q1", "en", None, "ab" * 20))


if __name__ == "__main__":
    unittest.main()
