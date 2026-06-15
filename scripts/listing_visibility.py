#!/usr/bin/env python3
"""Скрытые объекты: slug-список и деактивация в catalog snapshot (или Supabase legacy)."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
HIDDEN_LISTINGS_FILE = ROOT / "tools" / "hidden_listings.json"
SNAPSHOT_PATH = ROOT / "data" / "catalog-snapshot.json"


def load_hidden_slugs() -> set[str]:
    if not HIDDEN_LISTINGS_FILE.is_file():
        return set()
    data = json.loads(HIDDEN_LISTINGS_FILE.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return {str(item).strip() for item in data if str(item).strip()}
    if isinstance(data, dict):
        slugs = data.get("slugs") or data.get("hotels") or []
        return {str(item).strip() for item in slugs if str(item).strip()}
    return set()


def save_hidden_slugs(slugs: set[str]) -> None:
    ordered = sorted(slugs)
    HIDDEN_LISTINGS_FILE.write_text(json.dumps(ordered, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def merge_hidden_slugs(new_slugs: list[str]) -> set[str]:
    merged = load_hidden_slugs() | {s.strip() for s in new_slugs if s.strip()}
    save_hidden_slugs(merged)
    return merged


def use_snapshot_store() -> bool:
    if os.getenv("SKIP_SUPABASE_SYNC", "").strip().lower() in {"1", "true", "yes", "on"}:
        return True
    return SNAPSHOT_PATH.exists()


def _rows_from_store(supa: Any | None) -> list[dict[str, Any]]:
    if use_snapshot_store() or supa is None:
        from catalog_snapshot import load_listings

        return load_listings()
    return supa.fetch_listings() if hasattr(supa, "fetch_listings") else []


def deactivate_slugs(supa: Any | None, slugs: set[str]) -> tuple[list[str], list[str]]:
    """Вернуть (деактивированы, не найдены)."""
    if not slugs:
        return [], []
    rows = _rows_from_store(supa)
    by_slug = {str(r.get("slug") or ""): r for r in rows}
    done: list[str] = []
    missing: list[str] = []
    snapshot_mode = use_snapshot_store() or supa is None
    for slug in sorted(slugs):
        row = by_slug.get(slug)
        if not row:
            missing.append(slug)
            continue
        if row.get("is_active") is not False:
            if snapshot_mode:
                from catalog_snapshot import deactivate_listing

                deactivate_listing(slug)
            else:
                supa.patch_listing(int(row["id"]), {"is_active": False})
        done.append(slug)
    return done, missing


def activate_slugs(supa: Any | None, slugs: set[str]) -> tuple[list[str], list[str]]:
    """Вернуть (активированы, не найдены)."""
    if not slugs:
        return [], []
    rows = _rows_from_store(supa)
    by_slug = {str(r.get("slug") or ""): r for r in rows}
    done: list[str] = []
    missing: list[str] = []
    snapshot_mode = use_snapshot_store() or supa is None
    for slug in sorted(slugs):
        row = by_slug.get(slug)
        if not row:
            missing.append(slug)
            continue
        if row.get("is_active") is not True:
            if snapshot_mode:
                from catalog_snapshot import activate_listing

                activate_listing(slug)
            else:
                supa.patch_listing(int(row["id"]), {"is_active": True})
        done.append(slug)
    return done, missing
