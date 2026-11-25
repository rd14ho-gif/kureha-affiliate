import unittest
from datetime import datetime

from pipeline.normalize import JST, crop_year, parse_weight_kg


class TestWeight(unittest.TestCase):
    def test_simple(self):
        self.assertEqual(parse_weight_kg("新潟県産コシヒカリ 5kg 送料無料"), 5)
        self.assertEqual(parse_weight_kg("あきたこまち １０ｋｇ"), 10)
        self.assertEqual(parse_weight_kg("ゆめぴりか 5キロ"), 5)

    def test_multiply(self):
        self.assertEqual(parse_weight_kg("ひとめぼれ 5kg×2袋"), 10)
        self.assertEqual(parse_weight_kg("ひとめぼれ 10kg（5kg×2袋）"), 10)
        self.assertEqual(parse_weight_kg("精米 2kg×3袋 計6kg"), 6)
        self.assertEqual(parse_weight_kg("お米 500g×4袋"), 2)

    def test_ambiguous(self):
        self.assertIsNone(parse_weight_kg("コシヒカリ 5kg/10kg 選べる"))
        self.assertIsNone(parse_weight_kg("コシヒカリ 10kg（5kg×3袋）"))
        self.assertIsNone(parse_weight_kg("コシヒカリ 新米"))


class TestYear(unittest.TestCase):
    def test_year(self):
        now = datetime(2026, 11, 25, tzinfo=JST)
        self.assertEqual(crop_year("令和8年産 コシヒカリ", now), 2026)
        self.assertEqual(crop_year("R7年産 つや姫", now), 2025)
        self.assertEqual(crop_year("2026年産 ゆめぴりか", now), 2026)
        self.assertIsNone(crop_year("コシヒカリ", now))


if __name__ == "__main__":
    unittest.main()
