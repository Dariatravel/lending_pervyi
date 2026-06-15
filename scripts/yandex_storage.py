"""Upload site media files to Yandex Object Storage."""

from __future__ import annotations

import mimetypes
import os
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

from media_urls import YANDEX_MEDIA_BASE

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env.yandex.local"


def load_yandex_env() -> None:
    if not ENV_PATH.exists():
        return
    for raw in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def yandex_object_key(storage_path: str) -> str:
    path = storage_path.lstrip("/")
    return path if path.startswith("media/") else f"media/{path}"


def yandex_public_url(storage_path: str) -> str:
    key = yandex_object_key(storage_path)
    relative = key[len("media/") :] if key.startswith("media/") else key
    return f"{YANDEX_MEDIA_BASE}/media/{relative}"


def _s3_client():
    load_yandex_env()
    access_key = os.environ.get("YANDEX_S3_ACCESS_KEY_ID") or os.environ.get("AWS_ACCESS_KEY_ID", "")
    secret_key = os.environ.get("YANDEX_S3_SECRET_ACCESS_KEY") or os.environ.get("AWS_SECRET_ACCESS_KEY", "")
    endpoint = os.environ.get("YANDEX_S3_ENDPOINT") or os.environ.get("AWS_ENDPOINT_URL", "https://storage.yandexcloud.net")
    region = os.environ.get("YANDEX_S3_REGION") or os.environ.get("AWS_DEFAULT_REGION", "ru-central1")
    if not access_key or not secret_key:
        raise RuntimeError(f"Нет S3-ключей в {ENV_PATH}")
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        region_name=region,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
    )


def _object_size_matches(s3, bucket: str, key: str, size: int) -> bool:
    try:
        response = s3.head_object(Bucket=bucket, Key=key)
    except ClientError as error:
        code = str(error.response.get("Error", {}).get("Code", ""))
        if code in {"404", "NoSuchKey", "NotFound"}:
            return False
        raise
    return int(response.get("ContentLength", -1)) == size


def upload_file(
    local_path: Path,
    storage_path: str,
    mime_type: str | None = None,
    *,
    force: bool = False,
) -> str:
    """Upload a local file; return public Yandex URL."""
    load_yandex_env()
    bucket = os.environ.get("YANDEX_S3_BUCKET", "abhazbereg-media")
    key = yandex_object_key(storage_path)
    size = local_path.stat().st_size
    s3 = _s3_client()
    if not force and size > 0 and _object_size_matches(s3, bucket, key, size):
        return yandex_public_url(storage_path)
    content_type = mime_type or mimetypes.guess_type(local_path.name)[0] or "application/octet-stream"
    s3.upload_file(
        str(local_path),
        bucket,
        key,
        ExtraArgs={
            "ContentType": content_type,
            "CacheControl": "public, max-age=31536000, immutable",
        },
    )
    return yandex_public_url(storage_path)
