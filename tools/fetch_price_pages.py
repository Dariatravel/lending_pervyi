#!/usr/bin/env python3
"""Съём цен со страниц отелей на внешних площадках (для сверки демпинга).

Запускается вручную из workflow price-probe.yml: получает список URL через
переменную окружения PROBE_URLS (по одному в строке), скачивает страницы с
браузерным User-Agent и печатает в лог строки, похожие на цены, с контекстом.
Ничего не сохраняет и не коммитит — результат читается из лога запуска.
"""
from __future__ import annotations

import os
import re
import sys

import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

PRICE_RX = re.compile(r"(\d[\d\s ]{2,9})\s*(?:₽|руб)", re.IGNORECASE)
KEYWORD_RX = re.compile(r"цен|стоимост|сутки|ночь|номер|август|сентябр|заезд|питани", re.IGNORECASE)


def visible_text(html: str) -> list[str]:
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text = soup.get_text("\n")
    except Exception:  # noqa: BLE001 — без bs4 грубая чистка тегов
        text = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", html, flags=re.I)
        text = re.sub(r"<[^>]+>", "\n", text)
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in text.splitlines()]
    return [ln for ln in lines if ln]


def dump_price_tables(html: str) -> int:
    """Ценовые таблицы страницы целиком: «ячейка | ячейка | …» построчно.
    Возвращает число напечатанных таблиц."""
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
    except Exception:  # noqa: BLE001
        return 0
    shown = 0
    for table in soup.find_all("table"):
        text = table.get_text(" ")
        if not PRICE_RX.search(text):
            continue
        shown += 1
        print(f"  [ТАБЛИЦА {shown}]")
        for tr in table.find_all("tr")[:50]:
            cells = [re.sub(r"\s+", " ", c.get_text(" ")).strip() for c in tr.find_all(["td", "th"])]
            cells = [c for c in cells if c]
            if cells:
                print("   | " + " | ".join(c[:60] for c in cells)[:300])
        if shown >= 4:
            break
    return shown


def probe(url: str) -> None:
    print(f"\n{'=' * 80}\nURL: {url}")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=40, allow_redirects=True)
    except Exception as error:  # noqa: BLE001
        print(f"STATUS: FETCH-ERROR {error}")
        return
    print(f"STATUS: {resp.status_code} FINAL-URL: {resp.url} BYTES: {len(resp.content)}")
    if resp.status_code != 200:
        return
    resp.encoding = resp.apparent_encoding or resp.encoding
    tables = dump_price_tables(resp.text)
    if tables:
        return
    lines = visible_text(resp.text)
    shown = 0
    for i, line in enumerate(lines):
        if not PRICE_RX.search(line) and not (KEYWORD_RX.search(line) and len(line) < 120):
            continue
        # цена интересна вместе с соседней строкой-подписью
        context = lines[i - 1] if i > 0 and len(lines[i - 1]) < 100 else ""
        out = f"{context} | {line}" if context and context != line else line
        print(f"  {out[:240]}")
        shown += 1
        if shown >= 120:
            print("  ... (обрезано, 120 строк)")
            break
    if not shown:
        print("  (строк с ценами не найдено — вероятно, цены рисуются скриптом)")


def main() -> int:
    urls = [u.strip() for u in os.environ.get("PROBE_URLS", "").splitlines() if u.strip()]
    if not urls:
        print("PROBE_URLS пуст — нечего проверять.", file=sys.stderr)
        return 1
    for url in urls[:40]:
        probe(url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
