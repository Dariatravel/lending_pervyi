#!/usr/bin/env python3
"""Обновить порядок начала главной по scripts/home_order.py без пересборки объектов.

Пересобирает только статичные карточки главной (index.html) и
data/catalog-index.json (поле home_rank для дорисовки в браузере). Страницы
объектов не трогает — на Mac без media/ полная пересборка их портит.
Нужна, когда поменялся состав постов «Межсезон»/«Новый год», а синка объектов
не было (шаг «Опубликовать подборки из постов» в watch-telegram.yml).

Запуск: python3 tools/reorder_home_grid.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from catalog_snapshot import write_catalog_index  # noqa: E402
from rebuild_from_catalog_snapshot import load_snapshot_payload, load_snapshot_rows  # noqa: E402
from rebuild_from_supabase import home_grid_from_rows  # noqa: E402

HREF_RE = re.compile(r'<a\s+class="catalog-card"[^>]*href="/(?:hotels|kvartira)/([^/"]+)/"')


def main() -> int:
    payload = load_snapshot_payload()
    rows = load_snapshot_rows(payload)
    home_grid_from_rows([dict(row) for row in rows])
    write_catalog_index(rows, generated_at=str(payload.get("generated_at") or ""))
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    grid = html.split('id="catalog-grid"', 1)[-1]
    for i, slug in enumerate(HREF_RE.findall(grid)[:20], 1):
        print(f"{i:2}. {slug}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
