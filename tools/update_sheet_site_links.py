#!/usr/bin/env python3
"""Автоподстановка ссылок сайта в столбец «Сайт» таблицы «БАЗА - отели и квартиры».

Вкладка СОЦСЕТИ, столбец H. Для каждой видимой строки, чьё название совпадает
с объектом каталога (data/catalog-index.json), в H должна стоять короткая ссылка
`abhazbereg.com/<ключ>` — та же, что в `short_url` каталога (её считает сайт:
ручной ключ из data/short-links.json главнее автоматического). Если короткой ещё
нет — полная `abhazbereg.com/<путь-страницы>/`; когда короткая появится, ячейка
обновится сама. Домен латиницей (решение Дарьи 19.10.2026), без протокола:
abhazbereg.com переадресует на абхазберег.рф с сохранением пути и меток.
Прежние ссылки abhazbereg.ru/<ключ> продолжают работать — их никто не удаляет.
Обновляются только ячейки, где значение отличается от актуального.

Не трогаем (правило 9 CLAUDE.md): скрытые строки и строки с заливкой в красных
оттенках — эти объекты Дарья не ведёт. Также пропускаем строки без однозначного
соответствия каталогу (объект снят с сайта или назван иначе) — они попадают в отчёт.

Запуск: python tools/update_sheet_site_links.py [--dry-run]
Ключ Google — как у других скриптов: env GOOGLE_SERVICE_ACCOUNT_JSON,
google-service-account.json в корне репо или ключ в Downloads на Mac.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build

ROOT = Path(__file__).resolve().parents[1]
SPREADSHEET_ID = '135fxeZX5OE30rH3Sg5KWpTR4VuhBntCzGrTk0WcdTBY'
TAB = 'СОЦСЕТИ'
SITE_COL_INDEX = 7  # H
LINK_HOST = 'abhazbereg.com'
# Наши домены в старых ячейках: ссылку на них переводим на LINK_HOST, чужие не трогаем.
OUR_HOSTS = r'(?:www\.)?(?:abhazbereg\.ru|abhazbereg\.com|абхазберег\.рф|xn--80aacbklan7f0b\.xn--p1ai)'
CATALOG_INDEX = ROOT / 'data' / 'catalog-index.json'
SHORT_LINKS = ROOT / 'data' / 'short-links.json'
SHORT_LINKS_GENERATED = ROOT / 'data' / 'short-links-generated.json'


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


def norm(text: str) -> str:
    text = text.lower().replace('ё', 'е')
    text = re.sub(r'[«»"\'“”()!,./–—-]', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def quoted_name(text: str):
    match = re.search(r'["«“]([^"»”]+)["»”]', text)
    return norm(match.group(1)) if match else None


def is_reddish(bg) -> bool:
    if not bg:
        return False
    return bg.get('red', 0) > 0.75 and bg.get('green', 0) < 0.72 and bg.get('blue', 0) < 0.72


def with_slash(path: str) -> str:
    return path if path.endswith('/') else path + '/'


def load_short_keys():
    """Путь страницы → ключ короткой ссылки (abhazbereg.ru/<ключ>)."""
    path_to_key = {}
    for source in (SHORT_LINKS_GENERATED, SHORT_LINKS):  # ручные перекрывают автоматические
        if not source.exists():
            continue
        data = json.loads(source.read_text(encoding='utf-8'))
        for key, target in data.get('links', data).items():
            if key.startswith('_') or not isinstance(target, str):
                continue
            if source is SHORT_LINKS_GENERATED:
                path_to_key.setdefault(with_slash(target), key)
            else:
                path_to_key[with_slash(target)] = key
    return path_to_key


def shorten_existing(current: str, short_keys: dict, promo_keys: set | None = None):
    """Наш домен/<полный путь>/ → LINK_HOST/<ключ>; старый домен/<ключ> → LINK_HOST/<ключ>.
    Ключ страницы-акции в строке объекта — не «уже короткая», а ошибка: строка идёт в отчёт."""
    match = re.fullmatch(r'(?:https?://)?' + OUR_HOSTS + r'(/[^?#\s]+)', current)
    if not match:
        return None
    key_part = match.group(1).strip('/')
    if key_part in (promo_keys or set()):
        return None
    if key_part in short_keys.values():  # уже короткая — только домен
        return f'{LINK_HOST}/{key_part}'
    key = short_keys.get(with_slash(match.group(1)))
    return f'{LINK_HOST}/{key}' if key else None


def short_link_of(item: dict, short_keys: dict, path: str) -> str:
    """Короткая ссылка объекта: short_url каталога (его считает сайт), иначе реестры, иначе полный путь."""
    short_url = str(item.get('short_url') or '')
    match = re.fullmatch(r'https://abhazbereg\.com/([a-z0-9-]+)', short_url)
    if match:
        return f'{LINK_HOST}/{match.group(1)}'
    key = short_keys.get(path)
    return f'{LINK_HOST}/{key}' if key else LINK_HOST + path


PROMO_TITLE = re.compile(r'^\s*(новый год|спецпредложение|акция|скидк)', re.I)


def is_promo(item: dict) -> bool:
    """Страница-акция («НОВЫЙ ГОД В «ГРАСС»…», «СПЕЦПРЕДЛОЖЕНИЕ…»): это не объект.
    В таблице БАЗА строки — объекты, поэтому акции в кандидаты не идут (ревью 19.10.2026:
    «ГРАСС» коттеджи получили ссылку на новогодний пост)."""
    return bool(PROMO_TITLE.match(item.get('title') or ''))


def load_catalog():
    data = json.loads(CATALOG_INDEX.read_text(encoding='utf-8'))
    short_keys = load_short_keys()
    by_norm, by_qname, promo_keys = {}, {}, set()
    for item in data['listings']:
        path = with_slash(item['page_url'].split('абхазберег.рф', 1)[-1])
        link = short_link_of(item, short_keys, path)
        by_norm.setdefault(norm(item['title']), link)
        if is_promo(item):
            promo_keys.add(link.split('/', 1)[1].strip('/'))
            continue
        qname = quoted_name(item['title'])
        if qname:
            by_qname.setdefault(qname, []).append(link)
    return by_norm, by_qname, promo_keys


def is_our_link(value: str) -> bool:
    return not value or bool(re.match(r'(?:https?://)?' + OUR_HOSTS + r'(/|$)', value))


def fetch_rows(service):
    fields = ('sheets(data(rowMetadata(hiddenByUser,hiddenByFilter),'
              'rowData(values(formattedValue,effectiveFormat(backgroundColor)))))')
    # Только название (A) и «Сайт» (H): контакты и прочие столбцы не читаем.
    resp = service.spreadsheets().get(
        spreadsheetId=SPREADSHEET_ID,
        ranges=[f"'{TAB}'!A1:A1500", f"'{TAB}'!H1:H1500"],
        includeGridData=True,
        fields=fields,
    ).execute()
    col_a, col_h = resp['sheets'][0]['data'][0], resp['sheets'][0]['data'][1]
    rows_a, rows_h = col_a.get('rowData', []), col_h.get('rowData', [])
    rows = []
    for i in range(max(len(rows_a), len(rows_h))):
        a = (rows_a[i].get('values') or [{}])[0] if i < len(rows_a) else {}
        h = (rows_h[i].get('values') or [{}])[0] if i < len(rows_h) else {}
        rows.append({'values': [a] + [{}] * (SITE_COL_INDEX - 1) + [h]})
    return col_a.get('rowMetadata', []), rows


def main() -> int:
    parser = argparse.ArgumentParser(description='Автоссылки abhazbereg.ru в столбце «Сайт» таблицы БАЗА.')
    parser.add_argument('--dry-run', action='store_true', help='только показать, ничего не записывать')
    parser.add_argument('--replace-foreign', action='store_true',
                        help='заменять и чужие ссылки (clck.ru, t.me…); по умолчанию они только в отчёте')
    args = parser.parse_args()

    creds = service_account.Credentials.from_service_account_file(
        str(pick_google_credentials_path()),
        scopes=['https://www.googleapis.com/auth/spreadsheets'])
    service = build('sheets', 'v4', credentials=creds, cache_discovery=False)

    by_norm, by_qname, promo_keys = load_catalog()
    short_keys = load_short_keys()
    rows_meta, rows = fetch_rows(service)

    updates, unmatched, foreign = [], [], []
    for i, row in enumerate(rows):
        row_no = i + 1
        if row_no == 1:
            continue
        values = row.get('values', [])
        name_cell = values[0] if values else {}
        name = (name_cell.get('formattedValue') or '').strip()
        if not name:
            continue
        meta = rows_meta[i] if i < len(rows_meta) else {}
        if meta.get('hiddenByUser') or meta.get('hiddenByFilter'):
            continue
        if is_reddish(name_cell.get('effectiveFormat', {}).get('backgroundColor')):
            continue

        current = ''
        if len(values) > SITE_COL_INDEX:
            current = (values[SITE_COL_INDEX].get('formattedValue') or '').strip()

        link = by_norm.get(norm(name))
        if not link:
            candidates = by_qname.get(quoted_name(name) or '', [])
            if len(candidates) == 1:
                link = candidates[0]
        if not link:
            # Название не узнали, но в ячейке уже полная ссылка на страницу сайта —
            # меняем её на короткую, если она есть.
            link = shorten_existing(current, short_keys, promo_keys)
        if not link:
            unmatched.append((row_no, name))
            continue
        # Чужую ссылку (clck.ru, t.me, avito…) не затираем молча: ссылки не удаляем
        # (Дарья 19.10.2026) — такие строки в отдельный отчёт, замена только с --replace-foreign.
        if not is_our_link(current) and not args.replace_foreign:
            foreign.append((row_no, name, current, link))
            continue

        if current != link:
            updates.append({'range': f'{TAB}!H{row_no}', 'values': [[link]]})
            print(f'  H{row_no} {name[:45]!r}: {current or "(пусто)"} → {link}')

    print(f'Строк к обновлению: {len(updates)}; без соответствия каталогу: {len(unmatched)}; '
          f'чужая ссылка оставлена: {len(foreign)}')
    for row_no, name in unmatched:
        print(f'  нет на сайте / неоднозначно: r{row_no} {name[:60]!r}')
    for row_no, name, current, link in foreign:
        print(f'  чужая ссылка оставлена: r{row_no} {name[:45]!r}: {current} (наша была бы {link})')

    if updates and not args.dry_run:
        service.spreadsheets().values().batchUpdate(
            spreadsheetId=SPREADSHEET_ID,
            body={'valueInputOption': 'RAW', 'data': updates},
        ).execute()
        print(f'Записано ячеек: {len(updates)}')
    elif updates:
        print('dry-run: запись пропущена')
    return 0


if __name__ == '__main__':
    sys.exit(main())
