#!/usr/bin/env python3
"""Split the OCR review bank into small JSON files for static pages."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BANK_PATH = ROOT / "media" / "reviews" / "review_text_bank.json"
SNAPSHOT_PATH = ROOT / "data" / "catalog-snapshot.json"
REVIEWS_ROOT = ROOT / "media" / "reviews"
GLOBAL_LIMIT = 64
MATCH_THRESHOLD = 1200


def normalize_review_slug(value: str) -> str:
    value = re.sub(r"-+", "-", (value or "").lower().strip().strip("/").replace("_", "-"))
    return re.sub(r"-\d{3,6}$", "", value)


def review_slug_match_score(source_slug: str, target_slug: str) -> int:
    if not source_slug or not target_slug:
        return 0
    if source_slug == target_slug:
        return 10_000 + len(source_slug)
    if source_slug.startswith(target_slug):
        return 5_000 + len(target_slug)
    if target_slug.startswith(source_slug):
        return 4_000 + len(source_slug)

    source_tokens = source_slug.split("-")
    target_tokens = target_slug.split("-")
    source_set = set(source_tokens)
    common = [token for token in target_tokens if token in source_set]
    if not common:
        return 0
    return round(len(common) / max(len(source_tokens), len(target_tokens)) * 1000) + len(common)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def active_listing_slugs() -> list[str]:
    payload = load_json(SNAPSHOT_PATH)
    rows = payload.get("listings") if isinstance(payload, dict) else []
    slugs = []
    for row in rows or []:
        if not isinstance(row, dict) or row.get("is_active") is False:
            continue
        slug = str(row.get("slug") or "").strip()
        if slug:
            slugs.append(slug)
    return sorted(set(slugs))


def reviews_for_slug(
    slug: str,
    bank: dict[str, list[dict[str, Any]]],
    excluded_fuzzy_slugs: set[str],
) -> tuple[str, list[dict[str, Any]]]:
    if slug in bank:
        return slug, bank[slug]

    target = normalize_review_slug(slug)
    best_key = ""
    best_score = 0
    for candidate in bank:
        if candidate in excluded_fuzzy_slugs:
            continue
        score = review_slug_match_score(normalize_review_slug(candidate), target)
        if score > best_score:
            best_key = candidate
            best_score = score

    if not best_key or best_score < MATCH_THRESHOLD:
        return "", []
    return best_key, bank.get(best_key, [])


def compact_global_reviews(reviews: list[dict[str, Any]], limit: int = GLOBAL_LIMIT) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen_objects: set[str] = set()

    for review in reviews:
        object_slug = str(review.get("object_slug") or "").strip()
        if object_slug and object_slug not in seen_objects:
            selected.append(review)
            seen_objects.add(object_slug)
        if len(selected) >= limit:
            return selected

    for review in reviews:
        if review in selected:
            continue
        selected.append(review)
        if len(selected) >= limit:
            return selected

    return selected


def main() -> int:
    payload = load_json(BANK_PATH)
    if not isinstance(payload, dict):
        raise TypeError(f"Unexpected bank payload: {BANK_PATH}")

    global_reviews = payload.get("global") if isinstance(payload.get("global"), list) else []
    by_object_raw = payload.get("by_object") if isinstance(payload.get("by_object"), dict) else {}
    by_object = {
        str(slug): reviews
        for slug, reviews in by_object_raw.items()
        if slug and isinstance(reviews, list) and reviews
    }
    excluded_fuzzy_slugs = {
        str(slug)
        for slug in (payload.get("excluded_fuzzy_slugs") or [])
        if slug
    }

    compact_global = compact_global_reviews(global_reviews)
    dump_json(
        REVIEWS_ROOT / "global.json",
        {
            "version": payload.get("version", 1),
            "source": "review_text_bank_split",
            "stats": {
                "global_total": len(global_reviews),
                "global_published": len(compact_global),
                "objects_with_source_reviews": len(by_object),
            },
            "global": compact_global,
            "excluded_fuzzy_slugs": sorted(excluded_fuzzy_slugs),
        },
    )

    written = 0
    missing = 0
    target_slugs = set(active_listing_slugs()) | set(by_object)
    for slug in sorted(target_slugs):
        source_slug, reviews = reviews_for_slug(slug, by_object, excluded_fuzzy_slugs)
        if not reviews:
            missing += 1
            continue
        dump_json(
            REVIEWS_ROOT / slug / "bank.json",
            {
                "version": payload.get("version", 1),
                "source": "review_text_bank_split",
                "slug": slug,
                "source_slug": source_slug,
                "reviews": reviews,
            },
        )
        written += 1

    print(
        f"global={len(compact_global)}/{len(global_reviews)} "
        f"object_banks={written} missing={missing} source_objects={len(by_object)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
