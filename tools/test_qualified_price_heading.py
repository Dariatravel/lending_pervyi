from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import apply_telegram_detail_sections as writer


class QualifiedHeadingTest(unittest.TestCase):
    def render_prices(self, post):
        with TemporaryDirectory() as directory:
            page = Path(directory) / "index.html"
            page.write_text('<main><div class="hotel-site-concept__detail-main"></div>'
                            '<ul class="price-card__seasons"><li>Прежняя цена</li></ul></main>')
            with patch.object(writer, "fetch_og_description", return_value=post):
                writer.apply_to_page(page, "example", 1, dry_run=False)
            return [li.get_text() for li in BeautifulSoup(page.read_text(), "html.parser").select("li")]

    def test_keeps_terms_and_all_tariffs_in_order(self):
        post = ("✔️Цены (при двухместном размещении):\n3500 ₽\n"
                "✔ЦЕНЫ (на троих)\n4500 ₽\n✔️УСЛОВИЯ:\nТишина после 23")
        self.assertEqual(self.render_prices(post),
                         ["(при двухместном размещении)", "3500 ₽", "(на троих)", "4500 ₽"])

    def test_empty_price_section_leaves_previous_prices(self):
        self.assertEqual(self.render_prices("✔️Цены (на двоих):\n+70001002030"), ["Прежняя цена"])

    def test_optional_marker_and_repeated_note(self):
        for marker in ("", "✅", "☑️"):
            with self.subTest(marker=marker):
                post = marker + "Цены (на двоих):\n(на двоих)\n3500 ₽"
                self.assertEqual(self.render_prices(post), ["(на двоих)", "3500 ₽"])

    def test_simple_price_heading(self):
        self.assertEqual(self.render_prices("✔️ЦЕНЫ:\n3500 ₽"), ["3500 ₽"])
