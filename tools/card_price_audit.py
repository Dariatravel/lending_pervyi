"""Сверка таблицы сезона с сохранёнными тарифными строками карточек."""
import hashlib
import json
import calendar
import datetime as dt
import re
from collections import defaultdict
from itertools import groupby
from urllib.parse import urlsplit, parse_qs

from compare_price_tabs import MONTHS, cell_text, is_reddish

MEALS = ('без питания', 'завтрак', 'полупансион', 'полный пансион')
MONTH = '|'.join(sorted(MONTHS, key=len, reverse=True))
SEASON = 2026


def norm(s):
    return ' '.join(s.lower().replace('ё', 'е').split())


def identity(link):
    try:
        u = urlsplit(link.strip())
    except ValueError:
        return None
    if u.scheme not in ('http','https') or u.netloc.lower() not in ('t.me','telegram.me','www.t.me','www.telegram.me'):
        return None
    if set(parse_qs(u.query,keep_blank_values=True)) - {'single'} or u.fragment:
        return None
    m=re.fullmatch(r'/([a-zA-Z0-9_]+)/(?:[0-9]+/)?([0-9]+)/?',u.path)
    return (m[1].lower(),int(m[2])) if m else None


def period(text, year):
    """Все интервалы сохраняются; отсутствие разбора не переносит предыдущую дату."""
    intervals = []
    for part in re.split(r'\s+и\s+|,\s*', norm(text)):
        if part in MONTHS:
            month = MONTHS[part]
            intervals.append((dt.date(year, month, 1), dt.date(year, month, calendar.monthrange(year, month)[1])))
            continue
        m = re.fullmatch(rf'(?:с )?(\d{{1,2}})(?: ({MONTH}))?\s*(?:[–—-]| по )\s*(\d{{1,2}}) ({MONTH})', part)
        if not m:
            return []
        m2 = MONTHS[m[4]]
        m1 = MONTHS.get(m[2], m2)
        try:
            start = dt.date(year, m1, int(m[1]))
            end = dt.date(year + int(m2 < m1), m2, int(m[3]))
        except ValueError:
            return []
        if start > end:
            return []
        intervals.append((start, end))
    return intervals


def tariff(label, meal, double):
    label = norm(label)
    single = re.search(r' (?:одноместное разм(?:ещение)?|1-мест\.?)$', label)
    occupancy = 1 if single else 2 if double else None
    category = label[:single.start()] if single else label
    return (category, meal, occupancy)


def inline_periods(text, year):
    result=[]
    for part in norm(text.strip(' 🌲🎄')).split(','):
        part=part.strip()
        bounds=re.fullmatch(rf'с ({MONTH}) по ({MONTH})',part)
        half=re.fullmatch(rf'({MONTH}) (до|с) (\d{{1,2}})(?:го)?',part)
        if bounds:
            m1,m2=(MONTHS[x] for x in bounds.groups())
            y2=year+int(m2<m1)
            spans=[(dt.date(year,m1,1),dt.date(y2,m2,calendar.monthrange(y2,m2)[1]))]
        elif half:
            month=MONTHS[half[1]]
            try: cut=dt.date(year,month,int(half[3]))
            except ValueError: return []
            spans=[(dt.date(year,month,1),cut)] if half[2]=='до' else [(cut,dt.date(year,month,calendar.monthrange(year,month)[1]))]
        else:
            spans=period(part,year)
        if not spans: return []
        result.extend(spans)
    return result


def read_inline(card, offers):
    year=meal=category=None
    hints=set()
    parsed=0
    card["_examples"]=[]
    for i,item in enumerate(card['prices'] or [],1):
        raw=item.get('text','').strip()
        text=norm(raw)
        y=re.fullmatch(r'\(?(?:(?:раннее )?бронирование )?(20\d{2})\)?',text)
        if y:
            year=int(y[1]);meal=category=None
            continue
        if text.rstrip(':') in MEALS:
            meal=text.rstrip(':')
            continue
        price=re.fullmatch(r'([0-9 ]+)\s*(?:₽(?:/сутки)?|/сутки)\s*[–—-]\s*(.+)',text)
        if price:
            if not year: hints.add('год')
            if not meal: hints.add('питание')
            if not category: hints.add('категорию')
            spans=inline_periods(price[2],year) if year else []
            if spans:
                parsed+=1
                card['_examples'].append((category or '',meal or '',year,i,raw))
                if category and meal:
                    key=tariff(category,meal,False)
                    if key[2]:
                        for lo,hi in spans:
                            offers[key].append((lo,hi,int(price[1].replace(' ','')),f'{card["title"]}, строка {i}: {year}, {category}, {meal}, {raw}'))
            continue
        if re.fullmatch(r'(?:одно|двух|трех|четырех)комнатный номер|(?:двух|трех|четырех)местное|(?:стандарт|люкс|семейный)(?: 1-мест\.?)?',text):
            category,meal=text,None
        else:
            category=meal=None
    card['_parsed_periods']=parsed
    card['_missing']=sorted(hints)

