"""Устойчивое хранилище блоков «Дополнительные обзоры» (медиа с подписями из комментариев).

Раньше блоки жили только в HTML страниц и стирались при каждой пересборке
(render_detail_page пишет страницу с нуля). Теперь готовая секция каждого
объекта хранится в data/supplemental-blocks.json (в git), и генераторы
вставляют её обратно при каждой перегенерации страницы.

Запись в манифест делает apply_telegram_supplemental_comments.py (перенос
медиа с подписью из комментариев Telegram); чтение — sync_catalog_from_telegram
и любой другой генератор страниц объектов.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "data" / "supplemental-blocks.json"


def load_manifest() -> dict[str, dict]:
    try:
        data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_section(slug: str, kind: str, section_html: str) -> None:
    manifest = load_manifest()
    manifest[slug] = {
        "kind": kind,
        "section_html": section_html,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1, sort_keys=True),
        encoding="utf-8",
    )


def remove_section(slug: str) -> None:
    manifest = load_manifest()
    if slug in manifest:
        del manifest[slug]
        MANIFEST_PATH.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=1, sort_keys=True),
            encoding="utf-8",
        )


def apply_to_page_html(page_html: str, slug: str) -> str:
    """Вставить сохранённую секцию объекта в свежесгенерированный HTML страницы.

    Точки вставки повторяют apply_telegram_supplemental_comments.insert_section;
    если секции для slug нет или точка вставки не найдена — HTML не меняется.
    """
    entry = load_manifest().get(slug)
    section_html = (entry or {}).get("section_html") or ""
    if not section_html:
        return page_html

    soup = BeautifulSoup(page_html, "html.parser")
    fragment = BeautifulSoup(section_html, "html.parser")
    existing = soup.select_one("#supplemental-comments, #room-overviews")
    if existing:
        existing.replace_with(fragment)
        return str(soup)
    media_section = soup.select_one("section.hotel-media-section")
    if media_section:
        media_section.insert_after(fragment)
        return str(soup)
    detail_main = soup.select_one(".hotel-site-concept__detail-main")
    if detail_main:
        detail_main.insert(0, fragment)
        return str(soup)
    return page_html
