#!/usr/bin/env python3
"""
Upload hero intro MP4s to Supabase Storage bucket `site-media` at videos/hero/...

Requires (environment or .env.supabase.local in repo root):
  SUPABASE_URL=https://chnyazvybzzryduhgopa.supabase.co
  SUPABASE_SERVICE_ROLE_KEY=<service_role JWT from Dashboard → Settings → API>

Small files: standard POST. Large files: TUS resumable (direct storage hostname).

Free plan: max ~50 MB per object — a ~600 MB «high» file will fail until you upgrade
(Pro) or re-encode to under 50 MB. See: Supabase → Storage settings / plan limits.

Optional: pip install tusclient (for resumable uploads)

Usage:
  cd repo && python3 scripts/upload_hero_videos.py
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
BUCKET = "site-media"
OBJECT_PREFIX = "videos/hero"
FILES = (
    "darya-intro-vertical-low.mp4",
    "darya-intro-vertical-high.mp4",
)

# Below this size use POST; above use TUS (Supabase recommends resumable for >6 MB;
# we switch at 40 MiB to avoid edge cases near the 50 MB Free limit on POST).
POST_MAX_BYTES = 40 * 1024 * 1024


def load_env_file(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.is_file():
        return data
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            data[key] = value
    return data


def project_ref_from_url(base: str) -> str:
    m = re.match(r"https://([^.]+)\.supabase\.co/?$", base.rstrip("/"))
    if not m:
        raise ValueError(f"Unexpected SUPABASE_URL (need https://<ref>.supabase.co): {base!r}")
    return m.group(1)


def upload_post(session: requests.Session, base: str, object_path: str, path: Path) -> requests.Response:
    url = f"{base}/storage/v1/object/{BUCKET}/{object_path}"
    with path.open("rb") as f:
        return session.post(
            url,
            data=f,
            headers={
                "Content-Type": "video/mp4",
                "x-upsert": "true",
            },
            timeout=(60, 7200),
        )


def upload_tus(base: str, key: str, object_path: str, path: Path) -> None:
    try:
        from tusclient import client as tus_client
    except ImportError as error:
        raise SystemExit(
            "Large file upload needs TUS. Run: python3 -m pip install tusclient\n"
            f"({error})"
        ) from error

    ref = project_ref_from_url(base)
    tus_endpoint = f"https://{ref}.storage.supabase.co/storage/v1/upload/resumable"
    my_client = tus_client.TusClient(
        tus_endpoint,
        headers={
            "Authorization": f"Bearer {key}",
            "apikey": key,
            "x-upsert": "true",
        },
    )
    with path.open("rb") as fs:
        uploader = my_client.uploader(
            file_stream=fs,
            chunk_size=6 * 1024 * 1024,
            metadata={
                "bucketName": BUCKET,
                "objectName": object_path,
                "contentType": "video/mp4",
                "cacheControl": "3600",
            },
        )
        uploader.upload()


def main() -> int:
    env_path = ROOT / ".env.supabase.local"
    file_env = load_env_file(env_path)
    for k, v in file_env.items():
        os.environ.setdefault(k, v)

    base = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or ""

    if not base or not key:
        print(
            "Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY.\n"
            f"Add them to {env_path} (see scripts/upload_hero_videos.py header) or export in the shell.",
            file=sys.stderr,
        )
        return 1

    session = requests.Session()
    session.headers.update(
        {
            "Authorization": f"Bearer {key}",
            "apikey": key,
        }
    )

    hero_dir = ROOT / "media" / "videos" / "hero"
    any_ok = False
    high_skipped = False

    for name in FILES:
        path = hero_dir / name
        if not path.is_file():
            print(f"Skip (missing): {path}", file=sys.stderr)
            continue
        if path.stat().st_size < 5000:
            print(f"Skip (too small, likely Git LFS pointer): {path}", file=sys.stderr)
            continue

        object_path = f"{OBJECT_PREFIX}/{name}"
        size = path.stat().st_size
        size_mb = size / (1024 * 1024)
        print(f"Uploading {name} ({size_mb:.1f} MiB) …", flush=True)

        try:
            if size <= POST_MAX_BYTES:
                r = upload_post(session, base, object_path, path)
                if r.status_code not in (200, 201):
                    print(f"Failed {r.status_code}: {r.text[:500]}", file=sys.stderr)
                    if r.status_code == 413 and "high" in name:
                        high_skipped = True
                        print(
                            "\nНа бесплатном плане Supabase лимит ~50 МБ на файл. "
                            "Полная версия high (~600 МБ) не влезет без тарифа Pro "
                            "или перекодирования в файл <50 МБ.\n",
                            file=sys.stderr,
                        )
                    return 1
            else:
                upload_tus(base, key, object_path, path)
        except Exception as error:
            err_text = str(error)
            if "413" in err_text or "Payload too large" in err_text or "status 413" in err_text:
                high_skipped = True
                print(
                    f"\nНе удалось загрузить {name}: превышен лимит размера (часто ~50 МБ на Free).\n"
                    "Варианты: тариф Pro в Supabase, или сжать видео до <50 МБ (ffmpeg), "
                    "или оставить только low на сайте.\n",
                    file=sys.stderr,
                )
                continue
            raise

        public = f"{base}/storage/v1/object/public/{BUCKET}/{object_path}"
        print(f"OK: {public}", flush=True)
        any_ok = True

    if not any_ok:
        return 1
    if high_skipped:
        print(
            "\nИтог: low загружен; high пропущен из‑за лимита. "
            "Сайт уже подставляет low, если high недоступен.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
