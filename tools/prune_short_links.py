#!/usr/bin/env python3
"""Удалить осиротевшие короткие ссылки из обоих бакетов.

Заливка сайта и редиректора только добавляет и обновляет файлы: когда
короткая ссылка исчезает из data/short-links*.json (объект снят с сайта),
её страницы-стрелки остаются в бакетах навсегда. Появился 08.09.2026 после
снятия «АФИНЫ»: /afina пропала из репозитория, но продолжала отвечать
с обоих доменов.

Что делает:
- бакет abhazbereg-ru-redirect (полностью управляется build_ru_redirector):
  перечисляет объекты и удаляет всё, что не входит в законное множество —
  переезды Тильды (old-site-redirects.json), короткие ссылки
  (short-links*.json, оба написания ключа) и error.html;
- бакет сайта abhazbereg-site: удаляет только `<ключ>/index.html` для ключей,
  переданных через PRUNE_KEYS (точечно и явно — этот бакет большой, автоматике
  в нём удалять нельзя).

Запуск (GitHub Actions, ключи YANDEX_S3_* в окружении):
    PRUNE_KEYS=afina python3 tools/prune_short_links.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import boto3

ROOT = Path(__file__).resolve().parents[1]
ENDPOINT = os.getenv("ENDPOINT", "https://storage.yandexcloud.net")
RU_BUCKET = "abhazbereg-ru-redirect"
SITE_BUCKET = "abhazbereg-site"


def s3_client():
    return boto3.client(
        "s3",
        endpoint_url=ENDPOINT,
        region_name=os.getenv("AWS_DEFAULT_REGION", "ru-central1"),
        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
    )


def load_links(name: str) -> dict[str, str]:
    try:
        data = json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {str(k): str(v) for k, v in (data.get("links") or {}).items()}


def valid_ru_keys() -> set[str]:
    keys = {"error.html"}
    try:
        redirects = json.loads((ROOT / "data" / "old-site-redirects.json").read_text(encoding="utf-8"))["redirects"]
    except (OSError, json.JSONDecodeError, KeyError):
        redirects = {}
    for path in redirects:
        keys.add(path.lstrip("/") or "index.html")
    for name in ("short-links.json", "short-links-generated.json"):
        for key in load_links(name):
            keys.add(key)
            keys.add(f"{key}/index.html")
    return keys


def list_keys(s3, bucket: str) -> list[str]:
    keys: list[str] = []
    token = None
    while True:
        kwargs = {"Bucket": bucket}
        if token:
            kwargs["ContinuationToken"] = token
        page = s3.list_objects_v2(**kwargs)
        keys += [obj["Key"] for obj in page.get("Contents", [])]
        token = page.get("NextContinuationToken")
        if not token:
            return keys


def main() -> int:
    s3 = s3_client()

    valid = valid_ru_keys()
    removed_ru = 0
    for key in list_keys(s3, RU_BUCKET):
        if key not in valid:
            s3.delete_object(Bucket=RU_BUCKET, Key=key)
            print(f"  {RU_BUCKET}: удалён {key}")
            removed_ru += 1
    print(f"Редиректор abhazbereg.ru: удалено осиротевших объектов {removed_ru}")

    prune_keys = [k.strip().strip("/") for k in os.getenv("PRUNE_KEYS", "").split(",") if k.strip()]
    current = set(load_links("short-links.json")) | set(load_links("short-links-generated.json"))
    removed_site = 0
    for key in prune_keys:
        if key in current:
            print(f"  {SITE_BUCKET}: /{key} всё ещё в манифестах — пропуск")
            continue
        if (ROOT / key / "index.html").is_file():
            print(f"  {SITE_BUCKET}: папка {key}/ существует в репозитории — пропуск")
            continue
        s3.delete_object(Bucket=SITE_BUCKET, Key=f"{key}/index.html")
        s3.delete_object(Bucket=SITE_BUCKET, Key=key)
        print(f"  {SITE_BUCKET}: удалён {key}/index.html")
        removed_site += 1
    print(f"Бакет сайта: удалено ключей {removed_site} (запрошено {len(prune_keys)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
