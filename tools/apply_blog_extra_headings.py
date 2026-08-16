#!/usr/bin/env python3
"""Вставка SEO-подзаголовков (заголовок = поисковый запрос + абзац-ответ)
в статьи блога из data/blog-extra-headings.json.

Идемпотентно: блоки помечены data-extra-heading, повторный запуск ничего
не дублирует. После пересинка поста из Telegram скрипт нужно прогнать
повторно — правки вернутся.

Позиции: intro — после первого абзаца тела; mid — перед серединным
существующим <h2> тела (либо перед серединным абзацем); end — перед
абзацем «Источник: …».

    python3 tools/apply_blog_extra_headings.py            # применить
    python3 tools/apply_blog_extra_headings.py --dry-run  # только отчёт
"""
from __future__ import annotations

import html as html_mod
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAP_PATH = ROOT / "data" / "blog-extra-headings.json"

BODY_START = 'blog-article__content'
SOURCE_RX = re.compile(r'<p[^>]*>\s*Источник:')


def render_block(item: dict) -> str:
    h = html_mod.escape(str(item["h"]))
    p = html_mod.escape(str(item["p"]))
    return (
        f'\n<h2 data-extra-heading="1">{h}</h2>\n'
        f'<p data-extra-heading="1">{p}</p>\n'
    )


def body_span(page: str) -> tuple[int, int] | None:
    """(start, end) содержимого div.blog-article__content (по балансу div)."""
    i = page.find(BODY_START)
    if i < 0:
        return None
    start = page.find('>', i) + 1
    depth = 1
    pos = start
    while depth and pos < len(page):
        m = re.search(r'<div\b|</div>', page[pos:])
        if not m:
            return None
        pos += m.end()
        depth += 1 if m.group(0) == '<div' else -1
    return start, pos - len('</div>')


def insert_at(page: str, idx: int, block: str) -> str:
    return page[:idx] + block + page[idx:]


def apply_to_page(page: str, items: list[dict]) -> tuple[str, int]:
    if 'data-extra-heading' in page:
        return page, 0
    span = body_span(page)
    if not span:
        return page, 0
    inserted = 0
    # Вставляем с конца, чтобы индексы не съезжали: end -> mid -> intro.
    order = {"end": 0, "mid": 1, "intro": 2}
    for item in sorted(items, key=lambda x: order.get(x.get("pos"), 3)):
        start, end = body_span(page)  # пересчёт после каждой вставки
        body = page[start:end]
        pos = item.get("pos")
        if pos == "end":
            m = SOURCE_RX.search(body)
            idx = start + (m.start() if m else len(body))
        elif pos == "mid":
            h2s = [m for m in re.finditer(r'<h2(?![^>]*data-extra)[^>]*>', body)]
            if h2s:
                idx = start + h2s[len(h2s) // 2].start()
            else:
                ps = list(re.finditer(r'<p[^>]*>', body))
                idx = start + (ps[len(ps) // 2].start() if len(ps) > 2 else len(body))
        else:  # intro — после первого закрытого абзаца тела
            m = re.search(r'</p>', body)
            idx = start + (m.end() if m else 0)
        page = insert_at(page, idx, render_block(item))
        inserted += 1
    return page, inserted


def main() -> int:
    dry = "--dry-run" in sys.argv
    mapping = json.loads(MAP_PATH.read_text(encoding="utf-8"))
    total_pages = total_blocks = skipped = 0
    for slug, items in mapping.items():
        if slug.startswith("_"):
            continue
        path = ROOT / "blog" / slug / "index.html"
        if not path.is_file():
            print(f"[нет страницы] {slug}")
            continue
        page = path.read_text(encoding="utf-8")
        new_page, n = apply_to_page(page, items)
        if n == 0:
            skipped += 1
            continue
        total_pages += 1
        total_blocks += n
        if not dry:
            path.write_text(new_page, encoding="utf-8")
    mode = "ПРОВЕРКА" if dry else "ПРИМЕНЕНО"
    print(f"{mode}: страниц {total_pages}, блоков {total_blocks}, пропущено (уже есть/нет тела): {skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