def card_rates(card):
    offers = defaultdict(list)
    dates, meal, double, year = [], None, False, None
    # У этого блока сезон зафиксирован сверкой исходного прайса 2026/27.
    royal = (card['channel'], card['post']) == ('abhazbooking', 5296)
    checked = hashlib.sha256(json.dumps(card['prices'],ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    royal = royal and checked == '54d0dec22b17b917f87d212a5281a06542ec0beb1433dba669e7828e456789a6'
    card['_royal_checked'] = royal
    if royal:
        year = SEASON
    for i, item in enumerate(card['prices'] or [], 1):
        raw = item.get('text', '').strip()
        text = norm(raw)
        y = re.fullmatch(r'\(?(?:(?:раннее )?бронирование )?(20\d{2})\)?', text)
        if y:
            year, dates, meal, double = int(y[1]), [], None, False
        elif text == '(за двухместное размещение)':
            double = True
        elif text.rstrip(':') in MEALS:
            meal = text.rstrip(':')
        elif year and (spans := period(text, year)):
            if royal:
                spans = [(lo.replace(year=lo.year+1),hi.replace(year=hi.year+1)) if lo.month < 11 else (lo,hi) for lo,hi in spans]
            dates, date_label, meal = spans, raw, None
        elif m := re.fullmatch(r'(\d+)\s*₽(?:/сутки)?\s*[-–]?\s*(.+)', raw):
            if dates and meal and tariff(m[2], meal, double)[2] is not None and not m[2].startswith('+'):
                ref = f'{card["title"]}, строка {i}: {date_label}; {meal}; {raw}'
                for start, end in dates:
                    offers[tariff(m[2], meal, double)].append((start,end,int(m[1]),ref))
        else:
            dates, meal = [], None
    read_inline(card,offers)
    return offers


def table_rates(raw, start, end):
    if not raw:
        return []
    out = []
    for part in re.split(r'[/\\;\n]', raw):
        m = re.fullmatch(r'(\d{3,6})(?:\s+(до|по|с)\s+(\d{1,2})(?:го)?)?', part.strip())
        if not m:
            return None
        lo, hi = start, end
        if m[2]:
            try:
                boundary = start.replace(day=int(m[3]))
            except ValueError:
                return None
            if m[2]=='с':
                lo = max(lo,boundary)
            else:
                hi = min(hi,boundary)
        out.append((lo,hi,int(m[1]),raw))
    return out


def audit(rows, cards, today):
    headers = [norm(cell_text(rows[0]['cells'],i)) for i in range(4,23)]
    expected = 'март|апрель|май с 1 по 15|май с 15 по 31|июнь с 1 по 15|июнь с 15 по 30|июль с 1 по 15|июль с 15 по 31|август|сентябрь с 1 по 20|сентябрь с 20|октябрь|ноябрь|декабрь|новый год|январь|февраль|март|апрель'.split('|')
    if headers != expected:
        raise ValueError('Изменились заголовки ручной таблицы')
    index = defaultdict(list)
    for card in cards:
        index[(card['channel'],card['post'])].append(card)
    records = []
    for row in rows[1:]:
        cells = row['cells']
        title = cell_text(cells,0)
        if not title or row['hidden'] or is_reddish(cells,0) or is_reddish(cells,1):
            continue
        link = (cells[2].get('hyperlink') or cell_text(cells,2)) if len(cells)>2 else ''
        matches = index.get(identity(link), [])
        def emit(status, manual, card):
            records.append((status,f'Таблица, строка {row["row"]}: {title} | {manual}',card))
        if len(matches)!=1:
            emit('Связь не подтверждена',link or 'нет ссылки','Карточка: '+('несколько по ссылке' if matches else 'нет по точной ссылке'))
            continue
        card = matches[0]
        prefix = norm(card['title'])+' '
        name = norm(title)
        meal = next((m for m in MEALS if name.endswith(' '+m)),None)
        ref = f'Карточка {card["title"]} ({link})'
        rates = []
        if name.startswith(prefix) and meal:
            label = name[len(prefix):-len(meal)].strip()
            if (card['_royal_checked'] and label=='люкс с видом на море'
                    and card.get('suite_evidence')=='Двухкомнатный Люкс с видом на море площадью 60 м².'):
                label='люкс'
            double_explicit = label.endswith(' двухместное размещение')
            label = label.removesuffix(' двухместное размещение')
            rates = card['_rates'].get(tariff(label,meal,double_explicit or card['_royal_checked']),[])
        if not rates:
            examples=[e for e in card['_examples'] if e[0] and e[0] in name]
            if examples:
                category,food,year,i,raw=examples[0]
                ref+=f' | строка {i}, {category}, {year}: {raw} (кандидат)'
            emit('Тариф не сопоставлен','точное размещение, категория или питание не установлены',ref)
            continue
        from compare_price_tabs import MANUAL_COLUMNS
        columns = {col:(dt.date(SEASON,m,d),dt.date(SEASON,m2,d2)) for col,(m,d,m2,d2) in MANUAL_COLUMNS.items()}
        for col,month in enumerate(range(1,5),19):
            columns[col]=(dt.date(SEASON+1,month,1),dt.date(SEASON+1,month,calendar.monthrange(SEASON+1,month)[1]))
        schedule=[]
        unknown=[]
        for col,(lo,hi) in columns.items():
            raw=cell_text(cells,col)
            segments=table_rates(raw,lo,hi)
            address=f'{chr(65+col)}{row["row"]}: {raw or "пусто"}'
            if segments is None:
                unknown.append((lo,hi,address))
            else:
                schedule.extend((start,end,value,address) for start,end,value,_ in segments)
        holiday=cell_text(cells,18)
        if holiday:
            address=f'S{row["row"]}: {holiday}'
            for part in re.split(r'[/;]',holiday):
                m=re.fullmatch(r'(\d+) с (\d{1,2}) по (\d{1,2})',part.strip())
                if not m:
                    unknown.append((dt.date(SEASON,12,1),dt.date(SEASON+1,1,31),address))
                    break
                day1,day2=int(m[2]),int(m[3])
                if not (1<=day1<=31 and 1<=day2<=31):
                    unknown.append((dt.date(SEASON,12,1),dt.date(SEASON+1,1,31),address))
                    break
                month=12 if day1>=20 else 1
                lo=dt.date(SEASON if month==12 else SEASON+1,month,day1)
                hi=dt.date(SEASON+1,1,day2) if month==1 or day2<day1 else dt.date(SEASON,12,day2)
                schedule.append((lo,hi,int(m[1]),address))
        for col,(lo,hi) in columns.items():
            events=[]
            day=max(lo,today)
            while day<=hi:
                a=[x for x in schedule if x[0]<=day<=x[1]]
                b=[x for x in rates if x[0]<=day<=x[1]]
                unclear=[x[2] for x in unknown if x[0]<=day<=x[1]]
                status='Совпадение'
                if len(a)>1 or len(b)>1:
                    status='Наложение периодов'
                elif unclear:
                    status='Тариф не сопоставлен'
                elif not a or not b:
                    status='Пропуск дат'
                elif a[0][2]!=b[0][2]:
                    status='Расхождение цен'
                sources=tuple(x[3] for x in a)+tuple(unclear)
                events.append((day,(status,tuple(x[3] for x in b),sources)))
                day+=dt.timedelta(days=1)
            for (status,refs,sources),days in groupby(events,key=lambda x:x[1]):
                ds=[x[0] for x in days]
                manual=' / '.join(sources) or f'{chr(65+col)}{row["row"]}: {cell_text(cells,col) or "пусто"} | нет цены на даты'
                emit(status,f'{manual} | {ds[0]}..{ds[-1]}', ' / '.join(refs) or ref+' | нет строки на даты')
    return records
