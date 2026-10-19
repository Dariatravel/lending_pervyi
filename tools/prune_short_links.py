#!/usr/bin/env python3
"""Показать короткие ссылки в бакетах сверх реестров. НИЧЕГО НЕ УДАЛЯЕТ.

С 19.10.2026 ссылки не удаляются никогда (Дарья: «ссылки вообще нельзя
удалять» — они уже размещены). Ниже — прежнее описание, для истории.

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

    # Дарья 19.10.2026: «ссылки вообще нельзя удалять» — они уже размещены в
    # постах и рассылках. Скрипт больше ничего не удаляет, только показывает,
    # что лежит в бакетах сверх реестров (для сверки руками).
    valid = valid_ru_keys()
    extra_ru = [key for key in list_keys(s3, RU_BUCKET) if key not in valid]
    for key in extra_ru:
        print(f"  {RU_BUCKET}: вне реестров (оставлен) {key}")
    print(f"Редиректор abhazbereg.ru: вне реестров {len(extra_ru)}, удалено 0")

    prune_keys = [k.strip().strip("/") for k in os.getenv("PRUNE_KEYS", "").split(",") if k.strip()]
    if prune_keys:
        print(f"Бакет сайта: запрошено удалить {len(prune_keys)} — не удаляю, ссылки удалять нельзя")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
