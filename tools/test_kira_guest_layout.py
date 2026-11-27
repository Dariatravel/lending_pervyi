import sys
import unittest
import json
from tempfile import TemporaryDirectory
from unittest.mock import patch
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from sync_catalog_from_telegram import render_detail_page
import kira_public_export as export


class GuestPageTest(unittest.TestCase):
    def page(self, slug):
        parsed = {"title": "Тест", "sections": [
            {"label": "Коротко об объекте", "lines": ["Короткий текст"]},
            {"label": "Рядом", "lines": ["Парк"]},
            {"label": "Отель", "lines": ["Описание"]},
        ], "prices": ["4000₽ - июнь"]}
        media = [{"kind": "photo", "source_url": "https://example.org/one.jpg",
                  "category_title": "Домик", "category_badge": "<вид>"},
                 {"kind": "photo", "source_url": "https://example.org/two.jpg"}]
        conditions = dict.fromkeys(export.PUBLIC_CONDITIONS)
        conditions["Заезд с"] = "14"
        sample = dict(hotel_id=export.HOTEL, slug=export.SLUG, guest_title=None, guest_address=None,
                      guest_description=None, guest_nearby=None, media=[], groups=[], conditions=conditions, prices=None)
        with TemporaryDirectory() as folder:
            snapshot = Path(folder, "sample.json")
            snapshot.write_text(json.dumps(sample))
            with patch.object(export, "SNAPSHOT", snapshot):
                return BeautifulSoup(render_detail_page("hotel", slug, "", "", parsed, media,
                                                     "/hotels/" + slug + "/"), "html.parser")

    def test_working_template_order_and_public_fields(self):
        soup = self.page("kira-gostevoy-kompleks-2725")
        main = soup.select_one(".hotel-site-concept__detail-main")
        self.assertEqual([el.text.strip() for el in main.select("h2")],
                         ["Об объекте", "Фото и видео", "Отель", "✔️ Рядом", "✔️ВАЖНО:"])
        self.assertEqual(main.select_one(".media-group-badge").text, "<вид>")
        self.assertEqual(len(main.select(".media-group-card")), 2)
        self.assertEqual(len(main.select(".media-grid img")), 2)
        self.assertTrue(soup.select_one("#prices + .guest-conditions"))
        self.assertIn("14:00", soup.select_one(".guest-conditions").text)
        self.assertIn("4000", soup.select_one("#prices").text)

    def test_other_objects_keep_original_layout(self):
        soup = self.page("drugoy-obekt")
        self.assertIsNone(soup.select_one(".guest-conditions, .media-group-frame"))
        self.assertEqual(len(soup.select(".media-grid img")), 2)
