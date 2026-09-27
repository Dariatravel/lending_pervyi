#!/usr/bin/env python3
"""Перенести уточнение из заголовка цен поста в каталог и на готовые страницы.

В постах Telegram заголовок «✔️ЦЕНЫ (при двухместном размещении):» — уточнение
стояло в скобках прямо в заголовке, и парсер терял его вместе с заголовком:
на сайте оставалось голое «ЦЕНЫ:» (Амзара, 27.09.2026 — гость пришёл с
претензией). Парсер починен (sync_abhazbooking_2026.parse_post), но страницы
объектов пересобираются только полным синком из Telegram — этот инструмент
добавляет примечание первой строкой блока цен в снапшот и на страницы уже
опубликованных объектов. Идемпотентен.

Вход: JSON {message_id: "текст в скобках"} — см. --notes.
    python3 tools/apply_price_heading_notes.py --notes notes.json [--dry-run]
"""
from __future__ import annotations

import argparse
import html as html_mod
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "data" / "catalog-snapshot.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--notes", required=True, help="JSON: {source_message_id: 'текст в скобках'}")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    notes = {int(k): str(v).strip() for k, v in json.loads(Path(args.notes).read_text(encoding="utf-8")).items()}

    snapshot_text = SNAPSHOT.read_text(encoding="utf-8")
    snapshot = json.loads(snapshot_text)
    snap_changed = 0
    page_changed = 0
    for row in snapshot.get("listings", []):
        if not row.get("is_active") or row.get("source_kind") != "hotel":
            continue
        note = notes.get(int(row.get("source_message_id") or 0))
        if not note:
            continue
        note_text = note if note.startswith("(") else f"({note})"
        prices = (row.get("details") or {}).get("prices")
        if not isinstance(prices, list):
            continue
        texts = [str(p.get("text") or "").strip().casefold() for p in prices if isinstance(p, dict)]
        if note_text.casefold() not in texts:
            prices.insert(0, {"kind": "note", "text": note_text})
            snap_changed += 1
            print(f"  снапшот: {row['slug']} ← {note_text}")

        page = ROOT / "hotels" / row["slug"] / "index.html"
        if not page.is_file():
            continue
        page_html = page.read_text(encoding="utf-8")
        escaped = html_mod.escape(note_text)
        if f"<li>{escaped}</li>" in page_html:
            continue
        marker = '<ul class="price-card__seasons">'
        if marker not in page_html:
            print(f"  страница без блока цен: {row['slug']}")
            continue
        new_html = page_html.replace(marker, f"{marker}\n<li>{escaped}</li>", 1)
        page_changed += 1
        print(f"  страница: {page.relative_to(ROOT)}")
        if not args.dry_run:
            page.write_text(new_html, encoding="utf-8")

    if snap_changed and not args.dry_run:
        # Тот же формат, что у catalog_snapshot.save_listings (indent=2).
        SNAPSHOT.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Снапшот: объектов {snap_changed} | страниц: {page_changed}" + (" (пробный прогон)" if args.dry_run else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
