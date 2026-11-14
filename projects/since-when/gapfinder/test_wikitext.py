"""python3 -m unittest gapfinder.test_wikitext"""

import unittest

from gapfinder.wikitext import passages

PROSE = " ".join(f"The archipelago was surveyed in {1900 + i} and named after the emperor." for i in range(5))
ORDERS = [f"Grand Cross of the Order number {i}, 18 May 1884" for i in range(8)]


class ListPassages(unittest.TestCase):
    def test_list_in_layout_template_is_its_own_passage(self):
        # The English honours of Nicholas II: prose, then the orders inside {{Columns-list}}.
        wiki = (
            "==Honours==\n"
            + PROSE
            + "\n\n'''Foreign'''\n{{Columns-list|colwidth=25em|\n"
            + "\n".join(f"* [[Order {i}|{o}]]" for i, o in enumerate(ORDERS))
            + "\n}}\n"
        )
        texts = [p[2] for p in passages(wiki)]
        self.assertEqual(len(texts), 2, texts)
        self.assertNotIn("Grand Cross", texts[0])
        self.assertTrue(all(o in texts[1] for o in ORDERS), texts[1])
        self.assertTrue(all("\ue002" not in t and "\ue003" not in t for t in texts))

    def test_short_list_stays_with_its_prose(self):
        wiki = "==Life==\n" + PROSE + "\n* one short item\n* another\n\nMore prose follows here."
        texts = [p[2] for p in passages(wiki)]
        self.assertEqual(len(texts), 1, texts)
        self.assertIn("one short item", texts[0])


class Leads(unittest.TestCase):
    # The Swedish lead of Nicholas II opens with a hand-written hatnote and names Russian in English.
    WIKI = (
        ":''För det finländska fartyget, se [[M/S Nikolai II]]''\n{{Regent|namn=Nikolaj II}}\n"
        "'''Nikolaj II''' ({{lang-ru|Николай II}}) var Rysslands siste kejsare. " + PROSE
    )

    def test_hatnote_is_not_lead_text(self):
        lead = passages(self.WIKI, edition="sv")[0][2]
        self.assertTrue(lead.startswith("Nikolaj II"), lead[:80])

    def test_language_name_follows_the_edition(self):
        self.assertIn("(ryska: Николай II)", passages(self.WIKI, edition="sv")[0][2])
        self.assertIn("(Russian: Николай II)", passages(self.WIKI)[0][2])

    def test_indented_italic_line_in_prose_stays(self):
        wiki = "==Verse==\n" + PROSE + "\n:''Vårt land, vårt land''\nMore prose follows here."
        self.assertIn("Vårt land", passages(wiki)[0][2])


if __name__ == "__main__":
    unittest.main()
