import copy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import kira_public_export as k


class SnapshotTest(unittest.TestCase):
    def setUp(self):
        self.page = k.PAGE.read_text()
        self.soup = BeautifulSoup(self.page, "html.parser")
        keys = [k.media_key(item) for item in self.soup.select(".media-group-card img")][:2]
        self.rows = [dict(id="ab000000-0000-4000-8000-00000000000" + str(i),
                          key=key, kind="photo", group=name)
                     for i, (key, name) in enumerate(zip(keys, ["Домик", "Территория"]))]
        self.data = dict(hotel_id=k.HOTEL, slug=k.SLUG, media=self.rows[::-1], prices=None,
                         conditions={field: None for field in k.PUBLIC_CONDITIONS},
                         groups=[dict(title="Территория", badge="<Обзор>"), dict(title="Домик", badge="")])

    def test_order_matched_files_and_keep_prices_and_media(self):
        result = k.apply_snapshot(self.page, self.data)
        soup = BeautifulSoup(result, "html.parser")
        self.assertEqual(str(soup.select_one("#prices")), str(self.soup.select_one("#prices")))
        self.assertCountEqual([i["src"] for i in soup.select("img")], [i["src"] for i in self.soup.select("img")])
        self.assertEqual([i.text for i in soup.select(".media-group-card h3")], ["Территория", "Домик"])
        self.assertEqual(soup.select_one(".media-group-card img")["data-crm-media-id"], self.rows[1]["id"])
        self.assertIn("&lt;Обзор&gt;", result)
        self.assertEqual(k.apply_snapshot(result, self.data), result)
        self.assertTrue(soup.select_one(".guest-conditions").has_attr("hidden"))

    def test_manual_price_projects_current_version_only(self):
        self.data["prices"] = dict(description="Цена за дом", groups=[dict(title="Домик", note="Двое",
            mode="rows", freeText="", rows=[dict(amount="777", period="июнь", note="")])])
        soup = BeautifulSoup(k.apply_snapshot(self.page, self.data), "html.parser")
        self.assertIn("777₽ - июнь", soup.select_one("#prices").get_text())
        self.assertEqual(len(soup.select("#prices")), 1)
        self.data["prices"]["history"] = []
        with self.assertRaises(ValueError):
            k.apply_snapshot(self.page, self.data)

    def test_private_or_other_hotel_never_replaces_published_files(self):
        for invalid in (dict(hotel_id="other"), dict(slug="other"), dict(reviews=[]), dict(media=[{
                **self.rows[0], "key": "media/hotels/other/photo-01.jpg"}])):
            with self.assertRaises(ValueError):
                k.apply_snapshot(self.page, {**self.data, **invalid})
        unknown = copy.deepcopy(self.rows[0])
        unknown["key"] = "media/hotels/" + k.SLUG + "/new.jpg"
        new_page = BeautifulSoup(k.apply_snapshot(self.page, {**self.data, "media":[unknown]}), "html.parser")
        self.assertNotIn("new.jpg", str(new_page.select_one(".media-group-frame")))

    def test_failed_fetch_does_not_replace_last_snapshot_or_html(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot, page = (Path(directory) / name for name in ("snapshot", "html"))
            snapshot.write_text("прежние тарифы")
            page.write_text("прежняя страница")
            with patch.object(k, "SNAPSHOT", snapshot), patch.object(k, "PAGE", page), \
                    patch.object(k, "urlopen", side_effect=TimeoutError), patch.object(sys, "argv", ["export", "--apply"]):
                with self.assertRaises(TimeoutError):
                    k.main()
            self.assertEqual(snapshot.read_text(), "прежние тарифы")
            self.assertEqual(page.read_text(), "прежняя страница")
