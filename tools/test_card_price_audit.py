import datetime as dt
import unittest
from card_price_audit import card_rates,identity,table_rates,tariff,period

class PriceAuditTests(unittest.TestCase):
    def test_two_rivieras(self):
        self.assertNotEqual(identity('https://t.me/abhazbooking/5296'),identity('https://t.me/abhazbooking/2706'))
        self.assertIsNone(identity('https://example.com/abhazbooking/5296'))

    def test_tariff_key(self):
        self.assertNotEqual(tariff('Стандарт','завтрак',True),tariff('Стандарт 1-мест.','завтрак',True))
        self.assertNotEqual(tariff('Стандарт','полупансион',True),tariff('Стандарт','завтрак',True))
        self.assertIsNone(tariff('Стандарт','завтрак',False)[2])

    def test_overlap(self):
        d=lambda i:dt.date(2026,12,i)
        spans=table_rates('3000 до 25 / 4100 с 25',d(1),d(31))
        self.assertEqual([p for lo,hi,p,_ in spans if lo<=d(25)<=hi],[3000,4100])

    def test_missing(self):
        d=lambda i:dt.date(2026,12,i)
        self.assertFalse(any(lo<=d(26)<=hi for lo,hi,*_ in table_rates('3000 до 25',d(1),d(31))))

    def test_generic_single(self):
        raw=['(2026)','1–30 ноября','Завтрак:','3000₽ Стандарт 1-мест.','Условия для групп','2000₽ Стандарт 1-мест.']
        rates=card_rates({'title':'Дом','post':222,'channel':'abhazbooking','prices':[{'text':x} for x in raw]})
        self.assertEqual(len(rates[('стандарт','завтрак',1)]),1)

    def test_new_year(self):
        self.assertEqual(period('30 декабря–5 января',2026),[(dt.date(2026,12,30),dt.date(2027,1,5))])
