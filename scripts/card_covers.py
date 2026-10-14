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
# Обложки из комментариев «заглавное фото» — по файлу на объект: два
# автосинка подряд правили общий json и затирали друг друга (14.10.2026).
AUTO_DIR = ROOT / "data" / "card-covers"

_cache: dict[str, str] | None = None


def load_overrides(*, fresh: bool = False) -> dict[str, str]:
    global _cache
    if _cache is None or fresh:
        try:
            data = json.loads(OVERRIDES_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        covers = {str(k): str(v) for k, v in (data.get("covers") or {}).items() if v}
        # Обложка из комментария свежее ручной записи в общем файле.
        for path in sorted(AUTO_DIR.glob("*.json")) if AUTO_DIR.is_dir() else []:
            try:
                item = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if item.get("url"):
                covers[path.stem] = str(item["url"])
        _cache = covers
    return _cache


def cover_override(slug: str) -> str:
    return load_overrides().get(str(slug or ""), "")


def set_override(slug: str, url: str, note: str = "") -> None:
    """Записать обложку объекта в data/card-covers/<slug>.json."""
    AUTO_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"url": url}
    if note:
        payload["note"] = note
    (AUTO_DIR / f"{slug}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    load_overrides(fresh=True)
