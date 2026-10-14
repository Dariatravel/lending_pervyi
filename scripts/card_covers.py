"""Ручные обложки объектов («заглавное фото» карточки).

Обычно обложка — первое фото поста. Если оно невыигрышное (мангал вместо
моря у «Трио», 14.10.2026), обложку задаёт data/card-cover-overrides.json:
{"<slug>": "<URL фото на media-CDN>"}. Дарья может прислать новое заглавное
фото комментарием к посту с подписью «заглавное фото» — автосинк сам
загрузит его и запишет сюда (scripts/apply_telegram_supplemental_comments.py).

Обложку берут: карточки каталога/подборок и страница объекта
(rebuild_from_supabase.pick_cover_url) и дорисовка главной
(catalog_snapshot.compact_listing_for_index).
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OVERRIDES_PATH = ROOT / "data" / "card-cover-overrides.json"

_cache: dict[str, str] | None = None


def load_overrides(*, fresh: bool = False) -> dict[str, str]:
    global _cache
    if _cache is None or fresh:
        try:
            data = json.loads(OVERRIDES_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        _cache = {str(k): str(v) for k, v in (data.get("covers") or {}).items() if v}
    return _cache


def cover_override(slug: str) -> str:
    return load_overrides().get(str(slug or ""), "")


def set_override(slug: str, url: str, note: str = "") -> None:
    try:
        data = json.loads(OVERRIDES_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    data.setdefault("_comment", "Ручные обложки объектов: slug → URL фото на media-CDN. См. scripts/card_covers.py.")
    data.setdefault("covers", {})[slug] = url
    if note:
        data.setdefault("notes", {})[slug] = note
    OVERRIDES_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    load_overrides(fresh=True)
