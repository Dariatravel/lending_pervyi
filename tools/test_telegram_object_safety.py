"""Регрессия Семейной: ссылки в подвале и пропуск объекта в полном синке."""
import asyncio
from datetime import datetime, timezone
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]
import sync_catalog_from_telegram as sync
import watch_telegram_updates as watch
from telegram_object_text import is_service_text, SERVICE_MARKERS

TEXT = '''"СЕМЕЙНАЯ" квартира 2к
📍Гагра, ул. Абазгаа, 49/2, 1 этаж
🏖 5 минут пешком до пляжа
👥 Размещение до 6 человек
✔️ЦЕНЫ:
4000₽ – ноябрь
Кто я и почему выгодно бронировать со мной: t.me/abhazbooking/547
Отзывы гостей: t.me/abhazbooking/476'''


class ObjectTextTests(unittest.TestCase):
    def test_semeynaya_footer_does_not_hide_real_object(self):
        self.assertFalse(is_service_text(TEXT))
        self.assertTrue(sync.is_kvartira_object_message(TEXT))
        self.assertTrue(watch.is_kvartira_object_message(TEXT))
        self.assertGreater(sync.topic_message_score(TEXT), 0)
        self.assertGreater(watch.topic_message_score(TEXT), 0)

    def test_hotel_with_shared_footer_is_object_too(self):
        text = TEXT.replace('"СЕМЕЙНАЯ" квартира 2к', '"ПРИМЕР" отель')
        self.assertTrue(sync.is_hotel_object_message(text))
        self.assertTrue(watch.is_hotel_object_message(text))

    def test_service_posts_stay_service(self):
        for marker in SERVICE_MARKERS:
            with self.subTest(marker=marker):
                self.assertTrue(is_service_text(marker))
                self.assertFalse(sync.is_kvartira_object_message(marker))
                self.assertFalse(watch.is_kvartira_object_message(marker))

    def test_service_heading_not_mistaken_for_listing_with_emoji(self):
        text = 'Отзывы гостей\n📍Гагра\n👥 Обсуждаем поездку'
        self.assertTrue(is_service_text(text))
        self.assertFalse(sync.is_kvartira_object_message(text))

    def test_unknown_service_heading_remains_service_without_housing_markers(self):
        self.assertTrue(is_service_text('Полезные ссылки\nОтзывы гостей: ссылка'))
        self.assertFalse(is_service_text(''))

    def test_service_heading_whitespace_and_entities_are_normalized(self):
        for heading in ('Отзывы\u00a0гостей', 'Отзывы  гостей', 'Отзывы&nbsp;гостей',
                        'Отзывы\tгостей', 'Отзывы&#32;гостей'):
            with self.subTest(heading=heading):
                text = heading + '\n📍Гагра\n👥 Обсуждение'
                self.assertTrue(is_service_text(text))
                self.assertFalse(sync.is_kvartira_object_message(text))
                self.assertFalse(watch.is_kvartira_object_message(text))

    def test_listing_footer_whitespace_does_not_hide_it(self):
        text = TEXT.replace('Отзывы гостей', 'Отзывы&nbsp;гостей').replace('Кто я', 'Кто\u00a0я')
        self.assertFalse(is_service_text(text))
        self.assertTrue(sync.is_kvartira_object_message(text))
        self.assertTrue(watch.is_kvartira_object_message(text))

    def test_full_discovery_includes_semeynaya_and_album(self):
        message = SimpleNamespace(id=1104, message=TEXT, grouped_id=10,
                                  media=object(), date=datetime(2026, 2, 3, tzinfo=timezone.utc))
        photo = SimpleNamespace(id=1105, message='', grouped_id=10, media=object())
        topic = SimpleNamespace(id=1103, title='СЕМЕЙНАЯ', top_message=1392)
        class Client:
            async def get_entity(self, name): return name
            async def __call__(self, request):
                return SimpleNamespace(topics=[topic])
        with patch.object(sync, 'TARGET_KV_TOPIC_IDS', set()), \
             patch.object(sync, 'fetch_topic_messages', AsyncMock(return_value=[message, photo])):
            objects, topics = asyncio.run(sync.build_kvartira_objects(Client()))
        self.assertEqual(len(objects), 1)
        self.assertEqual(objects[0]['canonical'].id, 1104)
        self.assertEqual(objects[0]['topic_id'], 1103)
        self.assertEqual([m.id for m in objects[0]['media_messages']], [1104, 1105])
        self.assertEqual(topics[0]['topic_id'], 1103)


class MissingObjectTests(unittest.TestCase):
    def setUp(self):
        self.row = {'id': 1164, 'slug': 'semeynaya-kvartira-2k-1104'}

    def test_empty_or_partial_telegram_response_cannot_remove_card(self):
        with patch.object(sync, 'load_hidden_slugs', return_value=set()), \
             patch.object(sync, 'cleanup_removed_listing') as remove:
            self.assertEqual(sync.cleanup_unprocessed_kvartira([self.row], set(), set(), None), (0, 1))
        remove.assert_not_called()

    def test_explicitly_hidden_object_is_still_removed(self):
        with patch.object(sync, 'load_hidden_slugs', return_value={self.row['slug']}), \
             patch.object(sync, 'cleanup_removed_listing') as remove:
            self.assertEqual(sync.cleanup_unprocessed_kvartira([self.row], set(), set(), None), (1, 0))
        remove.assert_called_once_with('kvartira', self.row, None)

    def test_processed_and_failed_objects_not_touched(self):
        for processed, failed in [({1164}, set()), (set(), {1164})]:
            with patch.object(sync, 'load_hidden_slugs', return_value=set()), \
                 patch.object(sync, 'cleanup_removed_listing') as remove:
                self.assertEqual(sync.cleanup_unprocessed_kvartira([self.row], processed, failed, None), (0, 0))
            remove.assert_not_called()


if __name__ == '__main__':
    unittest.main()
