import json
import sys
import unittest
from tempfile import TemporaryDirectory
from unittest.mock import patch
from pathlib import Path
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import kira_public_export as export


class GalleryV2Test(unittest.TestCase):
    def test_hourly_catalog_rebuild_preserves_crm_gallery_and_description(self):
        import rebuild_from_supabase as rebuild
        with TemporaryDirectory() as folder:
            path = Path(folder, "index.html")
            path.write_text(export.PAGE.read_text())
            with patch.object(rebuild, "resolve_site_page_path", return_value=path), \
                 patch.object(rebuild, "render_media_grid", return_value='<img src="stale.jpg">'):
                rebuild.update_hotel_page(dict(slug=export.SLUG, title="Кира", details={}))
            soup = BeautifulSoup(path.read_text(), "html.parser")
            data = json.loads(export.SNAPSHOT.read_text())
            self.assertEqual(len(soup.select(".media-group-frame [data-crm-media-id]")),len(data["media"]))
            self.assertIsNotNone(soup.select_one("[data-static-important]"))
            self.assertNotIn("stale.jpg",str(soup.select_one(".media-group-frame")))

    def test_rebuild_from_legacy_and_crm_files(self):
        data = json.loads(export.SNAPSHOT.read_text())
        data["conditions"]["Уборка"] = "Раз в неделю"
        data.update(guest_summary="Тихий двор", guest_highlights="Балкон", groups=[{"title":"Номера", "badge":"Внутри"}])
        def photo(uid, name):
            return dict(id=uid, kind="photo", key=f"media/photobank/{export.HOTEL}/large/{name}.jpg", group="Номера")
        old_id = next(iter(export.ORIGINAL_MEDIA))
        new_id = "791cc692-1018-412a-9201-e51a4450cf64"
        data["media"] = [photo(new_id,"new"), photo(old_id,"existing")]
        page = export.apply_snapshot(export.PAGE.read_text(), data)
        soup = BeautifulSoup(page, "html.parser")
        files = soup.select(".media-group-frame img")
        self.assertEqual([i["data-crm-media-id"] for i in files], [new_id, old_id])
        self.assertTrue(files[0]["src"].endswith("/large/new.jpg"))
        self.assertTrue(files[1]["src"].endswith("/photo-01.jpg"))
        self.assertEqual(soup.select_one(".media-group-card h3").find_previous_sibling().text,"Внутри")
        self.assertEqual(soup.select_one("[data-crm-summary] p").text,"Тихий двор")
        self.assertIn("Балкон",soup.select_one(".benefit-grid").get_text())
        self.assertEqual(page,export.apply_snapshot(page,data))
        data["media"][0]["group"] = "Номер, цена за троих"
        data["groups"] = []
        fallback = BeautifulSoup(export.apply_snapshot(page, data), "html.parser")
        self.assertEqual([b.text for b in fallback.select(".media-group-badge")], ["Обзор номера"])
        self.assertEqual(fallback.find("h3", string="Номер").find_previous_sibling().text, "Обзор номера")
        data["groups"] = [dict(title="Номер, цена за троих",badge="Внутри номера")]
        manual = BeautifulSoup(export.apply_snapshot(page, data), "html.parser")
        self.assertEqual([b.text for b in manual.select(".media-group-badge")], ["Внутри номера"])

    def test_regeneration_replaces_generated_summary_and_clears_stale_nearby(self):
        data = json.loads(export.SNAPSHOT.read_text())
        data["conditions"]["Уборка"] = None
        data.update(guest_summary="Новая сводка", guest_highlights=None, guest_nearby=None,
                    media=[], groups=[])
        source = export.PAGE.read_text().replace('<section class="section hotel-media-section',
            '<section class="section hotel-site-concept__detail-section"><article><h2>Об объекте</h2>'
            '<div class="paragraph-blocks">Старое</div></article></section>'
            '<section class="section hotel-media-section', 1)
        page = export.apply_snapshot(source, data)
        soup = BeautifulSoup(page, "html.parser")
        self.assertEqual(len(soup.find_all("h2", string="Об объекте")), 1)
        self.assertNotIn("Старое", soup.select_one(".hotel-site-concept__detail-main").text)
        self.assertFalse(any("рядом" == h.get_text(strip=True).strip("✔️: ").casefold() for h in soup.select("h2")))
