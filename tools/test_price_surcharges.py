from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.apply_telegram_detail_sections import price_lines_from_block
from sync_abhazbooking_2026 import parse_post


class SurchargeTest(unittest.TestCase):
    def test_prices_survive_and_contact_is_excluded(self):
        prices = ["Июнь 4000 ₽", "Завтрак +700", "Июль 4500 ₽"]
        for phone in ("+70001002030", "+7 (000) 100-20-30"):
            with self.subTest(phone=phone):
                block = "\n".join([*prices, phone])
                self.assertEqual(price_lines_from_block(block + "\nКонтакты"), prices)
                post = "ТЕСТ\n📍 Гагра\n✔️ЦЕНЫ:\n" + block
                self.assertEqual([row["text"] for row in parse_post(post)["prices"]], prices)
