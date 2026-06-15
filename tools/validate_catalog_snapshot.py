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
        if cover and "storage.yandexcloud.net" not in cover and not cover.startswith("/media/"):
            issues.append(f"cover not yandex: {slug}")
        details = row.get("details") or {}
        filters = details.get("filters") or {}
        if filters and not isinstance(filters, dict):
            issues.append(f"bad filters type: {slug}")
        for media in row.get("media") or []:
            mime = str(media.get("mime_type") or "")
            url = str(media.get("public_url") or media.get("source_url") or "")
            if mime.startswith("video/") and url and "storage.yandexcloud.net" not in url:
                issues.append(f"video not yandex: {slug}")
            if mime.startswith("image/") and url and "storage.yandexcloud.net" not in url and not url.startswith("/media/"):
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
