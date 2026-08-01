#!/usr/bin/env python3
"""Закрывает от индексации страницы скрытых и снятых объектов.

Скрытый объект уходит из каталога, подборок и sitemap, но его страница
остаётся доступной по прямой ссылке. Для Яндекса это «страница-сирота»: её
нет в структуре сайта, зато она конкурирует в поиске с активными объектами.
Такие страницы помечаем noindex, follow — ссылки внутри робот обойдёт,
а саму страницу в поиск не возьмёт.

Запуск:
    python3 tools/apply_noindex_to_hidden_pages.py [--check]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HIDDEN_FILE = ROOT / "tools" / "hidden_listings.json"
SNAPSHOT = ROOT / "data" / "catalog-snapshot.json"
SECTIONS = ("hotels", "kvartira")

ROBOTS_RX = re.compile(r'<meta[^>]*name="robots"[^>]*>|<meta[^>]*content="[^"]*"[^>]*name="robots"[^>]*>', re.I)
NOINDEX_RX = re.compile(r'<meta[^>]*name="robots"[^>]*noindex|<meta[^>]*noindex[^>]*name="robots"', re.I)
REDIRECT_RX = re.compile(r'http-equiv="refresh"', re.I)


def snapshot_rows() -> list[dict]:
    if not SNAPSHOT.is_file():
        return []
    try:
        snap = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return snap.get("listings") or snap.get("rows") or []


def hidden_slugs() -> set[str]:
    """Скрытые вручную, снятые (is_active=false) и осиротевшие страницы.

    Осиротевшая — это страница объекта, которого в каталоге уже нет: ссылок
    на неё нет ни в каталоге, ни в sitemap, а в поиске она мешает живым.
    """
    slugs: set[str] = set()
    if HIDDEN_FILE.is_file():
        try:
            data = json.loads(HIDDEN_FILE.read_text(encoding="utf-8"))
            slugs |= {str(s).strip() for s in (data if isinstance(data, list) else data.get("slugs", []))}
        except json.JSONDecodeError:
            pass
    rows = snapshot_rows()
    active: set[str] = set()
    for row in rows:
        slug = str(row.get("slug") or "").strip()
        if not slug:
            continue
        (active if row.get("is_active") is not False else slugs).add(slug)
    if active:  # снапшот прочитан — можно искать осиротевшие страницы
        for section in SECTIONS:
            base = ROOT / section
            if not base.is_dir():
                continue
            for path in base.glob("*/index.html"):
                if path.parent.name not in active:
                    slugs.add(path.parent.name)
    return {s for s in slugs if s}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="ничего не записывать")
    args = parser.parse_args()

    slugs = hidden_slugs()
    changed: list[str] = []
    for section in SECTIONS:
        base = ROOT / section
        if not base.is_dir():
            continue
        for slug in sorted(slugs):
            path = base / slug / "index.html"
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8")
            if NOINDEX_RX.search(text) or REDIRECT_RX.search(text):
                continue
            tag = '<meta name="robots" content="noindex, follow" />'
            if ROBOTS_RX.search(text):
                updated = ROBOTS_RX.sub(tag, text, count=1)
            elif "</head>" in text:
                updated = text.replace("</head>", f"  {tag}\n</head>", 1)
            else:
                continue
            changed.append(f"{section}/{slug}")
            if not args.check:
                path.write_text(updated, encoding="utf-8")

    for item in changed:
        print(f"noindex → {item}")
    print(f"Страниц закрыто от индексации: {len(changed)}"
          f"{' (проверка, без записи)' if args.check else ''}"
          f" | скрытых объектов всего: {len(slugs)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
