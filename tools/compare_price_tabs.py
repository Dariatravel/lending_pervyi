#!/usr/bin/env python3
"""Сверка вкладок «ЦЕНЫ АВТО» (из Telegram) и «АКТУАЛЬНЫЕ ЦЕНЫ» (вручную)
в Google-таблице «СЕЗОН 2026. Описание отелей, цены».

Что делает:
  1. Читает обе вкладки через Sheets API (service account).
  2. В ручной вкладке пропускает скрытые строки и строки с красной заливкой
     (правило: такие объекты Дарья не ведёт).
  3. Сопоставляет строки ручной вкладки с объектами авто-вкладки:
     по ссылке на Telegram-пост (через data/catalog-snapshot.json),
     затем по названию объекта.
  4. Разворачивает цены обеих вкладок в посуточные ряды (понимает пометки
     вида «5000 до 15», «2800 с 16», «6000 до 25 авг») и сравнивает по дням
     (по умолчанию от сегодня до конца декабря).
  5. Пишет отчёт в output/price_tabs_compare_report.txt и резюме в консоль.

Запуск (на Mac):  python3 tools/compare_price_tabs.py
Опции: --from-date 2026-05-01  --to-date 2026-12-31  (границы сравнения)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build

ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / 'output' / 'price_tabs_compare_report.txt'
SNAPSHOT_PATH = ROOT / 'data' / 'catalog-snapshot.json'

SPREADSHEET_ID = '1MwtvTx_VZ2tPrJ4ejDFipwgf5g5-tB8zX7u9AbCaUgg'
AUTO_TAB = 'ЦЕНЫ АВТО'
MANUAL_TAB = 'АКТУАЛЬНЫЕ ЦЕНЫ'
SEASON_YEAR = 2026

MONTHS = {
    'январь': 1, 'января': 1, 'февраль': 2, 'февраля': 2, 'март': 3, 'марта': 3,
    'апрель': 4, 'апреля': 4, 'май': 5, 'мая': 5, 'июнь': 6, 'июня': 6,
    'июль': 7, 'июля': 7, 'август': 8, 'августа': 8, 'сентябрь': 9, 'сентября': 9,
    'октябрь': 10, 'октября': 10, 'ноябрь': 11, 'ноября': 11,
    'декабрь': 12, 'декабря': 12,
}
MONTH_ABBR = {'янв': 1, 'фев': 2, 'мар': 3, 'апр': 4, 'мая': 5, 'май': 5,
              'июн': 6, 'июл': 7, 'авг': 8, 'сен': 9, 'окт': 10, 'ноя': 11, 'дек': 12}
MONTH_DAYS = {1: 31, 2: 28, 3: 31, 4: 30, 5: 31, 6: 30, 7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31}

# Колонки ручной вкладки -> диапазоны дат сезона 2026.
# Границы «с 15 по…» отдаём второй колонке (15-е число — в колонке «с 15»).
MANUAL_COLUMNS = {
    4: (3, 1, 3, 31),    # E март
    5: (4, 1, 4, 30),    # F апрель
    6: (5, 1, 5, 14),    # G май с 1 по 15
    7: (5, 15, 5, 31),   # H май с 15 по 31
    8: (6, 1, 6, 14),    # I июнь с 1 по 15
    9: (6, 15, 6, 30),   # J июнь с 15 по 30
    10: (7, 1, 7, 14),   # K июль с 1 по 15
    11: (7, 15, 7, 31),  # L июль с 15 по 31
    12: (8, 1, 8, 31),   # M август
    13: (9, 1, 9, 19),   # N сентябрь с 1 по 20
    14: (9, 20, 9, 30),  # O сентябрь с 20
    15: (10, 1, 10, 31), # P октябрь
    16: (11, 1, 11, 30), # Q ноябрь
    17: (12, 1, 12, 31), # R декабрь
    # S «новый год», T январь, U февраль, V/W март-апрель 2027 — не сравниваем.
}


# ---------------------------------------------------------------- Sheets API

def pick_google_credentials_path() -> Path:
    candidates = [
        os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON', '').strip(),
        str(ROOT / 'google-service-account.json'),
        '/Users/darya_botova/Downloads/sonorous-bounty-488706-q9-32a19387de8d.json',
    ]
    for value in candidates:
        if value and Path(value).exists():
            return Path(value)
    raise FileNotFoundError('Не найден JSON service account для Google Sheets.')


def fetch_tab(service, title: str) -> dict:
    fields = ('sheets(data(rowMetadata(hiddenByUser,hiddenByFilter),'
              'rowData(values(formattedValue,effectiveFormat(backgroundColor),hyperlink))))')
    resp = service.spreadsheets().get(
        spreadsheetId=SPREADSHEET_ID,
        ranges=[f"'{title}'!A1:Z1500"],
        includeGridData=True,
        fields=fields,
    ).execute()
    data = resp['sheets'][0]['data'][0]
    rows_meta = data.get('rowMetadata', [])
    rows = []
    for i, rd in enumerate(data.get('rowData', [])):
        meta = rows_meta[i] if i < len(rows_meta) else {}
        rows.append({
            'row': i + 1,
            'hidden': bool(meta.get('hiddenByUser') or meta.get('hiddenByFilter')),
            'cells': rd.get('values', []),
        })
    return {'rows': rows}


def cell_text(cells, idx) -> str:
    if idx < len(cells):
        return str(cells[idx].get('formattedValue') or '').strip()
    return ''


def is_reddish(cells, idx) -> bool:
    if idx >= len(cells):
        return False
    bg = cells[idx].get('effectiveFormat', {}).get('backgroundColor', {})
    if not bg:
        return False
    r, g, b = bg.get('red', 0), bg.get('green', 0), bg.get('blue', 0)
    return r > 0.75 and g < 0.75 and b < 0.75


# ------------------------------------------------------------- нормализация

def norm_text(s: str) -> str:
    s = (s or '').upper().replace('Ё', 'Е')
    s = re.sub(r'["«»“”\'`]', ' ', s)
    s = re.sub(r'[^А-ЯA-Z0-9 ]', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def auto_title_core(title: str) -> str:
    m = re.search(r'"([^"]+)"', title or '')
    return norm_text(m.group(1) if m else title)


def daterange_days(m1, d1, m2, d2):
    start = dt.date(SEASON_YEAR, m1, min(d1, MONTH_DAYS[m1]))
    end = dt.date(SEASON_YEAR, m2, min(d2, MONTH_DAYS[m2]))
    days = []
    cur = start
    while cur <= end:
        days.append(cur)
        cur += dt.timedelta(days=1)
    return days


def parse_auto_period(text: str):
    """'Май' | '1 июня — 15 июня' -> список дат. None, если не разобрали."""
    t = (text or '').strip().lower().replace('ё', 'е')
    if t in MONTHS:
        m = MONTHS[t]
        return daterange_days(m, 1, m, MONTH_DAYS[m])
    m = re.fullmatch(r'(\d{1,2})\s+([а-я]+)\s*[—\-–]\s*(\d{1,2})\s+([а-я]+)', t)
    if m and m.group(2) in MONTHS and m.group(4) in MONTHS:
        m1, m2 = MONTHS[m.group(2)], MONTHS[m.group(4)]
        d1, d2 = int(m.group(1)), int(m.group(3))
        if (m1, min(d1, MONTH_DAYS[m1])) <= (m2, min(d2, MONTH_DAYS[m2])):
            return daterange_days(m1, d1, m2, d2)
    return None


# --------------------------------------------- разбор ячейки цены (ручная)

def parse_manual_cell(text: str, col_days: list) -> tuple[dict, bool, list]:
    """Разбирает ячейку ручной вкладки в посуточные цены в пределах колонки.

    Понимает: '3500' | '5000 до 15' | '2800 с 16' | '6000 до 25 авг'
    | '5000 до 15го\\3000 с 16'. -> ({дата: цена}, чистая_ли, свободные_числа).
    Свободные числа (без дат, если их больше одного) сравниваются «мягко».
    """
    t = (text or '').strip().lower().replace('ё', 'е')
    if not t:
        return {}, True, []
    if re.fullmatch(r'\d{3,6}', t):
        p = int(t)
        return {d: p for d in col_days}, True, []
    if 'месяц' in t:  # помесячная аренда — не сравниваем
        return {}, False, []

    series: dict = {}
    consumed = []

    def month_of(word):
        if not word:
            return None
        return MONTH_ABBR.get(word[:3])

    # «5000 до 15 (авг)» / «2800 с 16го»
    pat = re.compile(r'(\d{3,6})\s*(?:р|руб)?\s*(до|по|с)\s*(\d{1,2})\s*(?:го|е|-го)?\s*([а-я]{3,})?')
    # «с 15 2500» / «до 10 4000»
    pat_rev = re.compile(r'(до|по|с)\s*(\d{1,2})\s*(?:го|е|-го)?\s*([а-я]{3,})?\s+(\d{3,6})')

    matches = []
    for m in pat.finditer(t):
        matches.append((m.span(), int(m.group(1)), m.group(2), int(m.group(3)), month_of(m.group(4))))
    for m in pat_rev.finditer(t):
        span = m.span()
        if any(not (span[1] <= s[0] or span[0] >= s[1]) for s, *_ in matches):
            continue
        matches.append((span, int(m.group(4)), m.group(1), int(m.group(2)), month_of(m.group(3))))

    for span, price, op, day, month in matches:
        consumed.append(span)
        for d in col_days:
            if month and d.month != month:
                continue
            if op in ('до', 'по') and d.day <= day and (month or d.month == col_days[0].month or True):
                if d <= dt.date(SEASON_YEAR, month or d.month, min(day, MONTH_DAYS[month or d.month])):
                    series[d] = price
            elif op == 'с':
                if d >= dt.date(SEASON_YEAR, month or d.month, min(day, MONTH_DAYS[month or d.month])):
                    series[d] = price

    # числа вне разобранных фрагментов
    rest = list(t)
    for a, b in consumed:
        for i in range(a, b):
            rest[i] = ' '
    loose = [int(x) for x in re.findall(r'\d{3,6}', ''.join(rest))]

    if not matches and len(loose) == 1:
        return {d: loose[0] for d in col_days}, True, []
    if len(loose) == 1:
        for d in col_days:
            series.setdefault(d, loose[0])
        loose = []
    return series, False, loose


# ------------------------------------------------------- категории (токены)

SEAT_WORDS = {'ОДНОМЕСТН': 1, 'ДВУХМЕСТН': 2, 'ТРЕХМЕСТН': 3, 'ЧЕТЫРЕХМЕСТН': 4,
              'ПЯТИМЕСТН': 5, 'ШЕСТИМЕСТН': 6, 'ВОСЬМИМЕСТН': 8}
ROOM_WORDS = {'ОДНОКОМНАТН': 1, 'ДВУХКОМНАТН': 2, 'ТРЕХКОМНАТН': 3}
LUX_GROUP = ('ПОЛУЛЮКС', 'ДЕЛЮКС', 'ЛЮКС')  # порядок важен: сперва длинные
CAT_KEYWORDS = ('СТАНДАРТ', 'УЛУЧШЕНН', 'КОМФОРТ', 'ЭКОНОМ', 'СЕМЕЙН', 'СТУДИЯ',
                'АПАРТАМЕНТ', 'ДОМИК', 'КОТТЕДЖ', 'НОМЕР', 'КОРПУС', 'ДЕРЕВЯНН',
                'КАМЕНН', 'СЬЮТ', 'ВИП', 'СУПЕРИОР', 'КИНГ', 'МОРЕ', 'ГОРЫ',
                'БАССЕЙН', 'ТЕРРАС', 'ОТДЕЛЬН', 'ЗАВТРАК', 'ПАНСИОН', 'СРУБ',
                'АФРЕЙМ', 'ШАТЕР', 'ВИД', 'ВЫХОД')
# «Сильные» слова — класс номера: расходиться они не должны.
STRONG_KEYWORDS = frozenset(('СТАНДАРТ', 'УЛУЧШЕНН', 'КОМФОРТ', 'ЭКОНОМ',
                             'СЬЮТ', 'ВИП', 'СУПЕРИОР', 'СЕМЕЙН') + LUX_GROUP)


def cat_tokens(text: str) -> set:
    n = norm_text(text)
    toks = set()
    # отрицания
    if re.search(r'БЕЗ\s+БАЛКОН', n):
        toks.add('НЕТ_БАЛКОН')
        n = re.sub(r'БЕЗ\s+БАЛКОН\w*', ' ', n)
    if 'БАЛКОН' in n:
        toks.add('БАЛКОН')
    # люкс-группа с маскировкой (ПОЛУЛЮКС/ДЕЛЮКС содержат «ЛЮКС»)
    for w in LUX_GROUP:
        if w in n:
            toks.add(w)
            n = n.replace(w, ' ')
            break
    # вместимость
    for w, num in SEAT_WORDS.items():
        if w in n:
            toks.add(f'{num}МЕСТ')
    for m in re.finditer(r'\b([1-8])\s*-?\s*Х\b', n):
        toks.add(f'{m.group(1)}МЕСТ')
    for m in re.finditer(r'\bЗА\s+([1-8])\b', n):
        toks.add(f'{m.group(1)}МЕСТ')
    for m in re.finditer(r'\b([1-8])\s*ЧЕЛ', n):
        toks.add(f'{m.group(1)}МЕСТ')
    # комнаты
    for w, num in ROOM_WORDS.items():
        if w in n:
            toks.add(f'{num}КОМН')
    for m in re.finditer(r'\b([1-3])\s*-?\s*К(?:ОМНАТН\w*)?\b(?!\s*ОРПУС)', n):
        toks.add(f'{m.group(1)}КОМН')
    for kw in CAT_KEYWORDS:
        if kw in n:
            toks.add(kw)
    return toks


def tokens_conflict(a: set, b: set) -> bool:
    for prefix in ('МЕСТ', 'КОМН'):
        av = {t for t in a if t.endswith(prefix)}
        bv = {t for t in b if t.endswith(prefix)}
        if av and bv and not (av & bv):
            return True
    a_strong = a & STRONG_KEYWORDS
    b_strong = b & STRONG_KEYWORDS
    if a_strong and b_strong and not (a_strong & b_strong):
        return True
    if ('НЕТ_БАЛКОН' in a and 'БАЛКОН' in b) or ('НЕТ_БАЛКОН' in b and 'БАЛКОН' in a):
        return True
    return False


# ------------------------------------------------------------------- отчёт

def group_dates(dates):
    out = []
    for d in sorted(dates):
        if out and (d - out[-1][1]).days == 1:
            out[-1][1] = d
        else:
            out.append([d, d])
    return [(a, b) for a, b in out]


def fmt_range(a: dt.date, b: dt.date) -> str:
    if a == b:
        return a.strftime('%d.%m')
    return f"{a.strftime('%d.%m')}–{b.strftime('%d.%m')}"


SVERKA_TAB = 'СВЕРКА'


def write_sverka_tab(service, values: list) -> None:
    """Перезаписывает вкладку «СВЕРКА» переданными строками (создаёт при отсутствии)."""
    meta = service.spreadsheets().get(
        spreadsheetId=SPREADSHEET_ID, fields='sheets(properties(title))').execute()
    titles = [s['properties']['title'] for s in meta.get('sheets', [])]
    if SVERKA_TAB not in titles:
        service.spreadsheets().batchUpdate(
            spreadsheetId=SPREADSHEET_ID,
            body={'requests': [{'addSheet': {'properties': {'title': SVERKA_TAB}}}]},
        ).execute()
    service.spreadsheets().values().clear(
        spreadsheetId=SPREADSHEET_ID, range=f"'{SVERKA_TAB}'!A1:Z5000").execute()
    service.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"'{SVERKA_TAB}'!A1",
        valueInputOption='RAW',
        body={'values': values},
    ).execute()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--from-date', default=None, help='YYYY-MM-DD, по умолчанию сегодня')
    ap.add_argument('--to-date', default=f'{SEASON_YEAR}-12-31')
    ap.add_argument('--write-sheet', action='store_true',
                    help='записать результат во вкладку «СВЕРКА» этой же таблицы')
    args = ap.parse_args()
    date_from = dt.date.fromisoformat(args.from_date) if args.from_date else dt.date.today()
    date_to = dt.date.fromisoformat(args.to_date)

    scope = ('https://www.googleapis.com/auth/spreadsheets' if args.write_sheet
             else 'https://www.googleapis.com/auth/spreadsheets.readonly')
    creds = service_account.Credentials.from_service_account_file(
        str(pick_google_credentials_path()), scopes=[scope])
    service = build('sheets', 'v4', credentials=creds, cache_discovery=False)

    auto = fetch_tab(service, AUTO_TAB)
    manual = fetch_tab(service, MANUAL_TAB)

    # ---- Авто-вкладка -> {title: {category: {date: price}}} ----
    auto_prices: dict[str, dict[str, dict]] = defaultdict(dict)
    auto_bad_periods = []
    cur_title = cur_cat = None
    for r in auto['rows'][2:]:
        cells = r['cells']
        if cell_text(cells, 0):
            cur_title = cell_text(cells, 0)
        if cell_text(cells, 2):
            cur_cat = cell_text(cells, 2)
        period, price_txt = cell_text(cells, 4), cell_text(cells, 5)
        if not cur_title or not period or not price_txt:
            continue
        days = parse_auto_period(period)
        pm = re.fullmatch(r'\d{3,6}', price_txt.replace(' ', ''))
        if days is None or not pm:
            auto_bad_periods.append((r['row'], cur_title, period, price_txt))
            continue
        bucket = auto_prices[cur_title].setdefault(cur_cat or '', {})
        price = int(pm.group(0))
        for d in days:
            bucket[d] = price

    auto_cores = {t: auto_title_core(t) for t in auto_prices}
    auto_used: set[str] = set()

    # ---- Снапшот: ссылка -> title ----
    link_to_title = {}
    snapshot_titles = set()
    if SNAPSHOT_PATH.exists():
        snap = json.load(open(SNAPSHOT_PATH, encoding='utf-8'))
        for l in snap.get('listings', []):
            ch, t = l.get('source_channel'), (l.get('title') or '').strip()
            if t:
                snapshot_titles.add(auto_title_core(t))
            for key in ('source_message_id', 'source_topic_id'):
                v = l.get(key)
                if ch and v and t:
                    if str(l.get('is_active')) == 'True' or f't.me/{ch}/{v}' not in link_to_title:
                        link_to_title[f't.me/{ch}/{v}'] = t

    def core_in_name(core: str, name_norm: str) -> bool:
        return bool(core) and re.search(rf'(?<![А-ЯA-Z0-9]){re.escape(core)}(?![А-ЯA-Z0-9])', name_norm)

    def find_auto_object(name: str, link: str):
        nl = re.search(r't\.me/([\w_]+)/(\d+)', link or '')
        if nl:
            t = link_to_title.get(f't.me/{nl.group(1)}/{nl.group(2)}')
            if t and t in auto_prices:
                return t
        n = norm_text(name)
        candidates = [(len(core), t) for t, core in auto_cores.items() if core_in_name(core, n)]
        if candidates:
            candidates.sort(reverse=True)
            return candidates[0][1]
        return None

    def match_category(manual_name: str, auto_title: str):
        cats = list(auto_prices[auto_title].keys())
        remainder = norm_text(manual_name)
        for w in auto_cores[auto_title].split():
            remainder = re.sub(rf'(?<![А-ЯA-Z0-9]){re.escape(w)}(?![А-ЯA-Z0-9])', ' ', remainder)
        want = cat_tokens(remainder)
        if len(cats) == 1:
            if tokens_conflict(want, cat_tokens(cats[0])):
                return None, False
            return cats[0], True
        want_strong = want & STRONG_KEYWORDS
        scored = []
        for c in cats:
            have = cat_tokens(c)
            if tokens_conflict(want, have):
                continue
            # класс номера (стандарт/люкс/комфорт…) из ручного названия обязан
            # найтись в категории авто, иначе матч ненадёжен
            if want_strong and not (want_strong & have):
                continue
            scored.append((len(want & have), -len(have - want), c))
        scored.sort(reverse=True)
        if not want or not scored or scored[0][0] == 0:
            return None, False
        if len(scored) > 1 and scored[0][:2] == scored[1][:2]:
            return None, False
        return scored[0][2], True

    # ---- Проход по ручной вкладке ----
    mismatches, matched_ok = [], []
    skipped_red, no_object, no_category = [], [], []
    missing_in_auto = []   # есть в каталоге сайта, но нет в авто-вкладке
    early_2027 = []        # в авто-вкладке цены 2027 (раннее бронирование)
    dirty_cells = []

    for r in manual['rows'][1:]:
        cells = r['cells']
        name = cell_text(cells, 0)
        if not name or r['hidden']:
            continue
        if is_reddish(cells, 0) or is_reddish(cells, 1):
            skipped_red.append((r['row'], name))
            continue
        link = ''
        if len(cells) > 2:
            link = cells[2].get('hyperlink') or cell_text(cells, 2)

        auto_title = find_auto_object(name, link)
        if not auto_title:
            core_known = any(core_in_name(c, norm_text(name)) for c in snapshot_titles)
            (missing_in_auto if core_known else no_object).append((r['row'], name))
            continue
        auto_used.add(auto_title)
        if '2027' in auto_title:
            early_2027.append((r['row'], name, auto_title))
            continue
        cat, ok = match_category(name, auto_title)
        if not ok:
            no_category.append((r['row'], name, auto_title, len(auto_prices[auto_title])))
            continue
        auto_series = auto_prices[auto_title][cat]

        diffs_by_key = defaultdict(list)
        compared_days = 0
        for col, (m1, d1, m2, d2) in MANUAL_COLUMNS.items():
            raw = cell_text(cells, col)
            if not raw:
                continue
            col_days = daterange_days(m1, d1, m2, d2)
            series, clean, loose = parse_manual_cell(raw, col_days)
            if not clean and (series or loose):
                dirty_cells.append((r['row'], name, raw))
            for d in col_days:
                if not (date_from <= d <= date_to):
                    continue
                ap_ = auto_series.get(d)
                if ap_ is None:
                    continue
                mp = series.get(d)
                if mp is None:
                    if loose:
                        compared_days += 1
                        if ap_ not in loose:
                            diffs_by_key[(loose[0], ap_, f' (в ручной: «{raw}»)')].append(d)
                    continue
                compared_days += 1
                if mp != ap_:
                    note = '' if clean else f' (в ручной: «{raw}»)'
                    diffs_by_key[(mp, ap_, note)].append(d)
        if diffs_by_key:
            detail = []
            for (mp, ap_, note), dates in sorted(diffs_by_key.items(), key=lambda kv: min(kv[1])):
                for a, b in group_dates(dates):
                    extra = note + (' [граница периодов?]' if a == b else '')
                    detail.append((fmt_range(a, b), mp, ap_, extra))
            mismatches.append((r['row'], name, auto_title, cat, detail))
        elif compared_days:
            matched_ok.append((r['row'], name, auto_title, cat))

    auto_unused = sorted(set(auto_prices) - auto_used)

    # ---- Отчёт ----
    lines = []
    push = lines.append
    push(f'СВЕРКА ЦЕН: «{MANUAL_TAB}» (ручная) vs «{AUTO_TAB}» (из Telegram)')
    push(f'Дата запуска: {dt.date.today().isoformat()}. '
         f'Сравнение по дням: {date_from.isoformat()} — {date_to.isoformat()}.')
    push('Скрытые строки и строки с красной заливкой в ручной вкладке пропущены.')
    push('')
    push(f'Совпадают полностью: {len(matched_ok)} строк')
    push(f'С расхождениями цен: {len(mismatches)} строк')
    push(f'Объект есть на сайте, но нет в авто-вкладке: {len(missing_in_auto)} строк')
    push(f'Объект не найден нигде: {len(no_object)} строк')
    push(f'Категория не сопоставлена (нужен взгляд человека): {len(no_category)} строк')
    push(f'В авто-вкладке цены 2027 (раннее бронирование), сравнение пропущено: {len(early_2027)} строк')
    push(f'Объекты авто-вкладки без пары в ручной: {len(auto_unused)}')
    if skipped_red:
        push(f'Пропущено по красной заливке: {len(skipped_red)}')
    push('')

    if mismatches:
        push('=' * 70)
        push('РАСХОЖДЕНИЯ ЦЕН')
        push('=' * 70)
        for row, name, auto_title, cat, detail in mismatches:
            push(f'\n[строка {row}] {name}')
            push(f'  ↔ {auto_title} / {cat[:70]}')
            for rng, mp, ap_, extra in detail:
                push(f'  {rng}: ручная {mp} ₽, авто {ap_} ₽{extra}')

    if missing_in_auto:
        push('')
        push('=' * 70)
        push('ЕСТЬ НА САЙТЕ, НО НЕТ В АВТО-ВКЛАДКЕ (авто-выгрузка их не покрыла)')
        push('=' * 70)
        for row, name in missing_in_auto:
            push(f'  [строка {row}] {name}')

    if no_object:
        push('')
        push('=' * 70)
        push('ОБЪЕКТ НЕ НАЙДЕН НИ В АВТО-ВКЛАДКЕ, НИ В КАТАЛОГЕ САЙТА')
        push('=' * 70)
        for row, name in no_object:
            push(f'  [строка {row}] {name}')

    if no_category:
        push('')
        push('=' * 70)
        push('ОБЪЕКТ НАЙДЕН, НО КАТЕГОРИЯ НЕ ОПРЕДЕЛЕНА ОДНОЗНАЧНО')
        push('=' * 70)
        for row, name, auto_title, ncats in no_category:
            push(f'  [строка {row}] {name} → {auto_title} (категорий в авто: {ncats})')

    if early_2027:
        push('')
        push('=' * 70)
        push('В АВТО-ВКЛАДКЕ ЦЕНЫ 2027 ГОДА (сравнение с сезоном 2026 некорректно)')
        push('=' * 70)
        for row, name, auto_title in early_2027:
            push(f'  [строка {row}] {name} → {auto_title}')

    if auto_unused:
        push('')
        push('=' * 70)
        push('ОБЪЕКТЫ АВТО-ВКЛАДКИ, НЕ ВСТРЕТИВШИЕСЯ В РУЧНОЙ (видимых строк нет)')
        push('=' * 70)
        for t in auto_unused:
            push(f'  {t}')

    if dirty_cells:
        push('')
        push('=' * 70)
        push('НЕСТАНДАРТНЫЕ ЯЧЕЙКИ ЦЕН В РУЧНОЙ ВКЛАДКЕ (разобраны по датам из текста)')
        push('=' * 70)
        seen = set()
        for row, name, raw in dirty_cells:
            if (row, raw) in seen:
                continue
            seen.add((row, raw))
            push(f'  [строка {row}] {name}: «{raw}»')

    if auto_bad_periods:
        push('')
        push('=' * 70)
        push('НЕРАЗОБРАННЫЕ ПЕРИОДЫ В АВТО-ВКЛАДКЕ')
        push('=' * 70)
        for row, title, period, price in auto_bad_periods[:50]:
            push(f'  [строка {row}] {title}: «{period}» = «{price}»')

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text('\n'.join(lines) + '\n', encoding='utf-8')

    if args.write_sheet:
        msk_now = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=3)).strftime('%d.%m.%Y %H:%M')
        v: list = []
        v.append([f'ОБНОВЛЯЕТСЯ АВТОМАТИЧЕСКИ (сверка «{MANUAL_TAB}» ↔ «{AUTO_TAB}»). '
                  f'НЕ РЕДАКТИРОВАТЬ. Обновлено: {msk_now} МСК'])
        v.append([f'Сравнение по дням: {date_from.isoformat()} — {date_to.isoformat()}. '
                  f'Совпадают: {len(matched_ok)} | Расхождения: {len(mismatches)} | '
                  f'Нет в авто: {len(missing_in_auto)} | Категория неясна: {len(no_category)}'])
        v.append([])
        v.append(['РАСХОЖДЕНИЯ ЦЕН'])
        v.append(['Строка', 'Объект (ручная вкладка)', 'Объект и категория (авто)',
                  'Даты', 'Ручная, ₽', 'Авто, ₽', 'Пометка'])
        for row, name, auto_title, cat, detail in mismatches:
            for rng, mp, ap_, extra in detail:
                v.append([row, name, f'{auto_title} / {cat}', rng, mp, ap_, extra.strip()])
        if not mismatches:
            v.append(['', 'Расхождений нет ✅'])
        if missing_in_auto:
            v.append([])
            v.append(['ЕСТЬ НА САЙТЕ, НО НЕТ В АВТО-ВКЛАДКЕ'])
            for row, name in missing_in_auto:
                v.append([row, name])
        if no_object:
            v.append([])
            v.append(['ОБЪЕКТ НЕ НАЙДЕН НИ В АВТО-ВКЛАДКЕ, НИ В КАТАЛОГЕ САЙТА'])
            for row, name in no_object:
                v.append([row, name])
        if no_category:
            v.append([])
            v.append(['КАТЕГОРИЯ НЕ СОПОСТАВЛЕНА (нужен взгляд человека)'])
            for row, name, auto_title, ncats in no_category:
                v.append([row, name, f'{auto_title} (категорий в авто: {ncats})'])
        if early_2027:
            v.append([])
            v.append(['В АВТО-ВКЛАДКЕ ЦЕНЫ 2027 ГОДА — сравнение пропущено'])
            for row, name, auto_title in early_2027:
                v.append([row, name, auto_title])
        write_sverka_tab(service, v)
        print(f'Вкладка «{SVERKA_TAB}» обновлена.')

    print(f'Отчёт: {REPORT_PATH}')
    print(f'Совпадают: {len(matched_ok)} | Расхождения: {len(mismatches)} | '
          f'Нет в авто (есть на сайте): {len(missing_in_auto)} | Не найдены: {len(no_object)} | '
          f'Категория неясна: {len(no_category)} | Цены-2027: {len(early_2027)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
