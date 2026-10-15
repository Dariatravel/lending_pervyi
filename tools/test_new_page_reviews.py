#!/usr/bin/env python3
"""Новые карточки не должны получать отзывы от посторонних объектов."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import sync_catalog_from_telegram as catalog


class NewPageReviewsTest(unittest.TestCase):
    def test_no_confirmed_reviews_means_no_generic_reviews(self):
        for bank in ({}, {'other-object': []}):
            with self.subTest(bank=bank), \
                 patch.object(catalog, '_reviews_for_slug', return_value=[]), \
                 patch.object(catalog, '_load_ocr_review_bank', return_value=bank), \
                 patch.object(catalog, '_existing_reviews_panel', return_value=''), \
                 patch.object(catalog, 'pick_guest_reviews_for_slug') as generic:
                self.assertEqual(catalog._reviews_panel_for_slug(None, 'new-house', '/hotels/new-house/'), '')
                generic.assert_not_called()

    def test_existing_reviews_survive_when_bank_is_unavailable(self):
        panel = '<section class="reviews-panel">Отзывы объекта</section>'
        with patch.object(catalog, '_reviews_for_slug', return_value=[]), \
             patch.object(catalog, '_load_ocr_review_bank', return_value={}), \
             patch.object(catalog, '_existing_reviews_panel', return_value=panel):
            self.assertEqual(catalog._reviews_panel_for_slug(None, 'old-house', '/hotels/old-house/'), panel)

    def test_confirmed_object_reviews_appear_on_new_page(self):
        with patch.object(catalog, '_reviews_for_slug', return_value=[{'name': 'Гость', 'text': 'Подтверждённый отзыв'}]), \
             patch.object(catalog, '_clean_ocr_review_text', side_effect=lambda text: text):
            self.assertIn('Подтверждённый отзыв', catalog._reviews_panel_for_slug(None, 'new-house', '/hotels/new-house/'))


if __name__ == '__main__':
    unittest.main()
