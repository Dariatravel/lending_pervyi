"""Проверка: повторный импорт не меняет редакционную статью."""
import asyncio
import hashlib
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_blog_posts_batch as batch
import sync_blog_from_abhazbereg as sync
from blog_editorial_policy import protected_article, protected_source


class EditorialProtectionTest(unittest.TestCase):
    def test_legacy_batch_preserves_article(self):
        article = next(a for a in batch.ARTICLES if a['id'] == 3613)
        page = ROOT / 'blog' / article['slug'] / 'index.html'
        before = hashlib.sha256(page.read_bytes()).hexdigest()
        # Несуществующий исходник: защищённый пост даже не должен читаться.
        article = dict(article, src=ROOT / 'missing-editorial-source.txt')
        with patch.object(batch, 'ARTICLES', [article]):
            batch.main()
        self.assertEqual(before, hashlib.sha256(page.read_bytes()).hexdigest())

    def test_explicit_sync_skips_before_telegram(self):
        with patch.object(sync, 'connected_telegram_client', side_effect=AssertionError('Telegram не нужен')):
            self.assertEqual(asyncio.run(sync.sync_posts([3613])), [])

    def test_auto_article_not_blocked(self):
        self.assertFalse(protected_article('ldzaa-shtil-pitsunda-volny'))
        self.assertFalse(protected_source('abhazbereg', 2422))
        self.assertTrue(protected_source('abhazbooking', 3613))
        self.assertFalse(protected_source('another-channel', 3613))

    def test_full_sync_preserves_manual_cards(self):
        with patch.dict(sync.os.environ, {'TARGET_BLOG_POST_IDS': '', 'SKIP_BLOG_INDEX': ''}), \
                patch.object(sync, 'sync_posts', new=AsyncMock(return_value=[])), \
                patch.object(sync, 'render_blog_index', return_value='html') as render, \
                patch.object(sync, 'update_sitemap'), \
                patch('build_blog_posts_manifest.main'), \
                patch.object(Path, 'write_text'):
            self.assertEqual(asyncio.run(sync.main_async()), 0)
        slugs = {card['slug'] for card in render.call_args.args[0]}
        self.assertIn('prava-i-shtrafy-avto-abhaziya', slugs)
        self.assertIn('kak-vybrat-kurort-abkhaziya-pervyy-raz', slugs)


if __name__ == '__main__':
    unittest.main()
