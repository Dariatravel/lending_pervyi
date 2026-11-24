"""Проверки безопасного публичного снимка динамических цен Геги."""
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from export_gega_live_prices import build_snapshot


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 24, 15, tzinfo=timezone.utc)
        self.entities = [{'name': 'Категория ' + str(i)} for i in range(9)]
        self.rates = [{'id': 'winter', 'name': 'Межсезонье'}]
        self.rows = [{'night': '2026-11-24', 'checked_at': self.now.isoformat(), 'categories': [
            {'category': e['name'], 'available': 1,
             'tariffs': [{'rate': 'winter', 'price': 2800.50, 'deposit': 840, 'penalty': 840}]}
            for e in self.entities]}]

    def snapshot(self):
        return build_snapshot(self.rows, self.entities, self.rates, self.now)

    def test_prices_occupancy_and_privacy(self):
        result = self.snapshot()
        self.assertEqual(result['adults'], 2)
        self.assertEqual(result['children'], 0)
        categories = result['nights']['2026-11-24']['categories']
        self.assertEqual(len(categories), 9)
        self.assertEqual(categories[0]['tariffs'][0]['price'], 2800.50)
        self.assertEqual(set(categories[0]['tariffs'][0]), {'name', 'price', 'meal'})
        self.assertIn('уточнит', categories[0]['tariffs'][0]['meal'])

    def test_stale_and_future_timestamps_are_rejected(self):
        for delta in (timedelta(hours=-3), timedelta(seconds=1)):
            self.rows[0]['checked_at'] = (self.now + delta).isoformat()
            with self.assertRaises(ValueError): self.snapshot()

    def test_unknown_category_or_rate_is_rejected(self):
        original = deepcopy(self.rows)
        for field, value in [('category', 'Чужой отель'), ('tariffs', [{'rate': 'unknown', 'price': 5000}])]:
            self.rows = deepcopy(original)
            self.rows[0]['categories'][0][field] = value
            with self.assertRaises(ValueError): self.snapshot()

    def test_duplicate_category_is_rejected(self):
        self.rows[0]['categories'][1]['category'] = self.rows[0]['categories'][0]['category']
        with self.assertRaises(ValueError): self.snapshot()

    def test_invalid_prices_rejected_including_nan(self):
        for price in (-1, 0, float('nan'), float('inf'), True, '2800'):
            self.rows[0]['categories'][0]['tariffs'][0]['price'] = price
            with self.assertRaises(ValueError): self.snapshot()

    def test_moscow_date_rollover(self):
        self.now = datetime(2026, 11, 24, 22, tzinfo=timezone.utc)
        self.rows[0]['checked_at'] = self.now.isoformat()
        with self.assertRaises(ValueError): self.snapshot()

    def test_null_prices_not_converted_to_zero(self):
        self.rows[0]['categories'][0]['tariffs'][0]['price'] = None
        self.assertEqual(self.snapshot()['nights']['2026-11-24']['categories'][0]['tariffs'], [])

    def test_short_fractional_timestamp_from_database(self):
        self.rows[0]['checked_at'] = '2026-11-24T14:59:59.94+00:00'
        self.assertIn('2026-11-24', self.snapshot()['nights'])


if __name__ == '__main__':
    unittest.main()
