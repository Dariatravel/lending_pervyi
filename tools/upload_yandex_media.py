#!/usr/bin/env python3
"""Upload local media folders to Yandex Object Storage.

Reads credentials from environment or .env.yandex.local. The destination keys
match the repository paths, for example media/blog/telegram-3821.jpg.
"""

from __future__ import annotations

import argparse
import mimetypes
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import boto3
from botocore.exceptions import ClientError, NoCredentialsError


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FOLDERS = ("media/blog", "media/videos")


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def env_value(*names: str, default: str = "") -> str:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return default


def iter_files(folders: list[str]) -> list[Path]:
    files: list[Path] = []
    for folder in folders:
        root = ROOT / folder
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file() and path.name != ".DS_Store":
                files.append(path)
    return sorted(files)


def content_type(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(path.name)
    if guessed:
        return guessed
    return "application/octet-stream"


def object_matches(s3, bucket: str, key: str, path: Path) -> bool:
    try:
        response = s3.head_object(Bucket=bucket, Key=key)
    except ClientError as error:
        code = str(error.response.get("Error", {}).get("Code", ""))
        if code in {"404", "NoSuchKey", "NotFound"}:
            return False
        raise
    return int(response.get("ContentLength", -1)) == path.stat().st_size


def main() -> int:
    parser = argparse.ArgumentParser(description="Upload media to Yandex Object Storage")
    parser.add_argument("folders", nargs="*", default=list(DEFAULT_FOLDERS))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true", help="upload even if object size matches")
    parser.add_argument("--workers", type=int, default=16, help="parallel S3 checks/uploads")
    args = parser.parse_args()

    load_env_file(ROOT / ".env.yandex.local")

    access_key = env_value("YANDEX_S3_ACCESS_KEY_ID", "AWS_ACCESS_KEY_ID")
    secret_key = env_value("YANDEX_S3_SECRET_ACCESS_KEY", "AWS_SECRET_ACCESS_KEY")
    bucket = env_value("YANDEX_S3_BUCKET", default="abhazbereg-media")
    endpoint = env_value("YANDEX_S3_ENDPOINT", "AWS_ENDPOINT_URL", default="https://storage.yandexcloud.net")
    region = env_value("YANDEX_S3_REGION", "AWS_DEFAULT_REGION", default="ru-central1")

    if not access_key or not secret_key:
        print("Нет S3-ключей. Создайте .env.yandex.local по примеру .env.yandex.example.")
        return 2

    s3 = boto3.client(
        "s3",
        endpoint_url=endpoint,
        region_name=region,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
    )

    def process_file(path: Path) -> tuple[str, str]:
        key = path.relative_to(ROOT).as_posix()
        if not args.force and object_matches(s3, bucket, key, path):
            return "skipped", key
        extra_args = {
            "ContentType": content_type(path),
            "CacheControl": "public, max-age=31536000, immutable",
        }
        if args.dry_run:
            return "would_upload", key
        s3.upload_file(str(path), bucket, key, ExtraArgs=extra_args)
        return "uploaded", key

    files = iter_files(args.folders)
    uploaded = skipped = checked = 0
    worker_count = max(1, min(args.workers, 64))
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = [executor.submit(process_file, path) for path in files]
        for future in as_completed(futures):
            status, key = future.result()
            checked += 1
            if status == "skipped":
                skipped += 1
            else:
                uploaded += 1
                action = "would upload" if status == "would_upload" else "uploaded"
                print(f"{action} {key}")

    mode = "dry-run" if args.dry_run else "done"
    print(f"{mode}: checked={checked} uploaded={uploaded} skipped={skipped}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except NoCredentialsError:
        print("Нет S3-ключей. Создайте .env.yandex.local по примеру .env.yandex.example.")
        raise SystemExit(2)
