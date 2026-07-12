#!/usr/bin/env python3
"""Дозалить недостающие WebP-варианты (-480/-960/-1440) для фото в бакете.

Страницы ссылаются на варианты через srcset; если варианта нет — браузер
показывает битое фото (отката на src у srcset не бывает). Скрипт обходит
бакет, находит .jpg без вариантов, скачивает, конвертирует (Pillow) и заливает.

Запуск (нужны YANDEX_S3_ACCESS_KEY_ID/SECRET в env):
    python3 tools/backfill_image_variants.py                # всё
    python3 tools/backfill_image_variants.py --prefix media/kvartira/
    python3 tools/backfill_image_variants.py --dry-run --limit 20
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from image_variants import RESPONSIVE_WIDTHS, build_webp_variants, variant_key  # noqa: E402
from yandex_storage import load_yandex_env  # noqa: E402

import boto3  # noqa: E402
import os  # noqa: E402

PREFIXES = (
    "media/cards/",
    "media/kvartira-cards/",
    "media/hotels/",
    "media/kvartira/",
)


def s3_client():
    load_yandex_env()
    return boto3.client(
        "s3",
        endpoint_url=os.environ.get("YANDEX_S3_ENDPOINT", "https://storage.yandexcloud.net"),
        region_name=os.environ.get("YANDEX_S3_REGION", "ru-central1"),
        aws_access_key_id=os.environ.get("YANDEX_S3_ACCESS_KEY_ID") or os.environ.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("YANDEX_S3_SECRET_ACCESS_KEY") or os.environ.get("AWS_SECRET_ACCESS_KEY"),
    )


def list_keys(s3, bucket: str, prefix: str) -> list[str]:
    keys: list[str] = []
    token = None
    while True:
        kwargs = {"Bucket": bucket, "Prefix": prefix, "MaxKeys": 1000}
        if token:
            kwargs["ContinuationToken"] = token
        resp = s3.list_objects_v2(**kwargs)
        keys.extend(obj["Key"] for obj in resp.get("Contents") or [])
        if not resp.get("IsTruncated"):
            return keys
        token = resp.get("NextContinuationToken")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefix", default="", help="Обрабатывать только этот префикс бакета.")
    parser.add_argument("--limit", type=int, default=0, help="Максимум JPG для обработки (0 — без лимита).")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    bucket = os.environ.get("YANDEX_S3_BUCKET", "abhazbereg-media")
    s3 = s3_client()
    prefixes = [args.prefix] if args.prefix else list(PREFIXES)

    processed = fixed = failed = 0
    for prefix in prefixes:
        keys = set(list_keys(s3, bucket, prefix))
        jpgs = sorted(
            k for k in keys
            if k.lower().endswith((".jpg", ".jpeg")) and "/supplemental/" not in k
        )
        print(f"{prefix}: файлов jpg = {len(jpgs)}", flush=True)
        for key in jpgs:
            missing = [w for w in RESPONSIVE_WIDTHS if variant_key(key, w) not in keys]
            if not missing:
                continue
            processed += 1
            if args.limit and processed > args.limit:
                print("Достигнут --limit, остановка.")
                return 0
            if args.dry_run:
                print(f"[dry] {key}: нет {missing}")
                continue
            try:
                blob = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
                variants = build_webp_variants(blob)
                for width, data in variants:
                    if variant_key(key, width) in keys:
                        continue
                    s3.put_object(
                        Bucket=bucket,
                        Key=variant_key(key, width),
                        Body=data,
                        ContentType="image/webp",
                    )
                fixed += 1
                if fixed % 25 == 0:
                    print(f"  … дозалито {fixed}", flush=True)
            except Exception as error:  # noqa: BLE001
                failed += 1
                print(f"[err] {key}: {error}", flush=True)
    print(f"Итог: требовали вариантов={processed}, дозалито={fixed}, ошибок={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
