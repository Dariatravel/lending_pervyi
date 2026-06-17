#!/usr/bin/env python3
"""Аудит и правка привязки OCR-отзывов к объектам каталога."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BANK_PATH = ROOT / "media" / "reviews" / "review_text_bank.json"
MANIFEST_PATH = ROOT / "media" / "reviews" / "manifest.json"
HIDDEN_PATH = ROOT / "tools" / "hidden_listings.json"
SNAPSHOT_PATH = ROOT / "data" / "catalog-snapshot.json"
REPORT_PATH = ROOT / "output" / "review_assignment_audit.txt"

# Ошибочные алиасы: отзывы другого объекта (не в каталоге).
WRONG_HOTEL_IMAGE_MARKERS = (
    "costa-d-ora",
    "costa-ora",
    "costa d ora",
    "коста-d-ora",
    "коста-ора",
)


def load_hidden() -> set[str]:
    if not HIDDEN_PATH.is_file():
        return set()
    return set(json.loads(HIDDEN_PATH.read_text(encoding="utf-8")))


def load_active_slugs() -> dict[str, str]:
    hidden = load_hidden()
    rows = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8")).get("listings") or []
    return {
        str(row["slug"]): str(row.get("title") or "")
        for row in rows
        if row.get("slug") and row.get("is_active", True) and row["slug"] not in hidden
    }


def is_wrong_hotel_review(review: dict[str, Any]) -> bool:
    src = str(review.get("source_image") or "").lower()
    text = str(review.get("text") or "").lower()
    if any(marker in src for marker in WRONG_HOTEL_IMAGE_MARKERS):
        return True
    if re.search(r"costa\s*d['']?\s*ora|коста\s*d?\s*['']?\s*ора", text):
        return True
    return False


def fix_bank(payload: dict[str, Any], hidden: set[str]) -> tuple[dict[str, Any], list[str]]:
    log: list[str] = []
    by_object: dict[str, list[dict[str, Any]]] = {}
    removed_reviews = 0

    for slug, entries in (payload.get("by_object") or {}).items():
        if not slug or not isinstance(entries, list):
            continue
        if slug in hidden:
            log.append(f"removed bucket (hidden slug): {slug} ({len(entries)} reviews)")
            removed_reviews += len(entries)
            continue

        kept: list[dict[str, Any]] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            if is_wrong_hotel_review(entry):
                removed_reviews += 1
                log.append(f"removed wrong-hotel review from {slug}: {entry.get('source_image', '')[:90]}")
                continue
            kept.append(entry)
        if kept:
            by_object[str(slug)] = kept
        elif entries:
            log.append(f"removed empty bucket after cleanup: {slug}")

    global_entries = []
    for entry in payload.get("global") or []:
        if not isinstance(entry, dict):
            continue
        obj_slug = str(entry.get("object_slug") or "")
        if obj_slug in hidden or is_wrong_hotel_review(entry):
            removed_reviews += 1
            continue
        global_entries.append(entry)

    female_count = sum(1 for review in global_entries if review.get("gender") == "female")
    male_count = sum(1 for review in global_entries if review.get("gender") == "male")

    payload["global"] = global_entries
    payload["by_object"] = by_object
    payload["excluded_fuzzy_slugs"] = sorted(hidden)
    payload["stats"] = {
        "total": len(global_entries),
        "female": female_count,
        "male": male_count,
        "female_ratio": round((female_count / len(global_entries)) if global_entries else 0, 4),
        "male_ratio": round((male_count / len(global_entries)) if global_entries else 0, 4),
        "objects_with_reviews": len(by_object),
    }
    log.append(f"removed reviews total: {removed_reviews}")
    return payload, log


def fix_manifest(manifest: dict[str, Any], hidden: set[str]) -> tuple[dict[str, Any], list[str]]:
    log: list[str] = []
    cleaned: dict[str, Any] = {}
    for slug, items in manifest.items():
        if slug in hidden:
            log.append(f"removed manifest bucket: {slug} ({len(items)} images)")
            continue
        if any(marker in slug.lower() for marker in ("costa-d-ora", "costa-ora")):
            log.append(f"removed manifest bucket by marker: {slug}")
            continue
        cleaned[slug] = items
    return cleaned, log


def audit_fuzzy_inherits(active: dict[str, str], bank: dict[str, list[dict[str, Any]]], hidden: set[str]) -> list[str]:
    from tools.clean_review_text_bank import reviews_for_slug, load_review_bank

    loaded = load_review_bank()
    lines: list[str] = []
    for slug, title in sorted(active.items()):
        if slug in loaded:
            continue
        revs = reviews_for_slug(slug, loaded)
        if not revs:
            continue
        # find source key
        best = ""
        best_score = 0
        from tools.clean_review_text_bank import normalize_review_slug, review_slug_match_score

        target = normalize_review_slug(slug)
        for cand in loaded:
            if cand in hidden:
                continue
            sc = review_slug_match_score(normalize_review_slug(cand), target)
            if sc > best_score:
                best_score = sc
                best = cand
        if best and best != slug:
            sample = str(revs[0].get("text") or "")[:100]
            lines.append(f"FUZZY {slug} ({title}) <- {best} score={best_score} | {sample}")
    return lines


def main() -> int:
    hidden = load_hidden()
    active = load_active_slugs()

    payload = json.loads(BANK_PATH.read_text(encoding="utf-8"))
    payload, bank_log = fix_bank(payload, hidden | {"karalina-apartamenty-3124"})
    BANK_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    manifest, manifest_log = fix_manifest(manifest, hidden | {"karalina-apartamenty-3124"})
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    from tools.clean_review_text_bank import load_review_bank

    fuzzy_lines = audit_fuzzy_inherits(active, load_review_bank(), hidden | {"karalina-apartamenty-3124"})

    report_lines = ["Review assignment audit/fix", "", "Bank/manifest:", *bank_log, *manifest_log, "", "Remaining fuzzy inherits:"]
    report_lines.extend(fuzzy_lines or ["(none)"])
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    print("\n".join(report_lines[:40]))
    if len(report_lines) > 40:
        print(f"... full report: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
