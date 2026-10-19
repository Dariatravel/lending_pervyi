#!/usr/bin/env python3
"""Проверка ссылок столбца «Сайт» таблицы «БАЗА» (вкладка СОЦСЕТИ, H): каждая доводит до страницы объекта?

Старые ссылки (abhazbereg.ru/<ключ>) уже разосланы — они обязаны работать дальше
(Дарья 19.10.2026: ссылки не удалять). Идём по всей цепочке: HTTP-переадресации,
затем страницы-переходники (meta refresh / location.replace), пока не откроется
настоящая страница на абхазберег.рф. Скрипт ничего не меняет.

Запуск: python3 tools/check_sheet_site_links.py            # ссылки из таблицы
        python3 tools/check_sheet_site_links.py --urls f.txt # ссылки из файла (по одной в строке)
"""
from __future__ import annotations

import argparse
import re
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

SITE_HOSTS = ("xn--80aacbklan7f0b.xn--p1ai", "абхазберег.рф")
REAL_PATH = re.compile(r"/(hotels|kvartira|podborki|blog)/[^/]+/?$")
HOP_RE = re.compile(r'http-equiv=["\']refresh["\'][^>]*url=([^"\'>\s]+)|location\.replace\(["\']([^"\']+)["\']', re.I)


def fetch(url: str) -> tuple[int, str, str]:
    # Как браузер: сокращатели (clck.ru) неизвестным клиентам отвечают 404.
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Macintosh) abhazbereg-link-check/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            return resp.status, resp.geturl(), resp.read(6000).decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as e:
        return e.code, url, ""


def check(url: str) -> tuple[str, str]:
    current = url if url.startswith("http") else f"https://{url}"
    for _ in range(5):
        try:
            status, final, body = fetch(current)
        except Exception as e:  # noqa: BLE001
            return url, f"ошибка: {type(e).__name__}"
        if status != 200:
            return url, f"HTTP {status} на {final[:70]}"
        hop = HOP_RE.search(body)
        if hop:
            target = hop.group(1) or hop.group(2)
            current = target if target.startswith("http") else urllib.parse.urljoin(final, target)
            continue
        if any(h in final for h in SITE_HOSTS) and REAL_PATH.search(final.split("?")[0]):
            return url, "ок"
        return url, f"открылось не то: {final[:70]}"
    return url, "слишком длинная цепочка"


def sheet_links() -> dict[str, list[int]]:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    from update_sheet_site_links import SITE_COL_INDEX, fetch_rows, pick_google_credentials_path

    creds = service_account.Credentials.from_service_account_file(
        str(pick_google_credentials_path()), scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"])
    service = build("sheets", "v4", credentials=creds, cache_discovery=False)
    _, rows = fetch_rows(service)
    links: dict[str, list[int]] = {}
    for i, row in enumerate(rows):
        values = row.get("values", [])
        if i and len(values) > SITE_COL_INDEX:
            v = (values[SITE_COL_INDEX].get("formattedValue") or "").strip()
            if v:
                links.setdefault(v, []).append(i + 1)
    return links


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--urls", help="файл со ссылками (по одной в строке) вместо таблицы")
    args = parser.parse_args()
    if args.urls:
        links = {u.strip(): [n + 1] for n, u in enumerate(Path(args.urls).read_text(encoding="utf-8").splitlines()) if u.strip()}
    else:
        links = sheet_links()
    print(f"ссылок: {len(links)} уникальных")
    with ThreadPoolExecutor(8) as pool:
        results = list(pool.map(check, links))
    bad = [(u, r) for u, r in results if r != "ок"]
    print(f"работают: {len(results) - len(bad)}, не работают: {len(bad)}")
    for u, r in bad:
        print(f"  НЕ РАБОТАЕТ (строки {links[u][:5]}): {u} — {r}")
    return 1 if bad else 0


if __name__ == "__main__":
    import urllib.parse  # noqa: E402

    sys.exit(main())
