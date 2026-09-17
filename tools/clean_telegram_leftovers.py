#!/usr/bin/env python3
"""Разовая чистка телеграм-хвостов в уже опубликованных текстах сайта.

Фильтр scripts/telegram_line_filters.py чистит новые посты при сборке страниц.
Этот инструмент приводит в порядок то, что уже лежит на сайте: строки вида
«ОБЗОРЫ НОМЕРОВ ТУТ» (в Telegram «тут» было ссылкой), «Фото в комментариях»
и указатели-стрелки 👇 в готовых страницах и в data/catalog-snapshot.json,
чтобы при следующей пересборке они не вернулись.

    python3 tools/clean_telegram_leftovers.py --dry-run   # только показать
    python3 tools/clean_telegram_leftovers.py             # применить

Идемпотентно: повторный запуск ничего не меняет.
"""
from __future__ import annotations

import argparse
import html as html_mod
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from telegram_line_filters import POINTER_EMOJI, clean_line_for_site, strip_pointer_emoji  # noqa: E402

# Текст между тегами: добирает стрелки там, где абзац содержит вложенную разметку.
TEXT_NODE = re.compile(r">([^<>]+)<")
# Абзац с вложенной разметкой: <p …>текст<br/>текст</p>.
NESTED_PARA = re.compile(r"<p([^>]*)>((?:(?!</?p\b).)*?)</p>", re.S)
# Описание страницы в <meta …content="…"> — видно в поиске и превью ссылки.
META_CONTENT = re.compile(r'(<meta[^>]*content=")([^"]*)("[^>]*>)')

SNAPSHOT = ROOT / "data" / "catalog-snapshot.json"
PAGE_GLOBS = (
    "hotels/*/index.html",
    "kvartira/*/index.html",
    "blog/*/index.html",
    "answers/*/index.html",
    "podborki/*/index.html",
    "vezu/*/index.html",
)

CAPS_PARA = re.compile(r'<p class="paragraph-blocks__caps"><strong>([^<>]*)</strong></p>\s*')
# Абзацы и пункты списков с любыми атрибутами: на страницах экскурсий текст
# лежит в <p class="blog-hero__lead">, на страницах объектов — в простом <p>.
ELEMENT = re.compile(r"<(p|li)([^>]*)>([^<>]*)</(?:p|li)>")
EMPTY_UL = re.compile(r"<ul>\s*</ul>")


def clean_html(text: str) -> tuple[str, int, int]:
    """Возвращает (новый html, удалено строк, обрезано строк)."""
    removed = 0
    trimmed = 0

    def handle_caps(match: re.Match) -> str:
        nonlocal removed, trimmed
        raw = html_mod.unescape(match.group(1))
        cleaned = clean_line_for_site(raw)
        if not cleaned:
            removed += 1
            return ""
        if cleaned != raw:
            trimmed += 1
            escaped = html_mod.escape(cleaned)
            return f'<p class="paragraph-blocks__caps"><strong>{escaped}</strong></p>\n'
        return match.group(0)

    def handle_element(match: re.Match) -> str:
        nonlocal removed, trimmed
        tag, attrs, raw_escaped = match.group(1), match.group(2), match.group(3)
        raw = html_mod.unescape(raw_escaped)
        if not raw.strip():
            # Пустые <p></p>/<li></li> — часть вёрстки, не текст поста.
            return match.group(0)
        cleaned = clean_line_for_site(raw)
        if not cleaned:
            removed += 1
            return ""
        if cleaned != raw:
            trimmed += 1
            return f"<{tag}{attrs}>{html_mod.escape(cleaned)}</{tag}>"
        return match.group(0)

    def handle_text_node(match: re.Match) -> str:
        """Стрелки внутри абзацев с вложенной разметкой (<strong>, ссылки)."""
        nonlocal trimmed
        raw = html_mod.unescape(match.group(1))
        if not POINTER_EMOJI.search(raw):
            return match.group(0)
        cleaned = strip_pointer_emoji(raw)
        if cleaned == raw:
            return match.group(0)
        trimmed += 1
        if not cleaned:
            return "><"
        return f">{html_mod.escape(cleaned)}<"

    def handle_nested_para(match: re.Match) -> str:
        """Абзац с вложенной разметкой (<br/>, <strong>), целиком состоящий из
        телеграм-призыва: «напишите в комментариях…». Абзацы с фото, видео и
        ссылками не трогаем — там может быть полезное содержимое."""
        nonlocal removed
        inner = match.group(2)
        if re.search(r"<(?:img|video|picture|a|iframe)\b", inner, re.I):
            return match.group(0)
        plain = html_mod.unescape(re.sub(r"<[^>]+>", " ", inner))
        plain = re.sub(r"\s+", " ", plain).strip()
        if not plain:
            return match.group(0)
        if clean_line_for_site(plain):
            return match.group(0)
        removed += 1
        return ""

    def handle_meta(match: re.Match) -> str:
        """Описание страницы для поиска и превью ссылки: чистим стрелки."""
        nonlocal trimmed
        head, raw_escaped, tail = match.group(1), match.group(2), match.group(3)
        raw = html_mod.unescape(raw_escaped)
        if not POINTER_EMOJI.search(raw):
            return match.group(0)
        cleaned = strip_pointer_emoji(raw)
        if cleaned == raw:
            return match.group(0)
        trimmed += 1
        return f"{head}{html_mod.escape(cleaned, quote=True)}{tail}"

    text = META_CONTENT.sub(handle_meta, text)
    text = CAPS_PARA.sub(handle_caps, text)
    text = ELEMENT.sub(handle_element, text)
    text = NESTED_PARA.sub(handle_nested_para, text)
    text = TEXT_NODE.sub(handle_text_node, text)
    text = EMPTY_UL.sub("", text)
    return text, removed, trimmed


