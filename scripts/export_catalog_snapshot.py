#!/usr/bin/env python3
"""Export active catalog from Supabase into data/catalog-snapshot.json."""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
ENV_PATH = ROOT / ".env.supabase.local"
SNAPSHOT_PATH = ROOT / "data" / "catalog-snapshot.json"
SCHEMA_VERSION = 1

LISTING_FIELDS = (
    "id",
    "source_kind",
    "source_channel",
    "source_message_id",
    "source_topic_id",
    "slug",
    "title",
    "summary",
    "excerpt",
    "city",
    "location_text",
    "distance_text",
    "beach_text",
    "capacity_text",
    "page_url",
    "telegram_url",
    "published_at",
    "has_video",
    "cover_url",
    "is_active",
    "details",
)

MEDIA_FIELDS = (
    "id",
    "listing_id",
    "media_role",
    "sort_order",
    "mime_type",
    "source_url",
    "storage_bucket",
    "storage_path",
    "public_url",
    "details",
)


def load_env(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    if not path.exists():
        return result
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def fetch_all(base: str, key: str, table: str, select: str, *, extra_params: dict | None = None) -> list[dict]:
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    rows: list[dict] = []
    offset = 0
    limit = 1000
    while True:
        params = {"select": select, "order": "id.asc", "limit": str(limit), "offset": str(offset)}
        if extra_params:
            params.update(extra_params)
        response = requests.get(f"{base}/rest/v1/{table}", headers=headers, params=params, timeout=120)
        response.raise_for_status()
        chunk = response.json()
        if not chunk:
            break
        rows.extend(chunk)
        if len(chunk) < limit:
            break
        offset += limit
    return rows


def normalize_media_url(url: str, mime_type: str = "") -> str:
    from media_urls import media_src_for_html  # noqa: WPS433

    return media_src_for_html(url, mime_type=mime_type)


def normalize_listing(row: dict, media_rows: list[dict]) -> dict:
    cover = normalize_media_url(str(row.get("cover_url") or ""), mime_type="image/jpeg")
    listing = {field: row.get(field) for field in LISTING_FIELDS if field in row}
    listing["cover_url"] = cover
    listing["media"] = []
    for item in sorted(media_rows, key=lambda media: media.get("sort_order") or 0):
        mime = str(item.get("mime_type") or "")
        source_url = normalize_media_url(str(item.get("source_url") or ""), mime_type=mime)
        public_url = normalize_media_url(str(item.get("public_url") or ""), mime_type=mime)
        listing["media"].append(
            {
                "id": item.get("id"),
                "media_role": item.get("media_role"),
                "sort_order": item.get("sort_order"),
                "mime_type": mime,
                "source_url": source_url,
                "storage_bucket": item.get("storage_bucket"),
                "storage_path": item.get("storage_path"),
                "public_url": public_url or source_url,
                "details": item.get("details") or {},
            }
        )
    return listing


def validate_snapshot(listings: list[dict]) -> list[str]:
    issues: list[str] = []
    slugs = [str(row.get("slug") or "") for row in listings]
    slug_counts = Counter(slugs)
    for slug, count in slug_counts.items():
        if count > 1:
            issues.append(f"duplicate slug: {slug} ({count})")

    for row in listings:
        slug = row.get("slug") or "?"
        if not row.get("page_url"):
            issues.append(f"missing page_url: {slug}")
        cover = str(row.get("cover_url") or "")
        if cover and "storage.yandexcloud.net" not in cover:
            issues.append(f"cover not on Yandex: {slug}")
        for media in row.get("media") or []:
            mime = str(media.get("mime_type") or "")
            url = str(media.get("public_url") or media.get("source_url") or "")
            if mime.startswith("video/") and url and "storage.yandexcloud.net" not in url:
                issues.append(f"video not on Yandex: {slug} -> {url[:80]}")
            if mime.startswith("image/") and url and "storage.yandexcloud.net" not in url:
                issues.append(f"image not on Yandex: {slug} -> {url[:80]}")
    return issues


def main() -> int:
    env = load_env(ENV_PATH)
    base = env.get("SUPABASE_URL", "").rstrip("/")
    key = env.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not base or not key:
        print(f"Нужны SUPABASE_URL и SUPABASE_SERVICE_ROLE_KEY в {ENV_PATH}", file=sys.stderr)
        return 1

    listings_raw = fetch_all(
        base,
        key,
        "listings",
        ",".join(LISTING_FIELDS),
        extra_params={"is_active": "eq.true"},
    )
    media_raw = fetch_all(
        base,
        key,
        "listing_media",
        ",".join(MEDIA_FIELDS),
    )
    media_by_listing: dict[int, list[dict]] = defaultdict(list)
    for item in media_raw:
        listing_id = item.get("listing_id")
        if listing_id is not None:
            media_by_listing[int(listing_id)].append(item)

    listings = [
        normalize_listing(row, media_by_listing.get(int(row["id"]), []))
        for row in listings_raw
        if row.get("id") is not None
    ]
    listings.sort(key=lambda row: (row.get("published_at") or "", row.get("id") or 0), reverse=True)

    issues = validate_snapshot(listings)
    snapshot = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "schema_version": SCHEMA_VERSION,
        "source": "supabase-export",
        "listings_total": len(listings),
        "listings_hotels": sum(1 for row in listings if row.get("source_kind") == "hotel"),
        "listings_kvartira": sum(1 for row in listings if row.get("source_kind") == "kvartira"),
        "listings": listings,
    }

    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_PATH.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"snapshot={SNAPSHOT_PATH}")
    print(
        json.dumps(
            {
                "listings_total": snapshot["listings_total"],
                "hotels": snapshot["listings_hotels"],
                "kvartira": snapshot["listings_kvartira"],
                "validation_issues": len(issues),
            },
            ensure_ascii=False,
        )
    )
    for issue in issues[:20]:
        print(f"WARN {issue}")
    if len(issues) > 20:
        print(f"WARN ... and {len(issues) - 20} more")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
