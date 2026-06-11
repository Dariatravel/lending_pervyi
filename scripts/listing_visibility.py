#!/usr/bin/env python3
"""Скрытые объекты: slug-список и деактивация в Supabase (is_active=false)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
HIDDEN_LISTINGS_FILE = ROOT / "tools" / "hidden_listings.json"


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


def deactivate_slugs(supa: Any, slugs: set[str]) -> tuple[list[str], list[str]]:
    """Вернуть (деактивированы, не найдены в Supabase)."""
    if not slugs:
        return [], []
    rows = supa.fetch_listings() if hasattr(supa, "fetch_listings") else []
    by_slug = {str(r.get("slug") or ""): r for r in rows}
    done: list[str] = []
    missing: list[str] = []
    for slug in sorted(slugs):
        row = by_slug.get(slug)
        if not row:
            missing.append(slug)
            continue
        if row.get("is_active") is not False:
            supa.patch_listing(int(row["id"]), {"is_active": False})
        done.append(slug)
    return done, missing


def activate_slugs(supa: Any, slugs: set[str]) -> tuple[list[str], list[str]]:
    """Вернуть (активированы, не найдены в Supabase)."""
    if not slugs:
        return [], []
    rows = supa.fetch_listings() if hasattr(supa, "fetch_listings") else []
    by_slug = {str(r.get("slug") or ""): r for r in rows}
    done: list[str] = []
    missing: list[str] = []
    for slug in sorted(slugs):
        row = by_slug.get(slug)
        if not row:
            missing.append(slug)
            continue
        if row.get("is_active") is not True:
            supa.patch_listing(int(row["id"]), {"is_active": True})
        done.append(slug)
    return done, missing