def clean_snapshot(dry_run: bool) -> tuple[int, int, int]:
    data = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    removed = trimmed = touched = 0
    for listing in data.get("listings", []):
        changed = False
        sections = (listing.get("details") or {}).get("sections") or []
        for section in sections:
            lines = section.get("lines") or []
            new_lines = []
            for line in lines:
                cleaned = clean_line_for_site(line)
                if not cleaned:
                    removed += 1
                    changed = True
                    continue
                if cleaned != str(line).strip():
                    trimmed += 1
                    changed = True
                new_lines.append(cleaned)
            section["lines"] = new_lines
        # Блок цен: чистим только текст строки. Саму строку не удаляем —
        # там цифры, потерять их нельзя.
        for price in (listing.get("details") or {}).get("prices") or []:
            raw = price.get("text")
            if not isinstance(raw, str) or not raw.strip():
                continue
            cleaned = clean_line_for_site(raw)
            if cleaned and cleaned != raw:
                price["text"] = cleaned
                trimmed += 1
                changed = True
        if changed:
            touched += 1
    if not dry_run and (removed or trimmed):
        SNAPSHOT.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return removed, trimmed, touched


def main() -> int:
    parser = argparse.ArgumentParser(description="Чистка телеграм-хвостов в текстах сайта.")
    parser.add_argument("--dry-run", action="store_true", help="только показать, ничего не менять")
    args = parser.parse_args()

    total_removed = total_trimmed = 0
    touched_pages = []
    for pattern in PAGE_GLOBS:
        for page in sorted(ROOT.glob(pattern)):
            original = page.read_text(encoding="utf-8")
            cleaned, removed, trimmed = clean_html(original)
            if removed or trimmed:
                touched_pages.append((page.relative_to(ROOT), removed, trimmed))
                total_removed += removed
                total_trimmed += trimmed
                if not args.dry_run and cleaned != original:
                    page.write_text(cleaned, encoding="utf-8")

    print(f"Страниц изменено: {len(touched_pages)} | строк удалено: {total_removed} | обрезано: {total_trimmed}")
    for rel, removed, trimmed in touched_pages:
        print(f"  {str(rel):68} удалено {removed}, обрезано {trimmed}")

    snap_removed, snap_trimmed, snap_touched = clean_snapshot(args.dry_run)
    print(f"\nСнапшот каталога: объектов затронуто {snap_touched}, строк удалено {snap_removed}, обрезано {snap_trimmed}")
    if args.dry_run:
        print("\n(пробный прогон — файлы не менялись)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
