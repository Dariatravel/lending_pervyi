"""Tariff identity, regeneration and isolation of the single-page price pilot."""
import json
from pathlib import Path
import re
import sys
import unittest
from unittest.mock import patch
import html

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from bs4 import BeautifulSoup
from gega_prices import SLUG, apply_to_page_html, parse_lines
from supplemental_store import apply_to_page_html as with_supplemental


class GegaPricesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture=json.loads((ROOT/'tools/fixtures/gega-prices-20261124.json').read_text())
        cls.original = ('<html><head></head><body><main class="hotel-site-concept">'
            '<div class="benefit-grid"><li>Размещение с животными возможно с доп платой 2500₽.</li></div>'
            '<div class="hotel-site-concept__detail-grid"><div class="hotel-site-concept__detail-main">'
            '<section id="supplemental-comments"><article class="room-overview-card"><h3>Цены с 30 апреля:</h3><p>'+
            html.escape('\n'.join(fixture['summer_lines']))+'</p><img src="'+fixture['images'][-1]+'"></article></section>'
            +''.join('<img src="'+url+'">' for url in fixture['images'][:-1])+'</div>'
            '<aside><section id="prices" class="hotel-price-section"><article class="price-card"><ul class="price-card__seasons">'+
            ''.join('<li>'+html.escape(line)+'</li>' for line in fixture['winter_lines'])+
            '</ul></article></section></aside></div></main></body></html>')
        cls.output = apply_to_page_html(cls.original,SLUG)

    def test_all_112_tariffs_and_exact_source_periods_survive(self):
        soup = BeautifulSoup(self.original,'html.parser')
        winter = [li.get_text(' ',strip=True) for li in soup.select('#prices li')]
        summer = soup.select_one('#supplemental-comments .room-overview-card p').get_text('\n').splitlines()
        expected = parse_lines(winter)[0]+parse_lines(summer)[0]
        updated = BeautifulSoup(self.output,'html.parser')
        panels=updated.select('[data-gega-period]')
        self.assertEqual(len(panels),14)
        self.assertEqual(sum(len(p['rows']) for p in expected),112)
        self.assertEqual([p.get_text() for p in updated.select('#gega-period option')],[p['title'] for p in expected])
        for panel,period in zip(panels,expected):
            self.assertEqual(len(panel.select('tbody tr')),8)
            for tr,row in zip(panel.select('tbody tr'),period['rows']):
                self.assertEqual(tr.th.get_text(),row['room'])
                self.assertEqual(tr.select('td')[0].get_text(),str(row['guests'])+' гостя')
                amount=int(re.sub(r'\D','',tr.select('td')[1].get_text()))
                self.assertEqual(amount,row['amount'])

    def test_prices_full_width_and_no_price_article_left_in_overviews(self):
        s=BeautifulSoup(self.output,'html.parser')
        self.assertIn('hotel-site-concept__detail-grid',s.select_one('#prices').parent['class'])
        self.assertFalse(s.select('#supplemental-comments'))
        self.assertEqual(len(s.select('#prices')),1)

    def test_extras_preserved_separately_and_not_inserted_as_room_tariffs(self):
        s=BeautifulSoup(self.output,'html.parser');extra=s.select_one('.gega-extras').get_text(' ')
        for original in BeautifulSoup(self.original,'html.parser').select('#prices li')[-7:]:
            self.assertIn(original.get_text(),extra)
        self.assertIn('1500',extra);self.assertIn('2000',extra);self.assertIn('800',extra)
        self.assertIn('600',extra);self.assertIn('2500',extra)

    def test_original_image_preserved_and_no_media_changes(self):
        def images(source):
            return sorted(img.get('src','') for img in BeautifulSoup(source,'html.parser').find_all('img'))
        self.assertEqual(images(self.original),images(self.output))

    def test_second_application_and_fresh_supplement_do_not_duplicate_or_lose_prices(self):
        twice = apply_to_page_html(self.output,SLUG)
        a,b=BeautifulSoup(twice,'html.parser'),BeautifulSoup(self.output,'html.parser')
        self.assertEqual(str(a.select_one('#prices')),str(b.select_one('#prices')))
        self.assertEqual(len(a.select('link[data-gega-prices]')),1)
        self.assertEqual(len(a.select('script[data-gega-prices]')),1)
        fresh = with_supplemental(self.output,SLUG)
        self.assertEqual(len(BeautifulSoup(fresh,'html.parser').select('[data-gega-period]')),14)

    def test_other_pages_are_unchanged(self):
        for page in (ROOT/'hotels').glob('*/index.html'):
            if page.parent.name != SLUG:
                original=page.read_text()
                self.assertEqual(apply_to_page_html(original,page.parent.name),original)

    def test_missing_category_or_unknown_room_fails_closed(self):
        with self.assertRaises(ValueError):parse_lines(['С 1 по 10 мая с завтраками','4000₽ - Неизвестный номер'])
        with self.assertRaises(ValueError):parse_lines(['С 1 по 10 мая с завтраками','4000₽ - Люкс'])

    def test_existing_price_audit_reads_exact_original_winter_lines(self):
        from audit_telegram_site_prices import site_price_lines_ordered,site_prices
        self.assertEqual(site_price_lines_ordered(self.original),site_price_lines_ordered(self.output))
        self.assertEqual(site_prices(self.original),site_prices(self.output))

    def test_detail_writer_updates_visible_tariff_too(self):
        import apply_telegram_detail_sections as writer
        lines=json.loads((ROOT/'tools/fixtures/gega-prices-20261124.json').read_text())['winter_lines']
        new_lines=[line.replace('3000₽','3999₽') for line in lines]
        output=[];path=ROOT/'hotels'/SLUG/'index.html'
        with patch.object(Path,'read_text',return_value=self.output),patch.object(Path,'write_text',side_effect=lambda value,**kw:output.append(value)),patch.object(writer,'fetch_og_description',return_value='✔️ЦЕНЫ:\n'+'\n'.join(new_lines)):
            changed,_=writer.apply_to_page(path,'abhazbooking',5510,False)
        self.assertTrue(changed)
        panel=BeautifulSoup(output[0],'html.parser').select_one('[data-gega-period="0"]')
        self.assertIn('3\u202f999',panel.get_text())

    def test_price_block_replacement_restores_new_ui_and_summer_from_manifest(self):
        from sync_prices_from_telegram import replace_prices_block
        source=BeautifulSoup(self.original,'html.parser').select_one('#prices')
        result=replace_prices_block(self.output,str(source).replace('3000₽','3999₽'),SLUG)
        parsed=BeautifulSoup(result,'html.parser')
        self.assertEqual(len(parsed.select('[data-gega-period]')),14)
        self.assertIn('3\u202f999',parsed.select_one('[data-gega-period="0"]').get_text())

    def test_removed_summer_source_does_not_leave_old_tariffs_or_image(self):
        parsed=BeautifulSoup(self.output,'html.parser')
        for node in parsed.select('[data-gega-summer-source], .gega-original-image'):node.decompose()
        result=apply_to_page_html(str(parsed),SLUG)
        soup=BeautifulSoup(result,'html.parser')
        self.assertEqual(len(soup.select('[data-gega-period]')),4)
        self.assertFalse(soup.select('[data-gega-summer-source]'))
        self.assertFalse(soup.select('.gega-original-image'))

    def test_changed_guest_basis_is_not_silently_replaced_with_three(self):
        changed=self.original.replace('за трехместное размещение','за четырехместное размещение')
        with self.assertRaises(ValueError):apply_to_page_html(changed,SLUG)


if __name__=='__main__':unittest.main()
