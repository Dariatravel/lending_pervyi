#!/usr/bin/env python3
"""Перенести обложки (poster) видео из манифеста «Дополнительных обзоров» в страницы.

Манифест data/supplemental-blocks.json — источник истины для блоков, но в
страницы он попадает только при полном синке объекта из Telegram. Пересборка
из снапшота блоки не трогает, и обложки, прописанные в манифест инструментом
backfill-video-posters, до страниц не доходили (25.09.2026: 58 видео без
poster при полном манифесте).

Правка точечная: для каждого <video> без poster, чей <source src> есть в
манифесте с обложкой, добавляется атрибут poster. Остальной HTML страницы
не переформатируется (BeautifulSoup здесь намеренно не используется — он
переписывает кавычки и теги по всей странице). Идемпотентно.

    python3 tools/apply_supplemental_to_pages.py [--dry-run]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from supplemental_store import load_manifest  # noqa: E402

VIDEO_WITH_SOURCE = re.compile(
    r'(<video\b[^>]*?)(\s*/?>)(\s*<source\s+src="([^"]+\.mp4)"[^>]*>)', re.I
)


def poster_map(section_html: str) -> dict[str, str]:
    """src видео → URL обложки из section_html манифеста."""
    result: dict[str, str] = {}
    for match in VIDEO_WITH_SOURCE.finditer(section_html):
        head, src = match.group(1), match.group(4)
        poster = re.search(r'poster="([^"]+)"', head)
        if poster:
            result[src] = poster.group(1)
    return result


def page_for(slug: str, kind: str) -> Path | None:
    order = ["kvartira", "hotels"] if kind == "kvartira" else ["hotels", "kvartira"]
    for folder in order:
        path = ROOT / folder / slug / "index.html"
        if path.is_file():
            return path
    return None


def add_posters(page_html: str, posters: dict[str, str]) -> tuple[str, int]:
    added = 0

    def repl(match: re.Match) -> str:
        nonlocal added
        head, close, source, src = match.groups()
        if 'poster="' in head or src not in posters:
            return match.group(0)
        added += 1
        return f'{head} poster="{posters[src]}"{close}{source}'

    return VIDEO_WITH_SOURCE.sub(repl, page_html), added


def main() -> int:
    parser = argparse.ArgumentParser(description="Обложки видео из манифеста → страницы.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    manifest = load_manifest()
    pages_changed = posters_added = missing = 0
    for slug, section in manifest.items():
        if not isinstance(section, dict):
            continue
        posters = poster_map(str(section.get("section_html") or ""))
        if not posters:
            continue
        page = page_for(slug, str(section.get("kind") or ""))
        if page is None:
            missing += 1
            print(f"  нет страницы: {slug}")
            continue
        original = page.read_text(encoding="utf-8")
        updated, added = add_posters(original, posters)
        if not added:
            continue
        pages_changed += 1
        posters_added += added
        print(f"  {page.relative_to(ROOT)}: обложек добавлено {added}")
        if not args.dry_run:
            page.write_text(updated, encoding="utf-8")
    print(f"Страниц изменено: {pages_changed} | обложек добавлено: {posters_added} | без страницы: {missing}"
          + (" (пробный прогон)" if args.dry_run else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
