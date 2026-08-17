#!/usr/bin/env python3
"""Validate data/catalog-snapshot.json structure and media URLs."""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

SNAPSHOT_PATH = ROOT / "data" / "catalog-snapshot.json"
GROUPS = ("distance", "food", "price", "city", "beach", "room", "stay")
CANONICAL_FILTER_VALUES = {
    "distance": {"beachfront", "up-to-5", "up-to-10", "over-10"},
    "food": {"no-food", "half-board", "full-board", "breakfast", "cafe"},
    "price": {"economy", "midrange", "premium"},
    "city": {"ldzaa", "pitsunda", "gagra", "alakhadzy", "gudauta", "new-afon", "sukhum", "tsandripsh"},
    "beach": {"pine-pebble-ldzaa-pitsunda", "pitsunda-bay-mixed", "sand-ldzaa", "sand-sukhum", "pebble"},
    "room": {"sea-view", "pool", "balcony", "terrace", "tv", "kitchen", "five-plus", "two-room-plus", "beachfront-room"},
    "stay": {"cottages", "apartments", "turnkey-house", "pets", "no-small-kids"},
}


def main() -> int:
    if not SNAPSHOT_PATH.exists():
        print(f"missing: {SNAPSHOT_PATH}", file=sys.stderr)
        return 1

    payload = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    listings = payload.get("listings") or []
    issues: list[str] = []

    slugs = [str(row.get("slug") or "") for row in listings if row.get("is_active", True)]
    for slug, count in Counter(slugs).items():
        if count > 1:
            issues.append(f"duplicate slug: {slug}")

    for row in listings:
        if row.get("is_active") is False:
            continue
        slug = row.get("slug") or "?"
        if not row.get("page_url"):
            issues.append(f"missing page_url: {slug}")
        cover = str(row.get("cover_url") or "")
        if cover and "storage.yandexcloud.net" not in cover and "media.xn--80aacbklan7f0b.xn--p1ai" not in cover:
            issues.append(f"cover not yandex: {slug}")
        details = row.get("details") or {}
        filters = details.get("filters") or {}
        if filters and not isinstance(filters, dict):
            issues.append(f"bad filters type: {slug}")
        if isinstance(filters, dict):
            for group, raw_values in filters.items():
                if group not in GROUPS:
                    issues.append(f"unknown filter group: {slug} {group}")
                    continue
                if isinstance(raw_values, str):
                    values = [part.strip() for part in raw_values.split("|") if part.strip()]
                elif isinstance(raw_values, list):
                    values = [str(value).strip() for value in raw_values if str(value).strip()]
                else:
                    issues.append(f"bad filter values type: {slug} {group}")
                    continue
                for value in values:
                    if value not in CANONICAL_FILTER_VALUES[group]:
                        issues.append(f"unknown filter code: {slug} {group}={value}")
        for media in row.get("media") or []:
            mime = str(media.get("mime_type") or "")
            url = str(media.get("public_url") or media.get("source_url") or "")
            if mime.startswith("video/") and url and "storage.yandexcloud.net" not in url and "media.xn--80aacbklan7f0b.xn--p1ai" not in url:
                issues.append(f"video not yandex: {slug}")
            if mime.startswith("image/") and url and "storage.yandexcloud.net" not in url and "media.xn--80aacbklan7f0b.xn--p1ai" not in url:
                issues.append(f"image not yandex: {slug}")

    active = sum(1 for row in listings if row.get("is_active", True))
    print(
        json.dumps(
            {
                "generated_at": payload.get("generated_at"),
                "active_listings": active,
                "issues": len(issues),
            },
            ensure_ascii=False,
        )
    )
    for issue in issues[:30]:
        print(f"WARN {issue}")
    if len(issues) > 30:
        print(f"WARN ... and {len(issues) - 30} more")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
