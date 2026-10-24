#!/usr/bin/env python3
"""Опись всех вкладок и столбцов таблицы «БАЗА — отели и квартиры» — ТОЛЬКО ЧТЕНИЕ, без значений ячеек.

По каждому столбцу: буква, заголовок, скрыт ли; строк с данными (всего / видимых и не
красных / скрытых или красных); непустых ячеек в обеих группах; типы значений; гиперссылки
(через «вставить ссылку», через HYPERLINK(), ячейки с несколькими ссылками) и их ДОМЕНЫ
с числом — без самих адресов; примечания; функции формул. Печатает Markdown.

В вывод не попадает ни одно значение ячейки — только заголовки, количества и домены.
Комментарии (не примечания) Sheets API не отдаёт: их считает Drive API — см. --comments.

Запуск: python3 tools/inventory_base_sheet.py > опись.md
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
from update_sheet_site_links import SPREADSHEET_ID, is_reddish, pick_google_credentials_path  # noqa: E402

from google.oauth2 import service_account  # noqa: E402
from googleapiclient.discovery import build  # noqa: E402

URL_RE = re.compile(r'(?:https?://|www\.)[^\s"\'<>)]+|\b[a-z0-9.-]+\.(?:ru|com|me|cc|net|org|рф|online|ly|link)/[^\s"\'<>)]*', re.I)
FUNC_RE = re.compile(r'([A-Z][A-Z0-9.]*)\(')


def col_letter(i: int) -> str:
    s = ''
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def domain(url: str) -> str:
    u = url if '://' in url else 'https://' + url
    try:
        parts = urlsplit(u)
    except ValueError:
        return '(битая)'
    host = (parts.hostname or '').lower().removeprefix('www.')
    path = parts.path.strip('/').split('/')
    # для карт важен раздел, не только домен
    if host in ('yandex.ru', 'yandex.com') and path and path[0] in ('maps', 'map'):
        return host + '/maps'
    if host in ('google.com', 'google.ru') and path and path[0] == 'maps':
        return host + '/maps'
    if host == 'goo.gl' and path and path[0] == 'maps':
        return 'goo.gl/maps'
    return host or '(без домена)'


def cell_links(cell: dict) -> tuple[list[str], int, int]:
    """(ссылки, через «вставить ссылку», через HYPERLINK) — адреса только для подсчёта доменов."""
    links, inserted, formula = [], 0, 0
    if cell.get('hyperlink'):
        links.append(cell['hyperlink'])
        inserted += 1
    for run in cell.get('textFormatRuns') or []:
        uri = ((run.get('format') or {}).get('link') or {}).get('uri')
        if uri and uri not in links:
            links.append(uri)
            inserted += 1
    f = (cell.get('userEnteredValue') or {}).get('formulaValue') or ''
    if 'HYPERLINK' in f.upper():
        formula += 1
        links += [m for m in URL_RE.findall(f) if m not in links]
    text = cell.get('formattedValue') or ''
    for m in URL_RE.findall(text):
        if m not in links and not any(m in l or l in m for l in links):
            links.append(m)
    return links, inserted, formula


def value_type(cell: dict) -> str | None:
    uev = cell.get('userEnteredValue') or {}
    if 'formulaValue' in uev:
        return 'формула'
    if (cell.get('dataValidation') or {}).get('condition', {}).get('type') == 'BOOLEAN' or 'boolValue' in uev:
        return 'флажок'
    if 'numberValue' in uev:
        nf = ((cell.get('effectiveFormat') or {}).get('numberFormat') or {}).get('type', '')
        return 'дата' if nf in ('DATE', 'DATE_TIME', 'TIME') else 'число'
    if 'stringValue' in uev or cell.get('formattedValue'):
        return 'текст'
    return None


def inventory(service) -> tuple[str, list[str]]:
    meta = service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID, fields='properties.title,sheets.properties').execute()
    title = meta['properties']['title']
    sheet_titles = [s['properties']['title'] for s in meta['sheets']]
    out = [f'Таблица: «{title}», вкладок: {len(sheet_titles)}', '']
    totals = Counter()
    fields = ('sheets(properties(title,gridProperties),data(columnMetadata(hiddenByUser),'
              'rowMetadata(hiddenByUser,hiddenByFilter),rowData(values(formattedValue,userEnteredValue,'
              'hyperlink,note,textFormatRuns(format(link)),dataValidation(condition(type)),'
              'effectiveFormat(backgroundColor,numberFormat(type))))))')
    for st in sheet_titles:
        resp = service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID, ranges=[f"'{st}'"],
                                          includeGridData=True, fields=fields).execute()
        sheet = resp['sheets'][0]
        grid = sheet['properties'].get('gridProperties', {})
        data = (sheet.get('data') or [{}])[0]
        rows = data.get('rowData', [])
        rmeta = data.get('rowMetadata', [])
        cmeta = data.get('columnMetadata', [])
        ncols = max([len(r.get('values', [])) for r in rows] + [0])
        header = rows[0].get('values', []) if rows else []
        # строки с данными (без шапки): видимые и не красные / скрытые или красные
        body = []
        for i, r in enumerate(rows[1:], start=1):
            vals = r.get('values', [])
            if not any(v.get('formattedValue') or v.get('userEnteredValue') for v in vals):
                continue
            hidden = bool((rmeta[i] if i < len(rmeta) else {}).get('hiddenByUser') or
                          (rmeta[i] if i < len(rmeta) else {}).get('hiddenByFilter'))
            red = is_reddish(((vals[0] if vals else {}).get('effectiveFormat') or {}).get('backgroundColor'))
            body.append((vals, hidden or red))
        vis_rows = sum(1 for _, off in body if not off)
        off_rows = sum(1 for _, off in body if off)
        out += [f'## Вкладка «{st}»', '',
                f'Сетка {grid.get("rowCount", "?")}×{grid.get("columnCount", "?")}; строк с данными {len(body)} '
                f'(видимых и не красных {vis_rows}, скрытых или красных {off_rows}); столбцов с данными {ncols}.', '',
                '| Ст. | Заголовок | Скрыт | Непустых: видимых / скрытых-красных | Типы | Ссылок (вставка / HYPERLINK / неск. в ячейке) | Домены | Примечаний | Функции формул |',
                '|---|---|---|---|---|---|---|---|---|']
        seen_headers = Counter()
        for c in range(ncols):
            h = (header[c].get('formattedValue') if c < len(header) else '') or ''
            h = re.sub(r'\s+', ' ', h).strip().replace('|', '/')
            # Первая строка бывает не заголовком, а данными (заметка, ник, телефон) — такое не печатаем.
            if len(h) > 60 or re.search(r'@|\d{6,}|https?://|www\.|\.(ru|com|me|cc)\b', h, re.I):
                h = f'(в первой строке не заголовок, а текст: {len(h)} зн. — не показан)'
            seen_headers[h] += 1
            hidden_col = bool((cmeta[c] if c < len(cmeta) else {}).get('hiddenByUser'))
            nv = no = 0
            types, doms, funcs = Counter(), Counter(), Counter()
            ins = frm = multi = nlinks = notes = 0
            for vals, off in body:
                cell = vals[c] if c < len(vals) else {}
                t = value_type(cell)
                if t:
                    types[t] += 1
                    if off:
                        no += 1
                    else:
                        nv += 1
                if cell.get('note'):
                    notes += 1
                links, i_, f_ = cell_links(cell)
                ins += i_
                frm += f_
                nlinks += len(links)
                multi += len(links) > 1
                for l in links:
                    doms[domain(l)] += 1
                for fn in FUNC_RE.findall((cell.get('userEnteredValue') or {}).get('formulaValue') or ''):
                    funcs[fn] += 1
            label = h or '(без заголовка)'
            if seen_headers[h] > 1 and h:
                label += f' (повтор {seen_headers[h]})'
            out.append(
                f'| {col_letter(c)} | {label} | {"да" if hidden_col else ""} | {nv} / {no} | '
                f'{", ".join(f"{k} {v}" for k, v in types.most_common()) or "—"} | '
                f'{nlinks} ({ins} / {frm} / {multi}) | '
                f'{", ".join(f"{k} {v}" for k, v in doms.most_common(8)) or "—"} | {notes or ""} | '
                f'{", ".join(f"{k} {v}" for k, v in funcs.most_common(4)) or ""} |')
            totals['столбцов'] += 1
            totals['без заголовка'] += not h
            totals['только формулы'] += bool(types) and set(types) == {'формула'}
            if any(d.endswith('/maps') or d in ('2gis.ru', 'go.2gis.com', 'yandex.ru/maps') for d in doms):
                totals['с картами'] += 1
            if any(d in ('vk.com', 'vk.cc', 't.me', 'instagram.com', 'max.ru', 'ok.ru', 'dzen.ru', 'youtube.com',
                         'rutube.ru', 'avito.ru') for d in doms):
                totals['с соцсетями/площадками'] += 1
            if any('abhazbereg' in d or 'xn--80aacbklan7f0b' in d for d in doms):
                totals['с сайтом'] += 1
        out.append('')
    out += ['## Итог', '',
            f'- вкладок: {len(sheet_titles)}',
            f'- столбцов (с данными): {totals["столбцов"]}',
            f'- столбцов без заголовка: {totals["без заголовка"]}',
            f'- столбцов со ссылками на карты: {totals["с картами"]}',
            f'- столбцов со ссылками на соцсети и площадки: {totals["с соцсетями/площадками"]}',
            f'- столбцов со ссылками на наш сайт: {totals["с сайтом"]}',
            f'- столбцов только из формул: {totals["только формулы"]}']
    return title, out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--comments', action='store_true', help='посчитать комментарии файла через Drive API')
    args = parser.parse_args()
    creds = service_account.Credentials.from_service_account_file(
        str(pick_google_credentials_path()),
        scopes=['https://www.googleapis.com/auth/spreadsheets.readonly', 'https://www.googleapis.com/auth/drive.readonly'])
    service = build('sheets', 'v4', credentials=creds, cache_discovery=False)
    _, out = inventory(service)
    if args.comments:
        try:
            drive = build('drive', 'v3', credentials=creds, cache_discovery=False)
            n, token = 0, None
            while True:
                r = drive.comments().list(fileId=SPREADSHEET_ID, fields='nextPageToken,comments(id)',
                                          pageSize=100, pageToken=token, includeDeleted=False).execute()
                n += len(r.get('comments', []))
                token = r.get('nextPageToken')
                if not token:
                    break
            out.append(f'- комментариев в файле (Drive API, без привязки к столбцам): {n}')
        except Exception as e:  # noqa: BLE001
            out.append(f'- комментарии посчитать не удалось: {type(e).__name__}')
    print('\n'.join(out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
