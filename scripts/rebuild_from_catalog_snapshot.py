#!/usr/bin/env python3
"""Rebuild catalog HTML from data/catalog-snapshot.json without Supabase API."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from catalog_snapshot import write_catalog_index  # noqa: E402
from rebuild_from_supabase import rebuild_catalog  # noqa: E402

SNAPSHOT_PATH = ROOT / "data" / "catalog-snapshot.json"
CURRENT_PAGES_PATH = ROOT / "output" / "current_pages.json"


def load_snapshot_payload() -> dict[str, Any]:
    if not SNAPSHOT_PATH.exists():
        raise FileNotFoundError(f"Snapshot not found: {SNAPSHOT_PATH}")
    payload = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    return payload


def load_snapshot_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("listings") or []
    if not rows:
        raise RuntimeError("Snapshot has no listings")
    return rows


def write_current_pages(rows: list[dict[str, Any]]) -> None:
    current_pages = []
    for row in rows:
        if row.get("source_kind") != "hotel" or row.get("is_active") is False:
            continue
        slug = str(row.get("slug") or "").strip()
        source_id = row.get("source_message_id")
        if not slug or source_id is None:
            continue
        current_pages.append(
            {
                "slug": slug,
                "source_id": int(source_id),
                "title": str(row.get("title") or slug),
            }
        )
    CURRENT_PAGES_PATH.parent.mkdir(parents=True, exist_ok=True)
    CURRENT_PAGES_PATH.write_text(
        json.dumps(sorted(current_pages, key=lambda item: item["source_id"]), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> int:
    payload = load_snapshot_payload()
    rows = load_snapshot_rows(payload)
    rebuild_catalog(rows)
    write_catalog_index(rows, generated_at=str(payload.get("generated_at") or ""))
    write_current_pages(rows)
    print(f"snapshot={SNAPSHOT_PATH.name} generated_at={payload.get('generated_at')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
