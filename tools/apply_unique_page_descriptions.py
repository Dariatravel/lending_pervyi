#!/usr/bin/env python3
"""Уникализация meta description на страницах объектов.

У соседних объектов совпадают город, расстояние до пляжа и вместимость, из-за
чего описания получались одинаковыми, а Яндекс склеивал такие страницы как
дубли. Скрипт дописывает в начало описания название объекта (из <h1>).

Генераторы уже формируют описание правильно; этот проход нужен, чтобы не
пересобирать весь каталог ради одной строки в <head>.

Запуск:
    python3 tools/apply_unique_page_descriptions.py [--check]
"""
from __future__ import annotations

import argparse
import html as html_mod
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SECTIONS = ("hotels", "kvartira")

H1_RX = re.compile(r"<h1[^>]*>(.*?)</h1>", re.S | re.I)
ROBOTS_NOINDEX_RX = re.compile(r'<meta[^>]*name="robots"[^>]*noindex|<meta[^>]*noindex[^>]*name="robots"', re.I)
# Часть страниц прошла через нормализацию HTML, где атрибуты меняются местами
# (content раньше name), поэтому ловим оба порядка записи.
DESC_RX = re.compile(
    r'<meta\s+name="description"\s+content="([^"]*)"[^>]*>'
    r'|<meta\s+content="([^"]*)"\s+name="description"[^>]*>', re.I
)
OG_DESC_RX = re.compile(
    r'<meta\s+property="og:description"\s+content="([^"]*)"[^>]*>'
    r'|<meta\s+content="([^"]*)"\s+property="og:description"[^>]*>', re.I
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="ничего не записывать")
    args = parser.parse_args()

    changed = 0
    for section in SECTIONS:
        for path in sorted((ROOT / section).glob("*/index.html")):
            text = path.read_text(encoding="utf-8")
            if ROBOTS_NOINDEX_RX.search(text):  # редиректы и скрытые страницы
                continue
            h1 = H1_RX.search(text)
            desc = DESC_RX.search(text)
            if not h1 or not desc:
                continue
            title = html_mod.unescape(re.sub(r"<[^>]+>", "", h1.group(1))).strip()
            current = html_mod.unescape(desc.group(1) or desc.group(2) or "").strip()
            if not title or not current or current.lower().startswith(title.lower()):
                continue
            merged = html_mod.escape(f"{title}. {current}", quote=True)
            old_value = desc.group(1) or desc.group(2)

            def swap(match: re.Match) -> str:
                value = match.group(1) or match.group(2) or ""
                return match.group(0).replace(f'"{value}"', f'"{merged}"', 1) if value == old_value else match.group(0)

            updated = DESC_RX.sub(swap, text, count=1)
            updated = OG_DESC_RX.sub(swap, updated, count=1)
            if updated == text:
                continue
            changed += 1
            if not args.check:
                path.write_text(updated, encoding="utf-8")
    print(f"Страниц обновлено: {changed}{' (проверка, без записи)' if args.check else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
