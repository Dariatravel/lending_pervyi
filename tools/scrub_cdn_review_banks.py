#!/usr/bin/env python3
"""Вычистить телефоны и почту из банков отзывов на CDN.

18.08.2026 в отзыве на сайте всплыл номер телефона гостя. Исходный банк
живёт на Mac (media/ вне git), но раздаются гостям нарезки из бакета:
media/reviews/global.json и media/reviews/<slug>/bank.json. Этот скрипт
проходит по ним ПРЯМО В БАКЕТЕ: скачивает, чистит тексты, заливает обратно
только изменённые. Персональные данные в журнал не печатает — только счёт.

Запуск в GitHub Actions (нужны YANDEX_S3_* в env):

    python3 tools/scrub_cdn_review_banks.py           # почистить
    python3 tools/scrub_cdn_review_banks.py --dry-run # только посчитать
"""
from __future__ import annotations

import json
import os
import re
import sys

import boto3

BUCKET = os.getenv("YANDEX_S3_BUCKET", "abhazbereg-media")
ENDPOINT = os.getenv("ENDPOINT", "https://storage.yandexcloud.net")
PREFIX = "media/reviews/"

SEP = r"[\s\-–—.,()]"
PHONE_PATTERNS = [
    # российский мобильный: (+7/8) 9xx xxx-xx-xx в любых разделителях
    re.compile(rf"(?:\+?\s*[78]{SEP}{{0,3}})?9\d{{2}}{SEP}{{0,3}}\d{{3}}{SEP}{{0,3}}\d{{2}}{SEP}{{0,3}}\d{{2}}(?!{SEP}{{0,3}}\d)"),
    # 11 цифр подряд с 7/8 в начале; границы по цифрам, чтобы не задеть цены
    re.compile(rf"(?<!\d)\+?\s*[78]{SEP}{{0,2}}(?:\d{SEP}{{0,2}}){{9}}\d(?!{SEP}{{0,2}}\d)"),
]
EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def scrub_text(value: str) -> str:
    text = value
    for pattern in PHONE_PATTERNS:
        text = pattern.sub(" ", text)
    text = EMAIL_PATTERN.sub(" ", text)
    return re.sub(r"\s{2,}", " ", text).strip()


def scrub_payload(node):
    """Обойти JSON любой формы и почистить все строковые поля text/name."""
    hits = 0
    if isinstance(node, dict):
        for key, value in list(node.items()):
            if isinstance(value, str) and key in ("text", "name", "author", "title"):
                cleaned = scrub_text(value)
                if cleaned != re.sub(r"\s{2,}", " ", value).strip():
                    node[key] = cleaned
                    hits += 1
            else:
                hits += scrub_payload(value)
    elif isinstance(node, list):
        for item in node:
            hits += scrub_payload(item)
    return hits


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    s3 = boto3.client(
        "s3", endpoint_url=ENDPOINT,
        region_name=os.getenv("AWS_DEFAULT_REGION", "ru-central1"),
        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
    )

    keys: list[str] = []
    token = None
    while True:
        kwargs = {"Bucket": BUCKET, "Prefix": PREFIX, "MaxKeys": 1000}
        if token:
            kwargs["ContinuationToken"] = token
        page = s3.list_objects_v2(**kwargs)
        keys += [o["Key"] for o in page.get("Contents", []) if o["Key"].endswith(".json")]
        if not page.get("IsTruncated"):
            break
        token = page.get("NextContinuationToken")

    print(f"Банков отзывов в бакете: {len(keys)}")
    total_hits, changed_files = 0, 0
    for key in keys:
        raw = s3.get_object(Bucket=BUCKET, Key=key)["Body"].read()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            print(f"  ПРОПУСК (не JSON): {key}")
            continue
        hits = scrub_payload(payload)
        if not hits:
            continue
        total_hits += hits
        changed_files += 1
        print(f"  {key}: очищено полей — {hits}")
        if not dry_run:
            s3.put_object(
                Bucket=BUCKET, Key=key,
                Body=json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
                ContentType="application/json; charset=utf-8",
                CacheControl="public, max-age=3600",
                ACL="public-read",
            )

    print(f"\nИтог: файлов с находками {changed_files}, очищенных полей {total_hits}"
          + (" (пробный прогон, ничего не записано)" if dry_run else ""))
    if changed_files and not dry_run:
        print("Не забудь почистить кэш CDN, чтобы гости получили чистые версии.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
