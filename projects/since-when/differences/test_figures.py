"""Tests for figures.py.

    python -m unittest differences.test_figures
"""
import unittest

from .figures import compatible, read


class Counts(unittest.TestCase):
    def test_two_exact_figures_agree_only_when_equal(self):
        self.assertTrue(compatible("3 500 miestä", "3,500 men"))
        self.assertFalse(compatible("1 000 man", "1,100 Swedes"))
        self.assertFalse(compatible("102", "about 50"))

    def test_about_agrees_with_what_rounds_to_it(self):
        self.assertTrue(compatible("about 5,000", "4,900"))
        self.assertFalse(compatible("about 5,000", "5,600"))
        self.assertFalse(compatible("omkring 12 000", "12,600"))
        self.assertFalse(compatible("noin 8000", "7 000"))
        self.assertTrue(compatible("n. 70", "72"))
        self.assertTrue(compatible("ca 17 000", "about 17,400"))

    def test_over_and_almost(self):
        self.assertTrue(compatible("over 400 ships", "430"))
        self.assertFalse(compatible("more than 400", "520"))
        self.assertFalse(compatible("yli 400", "380"))
        self.assertTrue(compatible("nästan 7 000", "6 800"))
        self.assertFalse(compatible("almost 7,000", "6,000"))

    def test_a_range_agrees_with_what_lies_in_it(self):
        self.assertTrue(compatible("5–10%", "8 %"))
        self.assertFalse(compatible("5–10%", "12%"))

    def test_what_cannot_be_read_is_left_to_the_model(self):
        self.assertIsNone(compatible("some two thousand", "3 000"))
        self.assertIsNone(compatible("1,5 miljoonaa", "1 500 000"))
        self.assertIsNone(compatible("12 000", "7 July 1930"))
        self.assertIsNone(compatible("", "12 000"))
        self.assertIsNone(compatible("8%", "8"))


class Dates(unittest.TestCase):
    def test_the_same_day_in_three_languages(self):
        self.assertTrue(compatible("21. marraskuuta 1932", "21 November 1932"))
        self.assertTrue(compatible("den 21 november", "November 21st, 1932"))
        self.assertFalse(compatible("12. huhtikuuta", "April 14th"))
        self.assertFalse(compatible("12 maj 1920", "12 June 1920"))

    def test_a_coarser_date_agrees_with_a_finer_one(self):
        self.assertTrue(compatible("toukokuun alussa 1920", "6 May 1920"))
        self.assertTrue(compatible("1920", "6 May 1920"))
        self.assertFalse(compatible("May 1921", "6 May 1920"))
        self.assertFalse(compatible("1921", "1920"))

    def test_two_calendars_agree_when_one_day_matches(self):
        self.assertEqual(read("12. huhtikuuta (J: 31. maaliskuuta)")[1]["day"], {12, 31})
        self.assertTrue(compatible("the 2nd/14th day of April", "14 April"))
        self.assertFalse(compatible("the 2nd/14th day of April", "16 April"))


if __name__ == "__main__":
    unittest.main()
