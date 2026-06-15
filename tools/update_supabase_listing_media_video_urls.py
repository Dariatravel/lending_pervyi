#!/usr/bin/env python3
"""Patch listing_media video rows in Supabase: public_url/source_url → Yandex."""

from __future__ import annotations

import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from media_urls import yandex_video_url  # noqa: E402

ENV_PATH = ROOT / ".env.supabase.local"


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


def main() -> int:
    env = load_env(ENV_PATH)
    base = env.get("SUPABASE_URL", "").rstrip("/")
    key = env.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not base or not key:
        print(f"Need SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in {ENV_PATH}", file=sys.stderr)
        return 1

    headers = {"apikey": key, "Authorization": f"Bearer {key}", "Prefer": "return=minimal"}
    response = requests.get(
        f"{base}/rest/v1/listing_media",
        headers=headers,
        params={
            "select": "id,mime_type,public_url,source_url,storage_path",
            "mime_type": "like.video/%",
            "limit": "10000",
            "order": "id.asc",
        },
        timeout=120,
    )
    response.raise_for_status()
    rows = response.json()

    updated = 0
    skipped = 0
    for row in rows:
        row_id = row["id"]
        old_public = str(row.get("public_url") or "").strip()
        old_source = str(row.get("source_url") or "").strip()
        new_public = yandex_video_url(old_public or old_source)
        new_source = yandex_video_url(old_source or old_public)
        if not new_public.startswith("https://storage.yandexcloud.net/"):
            skipped += 1
            continue
        if new_public == old_public and new_source == old_source:
            skipped += 1
            continue
        patch = {
            "public_url": new_public,
            "source_url": new_source,
            "storage_bucket": "abhazbereg-media",
        }
        patch_response = requests.patch(
            f"{base}/rest/v1/listing_media",
            headers=headers,
            params={"id": f"eq.{row_id}"},
            json=patch,
            timeout=60,
        )
        patch_response.raise_for_status()
        updated += 1

    print(f"video_rows={len(rows)} updated={updated} skipped={skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
