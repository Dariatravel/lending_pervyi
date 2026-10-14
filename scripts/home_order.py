"""Порядок объектов в начале каталога на главной (первые 20 видны сразу).

Правило Дарьи 14.10.2026 — на главной в первую очередь межсезон и Новый год:
1. закреплённые партнёры из data/home-priority.json («Роял Ривьера» —
   основной партнёр на межсезон, затем «Мулберри»);
2. новогодние предложения — объекты из новогоднего поста, оформленные как
   новогодние (в названии «НОВЫЙ ГОД»/«НОВОГОДН»), в порядке поста;
3. остальные объекты из постов «Межсезон» и «Новый год»: сначала с
   бассейном, потом без, внутри — в порядке постов;
4. летний список data/featured-order.json (прежние «первые 20»);
5. всё остальное — прежним порядком каталога.

Состав подборок берётся из data/telegram-collections.json, который автосинк
обновляет по постам каждый час, поэтому начало главной следует за постами.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PRIORITY_PATH = ROOT / "data" / "home-priority.json"
COLLECTIONS_PATH = ROOT / "data" / "telegram-collections.json"
SNAPSHOT_PATH = ROOT / "data" / "catalog-snapshot.json"
FEATURED_PATH = ROOT / "data" / "featured-order.json"

NEW_YEAR_MARKERS = ("НОВЫЙ ГОД", "НОВОГОДН")


def _load(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _slugs(collection: dict) -> list[str]:
    return [
        str(href).strip("/").split("/")[-1]
        for group in (collection or {}).get("groups") or []
        for href in group.get("hrefs") or []
    ]


def has_pool(row: dict) -> bool:
    filters = (row.get("details") or {}).get("filters") or {}
    if "pool" in (filters.get("room") or []):
        return True
    return "БАССЕЙН" in str(row.get("title") or "").upper()


def is_new_year_offer(row: dict) -> bool:
    title = str(row.get("title") or "").upper().replace("Ё", "Е")
    return any(marker in title for marker in NEW_YEAR_MARKERS)


def home_order() -> list[str]:
    rows = (_load(SNAPSHOT_PATH, {}) or {}).get("listings") or []
    active = {str(r.get("slug")): r for r in rows if isinstance(r, dict) and r.get("is_active", True) and r.get("slug")}
    priority = _load(PRIORITY_PATH, {}) or {}
    collections = _load(COLLECTIONS_PATH, {}) or {}
    new_year = _slugs(collections.get("novyy-god-2027"))
    off_season = _slugs(collections.get("mezhsezon"))

    order: list[str] = []

    def add(slugs: list[str]) -> None:
        for slug in slugs:
            if slug in active and slug not in order:
                order.append(slug)

    add([str(s) for s in priority.get("pinned") or []])
    add([s for s in new_year if s in active and is_new_year_offer(active[s])])
    seasonal = [s for s in off_season + new_year if s in active]
    add([s for s in seasonal if has_pool(active[s])])
    add(seasonal)
    add([str(s) for s in _load(FEATURED_PATH, []) or []])
    return order


if __name__ == "__main__":
    rows = {r["slug"]: r for r in (_load(SNAPSHOT_PATH, {}) or {}).get("listings") or [] if r.get("slug")}
    for i, slug in enumerate(home_order(), 1):
        row = rows.get(slug, {})
        print(f"{i:3}. {'🏊' if has_pool(row) else '  '} {row.get('title', slug)[:70]}")
