from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import deploy_site_to_yandex as deploy


class PublishedFilesTest(unittest.TestCase):
    def test_public_files_only(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            hotel = root / "hotels" / "example"
            hotel.mkdir(parents=True)
            for name in ("index.html", ".env", ".ENV.production", "bot.session",
                         "bot.session-journal", "bot.session-wal", "bot.session-shm",
                         "bot.session.lock"):
                (hotel / name).touch()
            (root / "index.html").touch()
            (hotel / "picture.jpg").symlink_to(hotel / ".env")
            (root / "google-test.html").symlink_to(hotel / ".env")
            (root / "404.html").symlink_to(hotel / ".env")
            (root / "mirror").symlink_to(hotel, target_is_directory=True)
            with patch.object(deploy, "ROOT", root):
                self.assertEqual(set(deploy.collect()), {root / "index.html", hotel / "index.html"})
