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

def advertised_year(row, supplemental, today, extract_price):
    """Явное предложение ранней брони или тариф проживания следующего года."""
    from bs4 import BeautifulSoup
    target = 2027
    if today.year > target:
        return None
    details = row.get("details") or {}
    prices = [str(p.get("text", "") if isinstance(p, dict) else p)
              for p in details.get("prices", [])]
    sections = [str(line) for section in details.get("sections", [])
                for line in [section.get("label", ""), *section.get("lines", [])]]
    extra = BeautifulSoup(supplemental, "html.parser").get_text(" ", strip=True) if supplemental else ""
    lines = [str(row.get(key) or "") for key in ("title", "summary", "excerpt")]
    lines += [str(details.get("lead") or ""), *sections, *prices, extra]
    for line in lines:
        for match in re.finditer(r"\bранн?е[а-яё]*\s+бронировани[а-яё]*(?:\s+(?:на\s+)?(20\d{2}))?", line, re.I):
            if not match[1] or int(match[1]) == target:
                return target
        if re.search(rf"\b(?:бронирование|цены|тарифы)\s*(?:на\s+)?(?:сезон\s+)?{target}\b", line, re.I):
            return target
    for i, line in enumerate(prices):
        if not re.search(rf"\b{target}\b", line) or re.search(r"лист ожидания|появится|будет готов", line, re.I):
            continue
        if any(extract_price(text) and not NON_STAY_PRICE.search(text) for text in prices[i:]):
            return target
    return None

def current_prices_before_campaign(prices, today):
    """Для сезонной карточки сохраняем цену только в явно указанном текущем периоде."""
    current = []
    period = False
    for item in prices:
        text = str(item.get("text", "") if isinstance(item, dict) else item)
        years = [int(y) for y in re.findall(r"\b20\d{2}\b", text)]
        months = any(re.search(r"\b" + month, text, re.I) for month in MONTHS)
        if re.search(r"бронировани|цены.{0,12}2027|сезон.{0,12}2027", text, re.I):
            if today.year != 2027:
                break
        if years and today.year not in years:
            break
        if months:
            period = True
        if period:
            current.append(item)
    return current
