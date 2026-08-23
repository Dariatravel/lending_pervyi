#!/usr/bin/env python3
"""Страницы снятых объектов → страницы-переезды.

Когда объект уходит из каталога (заменён новым постом или снят с ведения),
его страница должна не жить сама по себе, а отправлять гостя на актуальную
карточку или в каталог. Иногда такие страницы оставались полноценными:
закрыты от поисковиков и вне каталога, но по старой ссылке открывались —
и могли показывать устаревшие цены и битые файлы (23.08.2026 нашлось 18 штук).

Куда какая страница ведёт — в data/retired-redirects.json. Двойники ведут на
актуальную карточку того же объекта, объекты без замены — в каталог.

    python3 tools/apply_retired_redirects.py --check   # только показать
    python3 tools/apply_retired_redirects.py           # применить
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "retired-redirects.json"

# Формат страницы-переезда повторяет retire_replaced_listing из
# scripts/sync_catalog_from_telegram.py — чтобы все переезды выглядели одинаково.
STUB = """<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8"/>
<meta http-equiv="refresh" content="0;url={href}"/>
<link rel="canonical" href="https://абхазберег.рф{canonical}"/>
<meta name="robots" content="noindex"/>
<title>Страница переехала</title></head>
<body><p>Объект переехал: <a href="{href}">открыть актуальную страницу</a>.</p></body></html>
"""


def load_manifest() -> dict[str, str]:
    try:
        payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"Не читается {MANIFEST.name}: {error}")
        return {}
    redirects = payload.get("redirects")
    return {str(k): str(v) for k, v in redirects.items()} if isinstance(redirects, dict) else {}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="показать, что будет сделано, не меняя файлы")
    args = parser.parse_args()

    redirects = load_manifest()
    if not redirects:
        print("Список переездов пуст — делать нечего.")
        return 0

    made = skipped = missing = broken = 0
    for page_dir, href in sorted(redirects.items()):
        page = ROOT / page_dir / "index.html"
        if not page.is_file():
            print(f"  НЕТ СТРАНИЦЫ  {page_dir}")
            missing += 1
            continue

        # Ведёт ли переезд на существующую страницу: промахнуться адресом
        # хуже, чем оставить как есть.
        if href != "/#catalog":
            target = ROOT / href.strip("/") / "index.html"
            if not target.is_file():
                print(f"  ЦЕЛЬ НЕ НАЙДЕНА  {page_dir} → {href}")
                broken += 1
                continue

        current = page.read_text(encoding="utf-8")
        if 'http-equiv="refresh"' in current:
            skipped += 1
            continue

        # У переезда в каталог собственного адреса для canonical нет —
        # канонической становится главная.
        canonical = "/" if href == "/#catalog" else href
        if not args.check:
            page.write_text(STUB.format(href=href, canonical=canonical), encoding="utf-8")
        print(f"  {'будет переезд' if args.check else 'переезд'}  /{page_dir}/ → {href}")
        made += 1

    print(
        f"\nИтог: переездов {made}, уже были {skipped}, "
        f"страниц не найдено {missing}, целей не найдено {broken}"
    )
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
