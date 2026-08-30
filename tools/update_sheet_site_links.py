#!/usr/bin/env python3
"""Автоподстановка ссылок сайта в столбец «Сайт» таблицы «БАЗА - отели и квартиры».

Вкладка СОЦСЕТИ, столбец H. Для каждой видимой строки, чьё название совпадает
с объектом каталога (data/catalog-index.json), в H должна стоять ссылка вида
`abhazbereg.ru/<путь-страницы>/` — латиницей, без протокола (домен abhazbereg.ru
переадресует на абхазберег.рф с сохранением пути). Обновляются только ячейки,
где значение отличается от актуального.

Не трогаем (правило 9 CLAUDE.md): скрытые строки и строки с заливкой в красных
оттенках — эти объекты Дарья не ведёт. Также пропускаем строки без однозначного
соответствия каталогу (объект снят с сайта или назван иначе) — они попадают в отчёт.

Запуск: python tools/update_sheet_site_links.py [--dry-run]
Ключ Google — как у других скриптов: env GOOGLE_SERVICE_ACCOUNT_JSON,
google-service-account.json в корне репо или ключ в Downloads на Mac.
"""

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
LINK_HOST = 'abhazbereg.ru'
CATALOG_INDEX = ROOT / 'data' / 'catalog-index.json'


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


def load_catalog():
    data = json.loads(CATALOG_INDEX.read_text(encoding='utf-8'))
    by_norm, by_qname = {}, {}
    for item in data['listings']:
        path = item['page_url'].split('абхазберег.рф', 1)[-1]
        if not path.endswith('/'):
            path += '/'
        link = LINK_HOST + path
        by_norm.setdefault(norm(item['title']), link)
        qname = quoted_name(item['title'])
        if qname:
            by_qname.setdefault(qname, []).append(link)
    return by_norm, by_qname


def fetch_rows(service):
    fields = ('sheets(data(rowMetadata(hiddenByUser,hiddenByFilter),'
              'rowData(values(formattedValue,effectiveFormat(backgroundColor)))))')
    resp = service.spreadsheets().get(
        spreadsheetId=SPREADSHEET_ID,
        ranges=[f"'{TAB}'!A1:H1500"],
        includeGridData=True,
        fields=fields,
    ).execute()
    data = resp['sheets'][0]['data'][0]
    return data.get('rowMetadata', []), data.get('rowData', [])


def main() -> int:
    parser = argparse.ArgumentParser(description='Автоссылки abhazbereg.ru в столбце «Сайт» таблицы БАЗА.')
    parser.add_argument('--dry-run', action='store_true', help='только показать, ничего не записывать')
    args = parser.parse_args()

    creds = service_account.Credentials.from_service_account_file(
        str(pick_google_credentials_path()),
        scopes=['https://www.googleapis.com/auth/spreadsheets'])
    service = build('sheets', 'v4', credentials=creds, cache_discovery=False)

    by_norm, by_qname = load_catalog()
    rows_meta, rows = fetch_rows(service)

    updates, unmatched = [], []
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

        link = by_norm.get(norm(name))
        if not link:
            candidates = by_qname.get(quoted_name(name) or '', [])
            if len(candidates) == 1:
                link = candidates[0]
        if not link:
            unmatched.append((row_no, name))
            continue

        current = ''
        if len(values) > SITE_COL_INDEX:
            current = (values[SITE_COL_INDEX].get('formattedValue') or '').strip()
        if current != link:
            updates.append({'range': f'{TAB}!H{row_no}', 'values': [[link]]})
            print(f'  H{row_no} {name[:45]!r}: {current or "(пусто)"} → {link}')

    print(f'Строк к обновлению: {len(updates)}; без соответствия каталогу: {len(unmatched)}')
    for row_no, name in unmatched:
        print(f'  нет на сайте / неоднозначно: r{row_no} {name[:60]!r}')

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
