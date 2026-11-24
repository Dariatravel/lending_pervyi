"""Подпись будущего сезона, только когда нет цены текущего месяца."""
import re

YEAR_MARKER = re.compile(r'(?:бронировани[ея]|цен[аы]|сезон|тариф[ыа]?)\D{0,18}(20\d{2})',re.I)
NON_STAY_PRICE = re.compile(r'свободного\s+посещения|сторонних\s+гостей|(?:₽|руб\w*)\s*(?:в|за|/)\s*час',re.I)
MONTH_YEAR = re.compile(r'(?:январ|феврал|март|апрел|ма[йя]|июн|июл|август|сентябр|октябр|ноябр|декабр)[а-яё]*\s+(20\d{2})',re.I)
MONTHS = ('январ','феврал','март','апрел','ма[йяе]','июн','июл','август','сентябр','октябр','ноябр','декабр')


def marker_year(text, month):
    marker = YEAR_MARKER.search(text) or MONTH_YEAR.search(text)
    if not marker:
        return None
    hits = sorted((m.start(),number) for number,pattern in enumerate(MONTHS,1)
                  for m in re.finditer(r'\b'+pattern+r'[а-яё]*',text,re.I))
    dated = MONTH_YEAR.search(text)
    if (dated and len(hits) >= 2 and hits[0][1] > hits[-1][1]
            and re.search(r'\bпо\b|[–—-]',text,re.I)):
        years = re.findall(r'\b(20\d{2})\b',text)
        end_year = int(years[-1])
        start_year = int(years[0]) if len(years)>1 else end_year-1
        return start_year if month >= hits[0][1] else end_year if month <= hits[-1][1] else start_year
    return int(marker[1])


def early_booking_year(row, month, today, monthly_prices, extract_price):
    """Не принимаем название «Новый год2027» за раннее бронирование."""
    if row.get('source_kind') != 'hotel':
        return None
    marker = YEAR_MARKER.search(str(row.get('title') or ''))
    year = int(marker[1]) if marker else today.year
    current, future = [], set()
    for item in (row.get('details') or {}).get('prices') or []:
        text = str(item.get('text') or '') if isinstance(item,dict) else str(item)
        heading_year = marker_year(text,month)
        if heading_year is not None and extract_price(text) is None:
            year = heading_year
        line_year = heading_year if heading_year is not None else year
        if line_year == today.year:
            current.append(item)
        elif line_year > today.year and extract_price(text) is not None and not NON_STAY_PRICE.search(text):
            future.add(line_year)
    if not future or monthly_prices(current,today).get(month) is not None:
        return None
    return min(future)
