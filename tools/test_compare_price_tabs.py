"""Регрессии сравнения цен: альтернативы питания, границы дат, размер коттеджа."""
import datetime as dt
import unittest
from unittest.mock import patch
import tempfile
from pathlib import Path
import compare_price_tabs as c


class PriceComparisonTests(unittest.TestCase):
    def test_all_manon_pairs_share_date_boundary(self):
        days = c.daterange_days(12, 1, 12, 31)
        for a, b in [(4200, 5600), (4900, 6300), (5900, 7300), (7900, 9300)]:
            with self.subTest(price=a):
                series, _, loose = c.parse_manual_cell(f'{a}/{b} до 27', days, True)
                self.assertEqual(series[dt.date(2026, 12, 1)], (a, b))
                self.assertEqual(series[dt.date(2026, 12, 27)], (a, b))
                self.assertNotIn(dt.date(2026, 12, 28), series)
                self.assertFalse(loose)

    def test_meals_without_boundary(self):
        days = c.daterange_days(11, 1, 11, 30)
        series, _, _ = c.parse_manual_cell('4200/5600', days, True)
        self.assertEqual(len(series), 30)
        self.assertEqual(set(series.values()), {(4200, 5600)})

    def test_meals_from_boundary(self):
        series, _, _ = c.parse_manual_cell('4200/5600 с 16', c.daterange_days(12, 1, 12, 31), True)
        self.assertNotIn(dt.date(2026, 12, 15), series)
        self.assertEqual(series[dt.date(2026, 12, 16)], (4200, 5600))

    def test_regular_date_change_still_works(self):
        series, _, _ = c.parse_manual_cell('5000 до 15 / 3000 с 16', c.daterange_days(12, 1, 12, 31), True)
        self.assertEqual(series[dt.date(2026, 12, 15)], 5000)
        self.assertEqual(series[dt.date(2026, 12, 16)], 3000)

    def test_cottage_sizes(self):
        title = '"ЦАРСКОЕ СЕЛО АНХУА" коттеджи'
        cats = ['коттеджи малые', 'коттедж большой (40 кв.м)']
        for name, expected in [('коттеджи малые', cats[0]), ('коттедж большой', cats[1])]:
            self.assertEqual(c.match_category('Царское село Анхуа (каждое доп место 500р) ' + name, title, cats), (expected, True))
        self.assertEqual(c.match_category('Царское село Анхуа коттеджи', title, ['коттеджи малые', 'коттеджи большие']), (None, False))
        self.assertEqual(c.match_category('Царское село Анхуа коттедж малый', title, [cats[1]]), (None, False))

    def test_report_accepts_either_meal_price_but_flags_other_price(self):
        def row(num, values):
            return {'row': num, 'hidden': False, 'cells': [{'formattedValue': x} for x in values]}
        title = '"МАНОН" отель'
        auto = {'rows': [row(1, []), row(2, []),
                         row(3, [title, '', 'стандарт', '', '1 декабря — 27 декабря', '4200'])]}
        manual_row = ['Манон стандарт без завтрака/с завтраком'] + [''] * 16 + ['4200/5600 до 27']
        manual = {'rows': [row(1, []), row(330, manual_row)]}
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / 'report.txt'
            with patch('sys.argv', ['compare', '--from-date', '2026-12-01']), \
                 patch('google.oauth2.service_account.Credentials.from_service_account_file'), \
                 patch('googleapiclient.discovery.build'), \
                 patch.object(c, 'pick_google_credentials_path', return_value=Path('unused')), \
                 patch.object(c, 'fetch_tab', side_effect=lambda _, tab: auto if tab == c.AUTO_TAB else manual), \
                 patch.object(c, 'REPORT_PATH', report), \
                 patch.object(c, 'SNAPSHOT_PATH', Path(tmp) / 'absent.json'):
                for price in ['4200', '5600', '6000']:
                    with self.subTest(auto=price):
                        auto['rows'][2]['cells'][5]['formattedValue'] = price
                        self.assertEqual(c.main(), 0)
                        result = report.read_text()
                        expected = 1 if price == '6000' else 0
                        self.assertIn(f'С расхождениями цен: {expected} строк', result)
                        if expected:
                            self.assertIn('ручная 4200/5600 ₽, авто 6000 ₽', result)


if __name__ == '__main__':
    unittest.main()
