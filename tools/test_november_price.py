from datetime import date
import json
import unittest

from build_min_prices import SNAPSHOT_PATH, monthly_min_prices


class NovemberPriceTests(unittest.TestCase):
    def test_prices_in_catalog_on_review_date(self):
        listings = {h["slug"]: h for h in json.loads(SNAPSHOT_PATH.read_text())["listings"]}
        expected = {
            "zhasmin-mini-otel-3736": 1700,
            "morskaya-laguna-gostinitsa-s-zavtrakami-3418": None,
            "flamingo-gostevoy-dom-5018": None,
            "boho-kompleks-polnogo-schastya-u-morya-4783": None,
        }
        for slug, value in expected.items():
            with self.subTest(slug=slug):
                prices = listings[slug]["details"]["prices"]
                self.assertEqual(monthly_min_prices(prices, date(2026, 11, 25)).get(11), value)
