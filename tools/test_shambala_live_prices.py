"""Соответствие тарифов, питания и категорий, устойчивость пересборки Шамбалы."""
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys
import unittest

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from export_shambala_live_prices import build_snapshot, ROOMS, MEALS
from shambala_prices import apply_to_page_html, SLUG
from supplemental_store import apply_to_page_html as supplemental
from sync_prices_from_telegram import replace_prices_block


class ShambalaTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026,11,24,17,tzinfo=timezone.utc)
        self.hotel = {'code': '64223', 'room_types': [
            {'code': code, 'name': name, 'max_adult_occupancy': 2} for code,name in ROOMS.items()],
            'rate_plans': [{'code': code, 'name': values[0]} for code,values in MEALS.items()] +
                          [{'code': '993994', 'name': 'Базовый тариф'}]}
        self.rows = [{'night':'2026-11-24', 'checked_at': self.now.isoformat(), 'categories':[
            {'category': name, 'available': 2, 'tariffs':[
                {'rate':'Раннее бронирование без питания','price':9900},
                {'rate':'Базовый с завтраком','price':13400},
                {'rate':'Базовый тариф','price':11000}]} for name in ROOMS.values()]}]

    def snapshot(self):
        return build_snapshot(self.rows, self.hotel, self.now)

    def test_exact_prices_and_meals_no_guesses(self):
        result = self.snapshot()
        self.assertEqual((result['hotel'],result['adults'],result['children']),('shambala',2,0))
        tariffs = result['nights']['2026-11-24']['categories'][0]['tariffs']
        self.assertEqual([(r['price'],r['meal']) for r in tariffs],
                         [(9900,'Без питания'),(13400,'Завтрак включён'),(11000,'Питание уточняется')])
        self.assertEqual(len(result['nights']['2026-11-24']['categories']),9)

    def test_changed_room_code_or_name_and_foreign_hotel_rejected(self):
        original = deepcopy(self.hotel)
        for key,value in [('code','foreign'),('name','Другой люкс')]:
            self.hotel = deepcopy(original);self.hotel['room_types'][0][key] = value
            with self.assertRaises(ValueError): self.snapshot()
        self.hotel = deepcopy(original); self.hotel['code'] = 'other'
        with self.assertRaises(ValueError): self.snapshot()

    def test_changed_meal_name_is_not_mislabeled(self):
        self.hotel['rate_plans'][0]['name'] = 'Без завтрака'
        with self.assertRaises(ValueError): self.snapshot()

    def test_new_tariff_meal_is_not_guessed(self):
        self.hotel['rate_plans'].append({'code':'new','name':'Новый тариф'})
        self.rows[0]['categories'][0]['tariffs'] = [{'rate':'Новый тариф','price':5000}]
        t = self.snapshot()['nights']['2026-11-24']['categories'][0]['tariffs'][0]
        self.assertEqual(t['meal'],'Питание уточняется')

    def test_old_prices_unknown_category_and_unknown_rate_rejected(self):
        original = deepcopy(self.rows)
        self.rows[0]['checked_at'] = (self.now-timedelta(hours=3)).isoformat()
        with self.assertRaises(ValueError): self.snapshot()
        self.rows = deepcopy(original);self.rows[0]['categories'][0]['category'] = 'Афрейм'
        with self.assertRaises(ValueError): self.snapshot()
        self.rows = deepcopy(original);self.rows[0]['categories'][0]['tariffs'][0]['rate'] = 'missing'
        with self.assertRaises(ValueError): self.snapshot()

    def test_public_snapshot_has_no_payment_or_client_fields(self):
        self.rows[0]['categories'][0]['tariffs'][0].update(deposit=999,secret='x',guest_phone='y')
        tariff = self.snapshot()['nights']['2026-11-24']['categories'][0]['tariffs'][0]
        self.assertEqual(set(tariff),{'name','price','meal'})

    def test_render_idempotence_sources_and_media_unchanged(self):
        original = (ROOT/'hotels'/SLUG/'index.html').read_text()
        result = apply_to_page_html(original,SLUG)
        self.assertEqual(apply_to_page_html(result,SLUG),result)
        a,b=BeautifulSoup(original,'html.parser'),BeautifulSoup(result,'html.parser')
        self.assertEqual([li.get_text() for li in a.select('#prices .price-card__seasons li')],
                         [li.get_text() for li in b.select('[data-shambala-source] .price-card__seasons li')])
        self.assertEqual([i.get('src') for i in a.select('img')],[i.get('src') for i in b.select('img')])
        self.assertEqual(len(b.select('#prices')),1)
        self.assertEqual(len(b.select('script[data-shambala-live]')),1)
        self.assertEqual(b.select_one('#prices').parent,b.select_one('.hotel-site-concept__detail-grid'))
        self.assertEqual(len(BeautifulSoup(supplemental(result,SLUG),'html.parser').select('.gega-live')),1)

    def test_price_writer_preserves_live_and_fresh_source(self):
        original = (ROOT/'hotels'/SLUG/'index.html').read_text()
        result = replace_prices_block(original,'<section id="prices" class="hotel-price-section"><article class="price-card"><ul class="price-card__seasons"><li>Свежие условия</li></ul></article></section>',SLUG)
        soup = BeautifulSoup(result,'html.parser')
        self.assertEqual(len(soup.select('.gega-live')),1)
        self.assertEqual(soup.select_one('[data-shambala-source] li').get_text(),'Свежие условия')

    def test_other_pages_unchanged(self):
        for page in (ROOT/'hotels').glob('*/index.html'):
            if page.parent.name != SLUG:
                value = page.read_text()
                self.assertEqual(apply_to_page_html(value,page.parent.name),value)


if __name__ == '__main__':
    unittest.main()
