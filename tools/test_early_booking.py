"""Будущий сезон не выдаётся за текущую цену размещения."""
from datetime import date
from pathlib import Path
import sys
import unittest
sys.path[:0] = [str(Path(__file__).resolve().parent),str(Path(__file__).resolve().parents[1]/'scripts')]
from build_min_prices import monthly_min_prices, extract_price
from early_booking import early_booking_year


class EarlyBookingTests(unittest.TestCase):
    def year(self,title,prices,kind='hotel'):
        row={'source_kind':kind,'title':title,'details':{'prices':[{'text':p} for p in prices]}}
        return early_booking_year(row,11,date(2026,11,24),monthly_min_prices,extract_price)

    def test_apartment_future_tariff_is_not_current(self):
        from early_booking import advertised_year, current_prices_before_campaign
        raw = ["РАННЕЕ БРОНИРОВАНИЕ 2027", "8000₽ за номер"]
        row = {"source_kind": "kvartira", "details": {"prices": raw}}
        today = date(2026, 11, 26)
        self.assertEqual(advertised_year(row, "", today, extract_price), 2027)
        self.assertFalse(current_prices_before_campaign(raw, today))
        self.assertEqual(current_prices_before_campaign(["Ноябрь", "3500₽", *raw], today),
                         ["Ноябрь", "3500₽"])

    def test_future_summer_only(self):
        self.assertEqual(self.year('Отель – РАННЕЕ БРОНИРОВАНИЕ 2027',['Май','8000₽ – номер']),2027)

    def test_current_month_before_future_block_is_retained(self):
        self.assertIsNone(self.year('Отель',['Ноябрь','5000₽ – номер','РАННЕЕ БРОНИРОВАНИЕ 2027','Июнь','6000₽ – номер']))

    def test_future_constant_price_not_current_month(self):
        self.assertEqual(self.year('Бронирование 2027',['8000₽ – номер']),2027)

    def test_year_in_price_block(self):
        self.assertEqual(self.year('Отель',['ЦЕНЫ НА 2027 ГОД','Июнь','8000₽ – номер']),2027)

    def test_no_guess_from_missing_price_or_new_year_title(self):
        self.assertIsNone(self.year('Отель',['Июнь','8000₽ – номер']))
        self.assertIsNone(self.year('Новый год2027',['Декабрь','8000₽ – номер']))

    def test_requires_actual_price_and_not_extra_or_apartment(self):
        self.assertIsNone(self.year('Раннее бронирование2027',['Доп место2000₽']))
        self.assertIsNone(self.year('Раннее бронирование2027',['Июнь','8000₽ – номер'],'kvartira'))

    def test_known_current_price_is_not_replaced(self):
        self.assertIsNone(self.year('Отель',['1–30ноября','4500₽ – номер']))

    def test_waitlist_and_sauna_are_not_room_prices(self):
        self.assertIsNone(self.year('Отель',['Доступна запись в лист ожидания на сезон 2027.',
            'Для сторонних гостей посещение – 2500₽ с человека','Сауна – 5000₽ в час']))

    def test_explicit_current_year_after_future_title(self):
        self.assertIsNone(self.year('Раннее бронирование2027',['Ноябрь 2026','4500₽ – номер','Цены2027','Июнь','8000₽ – номер']))
        self.assertIsNone(self.year('Раннее бронирование2027',['4500₽ – ноябрь 2026','8000₽ – июнь 2027']))

    def test_winter_crossing_new_year_retains_current_november(self):
        self.assertIsNone(self.year('Отель',['С ноября по май 2027','1700₽ – номер','Раннее бронирование2027','Июнь','8000₽ – номер']))
        self.assertIsNone(self.year('Отель',['1500₽/сутки – с ноября по апрель 2027','Раннее бронирование2027','Июнь','8000₽ – номер']))
        self.assertIsNone(self.year('Отель',['С ноября 2026 по май 2027','1700₽ – номер','Раннее бронирование2027','Июнь','8000₽ – номер']))

    def test_expired_explicit_year_is_not_current_november(self):
        self.assertEqual(self.year('Отель',['Ноябрь 2025','1700₽ – номер','Раннее бронирование2027','Июнь','8000₽ – номер']),2027)

    def test_extra_guest_fee_is_not_minimum_room_price(self):
        rows=['Ноябрь','4490₽ Стандарт','3590₽ Стандарт 1-мест.','1280₽ +1 взр.','1020₽ +1 реб.']
        self.assertEqual(monthly_min_prices(rows,date(2026,11,24))[11],3590)
        self.assertIsNone(extract_price('1020₽ +1 реб.'))
        self.assertIsNone(extract_price('1280руб +1 взр.'))
        self.assertEqual(extract_price('12000₽ – номер 2+1'),12000)


if __name__ == '__main__':
    unittest.main()
