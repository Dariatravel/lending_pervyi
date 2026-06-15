#!/usr/bin/env python3
"""Export Supabase listings/media and build a storage manifest for migration archive."""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import requests

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env.supabase.local"
OUTPUT_ROOT = ROOT / "output"
BUCKET = "site-media"
TOP_PREFIXES = (
    "cards/",
    "hotels/",
    "kvartira/",
    "kvartira-cards/",
    "branding/",
    "blog/",
    "reviews/",
    "videos/",
    "hero/",
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


def session(base: str, key: str) -> requests.Session:
    s = requests.Session()
    s.headers.update({"apikey": key, "Authorization": f"Bearer {key}"})
    s.base_url = base  # type: ignore[attr-defined]
    return s


def fetch_all(s: requests.Session, table: str, select: str) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    limit = 1000
    while True:
        response = s.get(
            f"{s.base_url}/rest/v1/{table}",
            params={
                "select": select,
                "order": "id.asc",
                "limit": str(limit),
                "offset": str(offset),
            },
            timeout=120,
        )
        response.raise_for_status()
        chunk = response.json()
        if not chunk:
            break
        rows.extend(chunk)
        if len(chunk) < limit:
            break
        offset += limit
    return rows


def list_storage_prefix(s: requests.Session, prefix: str, limit: int = 1000) -> list[dict]:
    encoded_bucket = quote(BUCKET, safe="")
    url = f"{s.base_url}/storage/v1/object/list/{encoded_bucket}"
    payload = {"prefix": prefix, "limit": limit, "offset": 0}
    response = s.post(url, json=payload, timeout=120)
    response.raise_for_status()
    return response.json() or []


def classify_path(path: str) -> str:
    p = (path or "").lstrip("/")
    for prefix in TOP_PREFIXES:
        if p.startswith(prefix):
            return prefix.rstrip("/")
    top = p.split("/", 1)[0] if p else "unknown"
    return top or "unknown"


def build_storage_manifest(
    s: requests.Session,
    media_rows: list[dict],
) -> dict:
    by_prefix_db: Counter[str] = Counter()
    by_mime_db: Counter[str] = Counter()
    supabase_urls = 0
    yandex_urls = 0
    local_like = 0

    for row in media_rows:
        path = str(row.get("storage_path") or "").strip()
        if path:
            by_prefix_db[classify_path(path)] += 1
        mime = str(row.get("mime_type") or "unknown").strip() or "unknown"
        by_mime_db[mime] += 1
        url = str(row.get("public_url") or row.get("source_url") or "").strip()
        if "supabase.co/storage" in url:
            supabase_urls += 1
        elif "storage.yandexcloud.net" in url:
            yandex_urls += 1
        elif url.startswith("/media/") or url.startswith("media/"):
            local_like += 1

    bucket_prefixes: dict[str, dict] = {}
    for prefix in TOP_PREFIXES:
        try:
            items = list_storage_prefix(s, prefix)
        except requests.HTTPError as error:
            bucket_prefixes[prefix.rstrip("/")] = {
                "listed_count": 0,
                "error": str(error),
            }
            continue
        bucket_prefixes[prefix.rstrip("/")] = {
            "listed_count": len(items),
            "sample_names": [item.get("name") for item in items[:5] if item.get("name")],
        }

    return {
        "bucket": BUCKET,
        "listing_media_rows": len(media_rows),
        "by_prefix_from_db": dict(sorted(by_prefix_db.items())),
        "by_mime_from_db": dict(sorted(by_mime_db.items())),
        "url_sources": {
            "supabase_storage": supabase_urls,
            "yandex_object_storage": yandex_urls,
            "local_like_paths": local_like,
        },
        "bucket_prefix_listing": bucket_prefixes,
    }


def main() -> int:
    env = load_env(ENV_PATH)
    base = env.get("SUPABASE_URL", "").rstrip("/")
    key = env.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not base or not key:
        print(f"Нужны SUPABASE_URL и SUPABASE_SERVICE_ROLE_KEY в {ENV_PATH}", file=sys.stderr)
        return 1

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_dir = OUTPUT_ROOT / f"supabase_archive_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    s = session(base, key)
    listings = fetch_all(
        s,
        "listings",
        "id,source_kind,source_channel,source_message_id,source_topic_id,slug,title,summary,excerpt,city,location_text,distance_text,beach_text,capacity_text,page_url,telegram_url,published_at,has_video,cover_url,is_active,details,created_at,updated_at",
    )
    media = fetch_all(
        s,
        "listing_media",
        "id,listing_id,media_role,sort_order,mime_type,source_url,storage_bucket,storage_path,public_url,details,created_at,updated_at",
    )
    manifest = build_storage_manifest(s, media)

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "supabase_url": base,
        "listings_total": len(listings),
        "listings_active": sum(1 for row in listings if row.get("is_active")),
        "listings_hotels": sum(1 for row in listings if row.get("source_kind") == "hotel"),
        "listings_kvartira": sum(1 for row in listings if row.get("source_kind") == "kvartira"),
        "listing_media_total": len(media),
        "listing_media_video": sum(1 for row in media if str(row.get("mime_type") or "").startswith("video/")),
        "listing_media_image": sum(1 for row in media if str(row.get("mime_type") or "").startswith("image/")),
    }

    (out_dir / "listings.json").write_text(
        json.dumps(listings, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out_dir / "listing_media.json").write_text(
        json.dumps(media, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out_dir / "storage_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"archive_dir={out_dir}")
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
