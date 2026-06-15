#!/usr/bin/env python3
"""Copy Supabase public videos to Yandex Object Storage."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import boto3
import requests
from botocore.exceptions import ClientError, NoCredentialsError

ROOT = Path(__file__).resolve().parents[1]
ENV_SUPABASE = ROOT / ".env.supabase.local"
ENV_YANDEX = ROOT / ".env.yandex.local"
DEFAULT_ARCHIVE = ROOT / "output" / "supabase_archive_2026-06-13" / "listing_media.json"
SUPABASE_PUBLIC_BASE = "https://chnyazvybzzryduhgopa.supabase.co/storage/v1/object/public/site-media"
HERO_VIDEO_JOBS = (
    {"storage_path": "videos/hero/darya-intro-vertical-high.mp4", "public_url": f"{SUPABASE_PUBLIC_BASE}/videos/hero/darya-intro-vertical-high.mp4", "mime_type": "video/mp4"},
    {"storage_path": "videos/hero/darya-intro-vertical-low.mp4", "public_url": f"{SUPABASE_PUBLIC_BASE}/videos/hero/darya-intro-vertical-low.mp4", "mime_type": "video/mp4"},
)


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def yandex_key_for_storage_path(storage_path: str) -> str:
    path = storage_path.lstrip("/")
    if path.startswith("media/"):
        return path
    return f"media/{path}"


def yandex_client():
    load_env(ENV_YANDEX)
    access_key = os.environ.get("YANDEX_S3_ACCESS_KEY_ID") or os.environ.get("AWS_ACCESS_KEY_ID", "")
    secret_key = os.environ.get("YANDEX_S3_SECRET_ACCESS_KEY") or os.environ.get("AWS_SECRET_ACCESS_KEY", "")
    bucket = os.environ.get("YANDEX_S3_BUCKET", "abhazbereg-media")
    endpoint = os.environ.get("YANDEX_S3_ENDPOINT") or os.environ.get("AWS_ENDPOINT_URL", "https://storage.yandexcloud.net")
    region = os.environ.get("YANDEX_S3_REGION") or os.environ.get("AWS_DEFAULT_REGION", "ru-central1")
    if not access_key or not secret_key:
        raise RuntimeError("Нет S3-ключей в .env.yandex.local")
    s3 = boto3.client(
        "s3",
        endpoint_url=endpoint,
        region_name=region,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
    )
    return s3, bucket


def collect_video_jobs(archive_path: Path) -> list[dict]:
    rows = json.loads(archive_path.read_text(encoding="utf-8"))
    seen: set[str] = set()
    jobs: list[dict] = []
    for row in rows:
        mime = str(row.get("mime_type") or "")
        if not mime.startswith("video/"):
            continue
        storage_path = str(row.get("storage_path") or "").strip()
        public_url = str(row.get("public_url") or row.get("source_url") or "").strip()
        if not storage_path or not public_url:
            continue
        if storage_path in seen:
            continue
        seen.add(storage_path)
        jobs.append({"storage_path": storage_path, "public_url": public_url, "mime_type": mime})
    for hero in HERO_VIDEO_JOBS:
        path = hero["storage_path"]
        if path not in seen:
            seen.add(path)
            jobs.append(hero)
    return jobs


def object_size_matches(s3, bucket: str, key: str, size: int) -> bool:
    try:
        response = s3.head_object(Bucket=bucket, Key=key)
    except ClientError as error:
        code = str(error.response.get("Error", {}).get("Code", ""))
        if code in {"404", "NoSuchKey", "NotFound"}:
            return False
        raise
    return int(response.get("ContentLength", -1)) == size


def process_job(job: dict, *, dry_run: bool, force: bool) -> tuple[str, str]:
    s3, bucket = yandex_client()
    key = yandex_key_for_storage_path(job["storage_path"])
    source_url = job["public_url"]

    try:
        head = requests.head(source_url, timeout=60, allow_redirects=True)
        if head.status_code >= 400:
            get = requests.get(source_url, stream=True, timeout=120)
            get.raise_for_status()
            size = int(get.headers.get("Content-Length", 0))
            get.close()
        else:
            size = int(head.headers.get("Content-Length", 0))
    except requests.RequestException as error:
        return "error", f"{key}: source unavailable ({error})"

    if not force and size > 0 and object_size_matches(s3, bucket, key, size):
        return "skipped", key

    if dry_run:
        return "would_upload", key

    response = requests.get(source_url, timeout=600)
    response.raise_for_status()
    data = response.content
    mime = job.get("mime_type") or mimetypes.guess_type(key)[0] or "video/mp4"
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=data,
        ContentType=mime,
        CacheControl="public, max-age=31536000, immutable",
    )
    return "uploaded", key


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate Supabase videos to Yandex Object Storage")
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    if not args.archive.exists():
        print(f"Archive not found: {args.archive}", file=sys.stderr)
        return 1

    jobs = collect_video_jobs(args.archive)
    print(f"video_jobs={len(jobs)}")

    uploaded = skipped = errors = 0
    worker_count = max(1, min(args.workers, 16))
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = [
            executor.submit(process_job, job, dry_run=args.dry_run, force=args.force)
            for job in jobs
        ]
        for future in as_completed(futures):
            status, detail = future.result()
            if status == "skipped":
                skipped += 1
            elif status == "error":
                errors += 1
                print(f"ERROR {detail}")
            else:
                uploaded += 1
                action = "would upload" if status == "would_upload" else "uploaded"
                print(f"{action} {detail}")

    mode = "dry-run" if args.dry_run else "done"
    print(f"{mode}: uploaded={uploaded} skipped={skipped} errors={errors}")
    return 1 if errors else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except NoCredentialsError:
        print("Нет S3-ключей. Создайте .env.yandex.local по примеру .env.yandex.example.")
        raise SystemExit(2)
