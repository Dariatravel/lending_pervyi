import json
import sys
import unittest
from pathlib import Path
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import kira_public_export as export


class GalleryV2Test(unittest.TestCase):
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
