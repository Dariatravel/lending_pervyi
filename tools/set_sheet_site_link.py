#!/usr/bin/env python3
"""Записать одну ссылку в столбец «Сайт» (H) вкладки СОЦСЕТИ таблицы «БАЗА» — точечная правка руками.

Показывает название строки и текущее значение, пишет только с --apply.
Запуск: python3 tools/set_sheet_site_link.py <номер строки> <ссылка> [--apply]
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from update_sheet_site_links import SPREADSHEET_ID, TAB, pick_google_credentials_path  # noqa: E402

from google.oauth2 import service_account  # noqa: E402
from googleapiclient.discovery import build  # noqa: E402


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    row, link, apply = int(sys.argv[1]), sys.argv[2], '--apply' in sys.argv
    creds = service_account.Credentials.from_service_account_file(
        str(pick_google_credentials_path()), scopes=['https://www.googleapis.com/auth/spreadsheets'])
    service = build('sheets', 'v4', credentials=creds, cache_discovery=False)
    got = service.spreadsheets().values().batchGet(
        spreadsheetId=SPREADSHEET_ID, ranges=[f"'{TAB}'!A{row}", f"'{TAB}'!H{row}"]).execute()
    name = (got['valueRanges'][0].get('values') or [['']])[0][0]
    current = (got['valueRanges'][1].get('values') or [['']])[0][0]
    print(f'H{row} {name[:60]!r}: {current or "(пусто)"} → {link}')
    if not apply:
        print('сухой прогон — не записано (записать: --apply)')
        return 0
    service.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID, range=f"'{TAB}'!H{row}", valueInputOption='RAW',
        body={'values': [[link]]}).execute()
    print('записано')
    return 0


if __name__ == '__main__':
    sys.exit(main())
