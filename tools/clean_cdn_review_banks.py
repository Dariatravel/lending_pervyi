#!/usr/bin/env python3
"""Дочистить банки отзывов прямо в бакете: шапки скринов и битые тексты.

25.09.2026 Дарья увидела на странице «Гранта» отзыв, начинающийся с
«Автотурист 31 августа 2025», и второй — «Евгения бо Отдали июне, сиали
домик…»: шапка чужого скрина и текст, который OCR прочёл с ошибками.
Исходный банк живёт на Mac (media/ вне git), а гости читают нарезки из
бакета abhazbereg-media: media/reviews/global.json и
media/reviews/<slug>/bank.json.

Скрипт, как и scrub_cdn_review_banks.py, работает ПРЯМО В БАКЕТЕ:
  * прогоняет каждый текст через общие правила чистки
    (tools/review_text_clean.py — те же, что применяются при сборке банка,
    поэтому пересборка на Mac мусор не вернёт);
  * выбрасывает отзывы из data/review-excludes.json — распознанные криво,
    которые правилом не лечатся;
  * заливает обратно только изменённые файлы.

Тексты отзывов целиком не печатает — только счёт и срезанные шапки.

Запуск в GitHub Actions (ключи YANDEX_S3_* → AWS_* в env), действие
reviews-clean в yandex-site-hosting.yml:

    python3 tools/clean_cdn_review_banks.py            # почистить
    python3 tools/clean_cdn_review_banks.py --dry-run  # только посчитать
"""
from __future__ import annotations

import json
import os
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

import boto3

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

from review_text_clean import (  # noqa: E402
    clean_ocr_review_text,
    is_excluded_review,
    load_review_excludes,
)

BUCKET = os.getenv("YANDEX_S3_BUCKET", "abhazbereg-media")
ENDPOINT = os.getenv("ENDPOINT", "https://storage.yandexcloud.net")
PREFIX = "media/reviews/"
MAX_EXAMPLES = 60


def normalize(text: object) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip().lower()


def clean_reviews(items: list, excludes: list[str], stats: dict) -> list:
    kept = []
    for entry in items:
        if not isinstance(entry, dict):
            kept.append(entry)
            continue
        text = str(entry.get("text") or "")
        # ensure_sentence_end=False — как в сборке банка на Mac
        # (clean_review_text_bank.py): иначе каждому тексту без точки в конце
        # она дописывается, и 118 отзывов выглядят «изменёнными» на ровном месте.
        cleaned = clean_ocr_review_text(text, ensure_sentence_end=False)
        if not cleaned or is_excluded_review(text, excludes) or is_excluded_review(cleaned, excludes):
            stats["dropped"] += 1
            stats["examples"].append(f"выброшен: «{normalize(text)[:45]}…»")
            continue
        if cleaned != text:
            stats["changed"] += 1
            # В журнал — только то, что убрано, не сам отзыв: срезанная шапка
            # или удалённые фрагменты (до трёх, по 70 знаков), чтобы по отчёту
            # пробного прогона было видно, какое правило сработало.
            if text.endswith(cleaned):
                head = text[: -len(cleaned)].strip() if cleaned else text.strip()
                stats["examples"].append(f"срезано: «{head[:60]}»")
            else:
                removed = [
                    text[i1:i2].strip()
                    for tag, i1, i2, _j1, _j2 in SequenceMatcher(None, text, cleaned).get_opcodes()
                    if tag in ("delete", "replace") and text[i1:i2].strip()
                ][:3]
                stats["examples"].append(
                    "убрано внутри: " + " | ".join(f"«{piece[:70]}»" for piece in removed)
                    if removed else "изменено внутри текста"
                )
            entry["text"] = cleaned
        kept.append(entry)
    return kept


def clean_payload(payload: dict, excludes: list[str], stats: dict) -> bool:
    """Почистить global.json («global») или bank.json («reviews»). True — были правки."""
    before = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    for key in ("global", "reviews"):
        items = payload.get(key)
        if isinstance(items, list):
            payload[key] = clean_reviews(items, excludes, stats)
    stats_block = payload.get("stats")
    if isinstance(stats_block, dict) and isinstance(payload.get("global"), list):
        stats_block["global_total"] = len(payload["global"])
    return json.dumps(payload, ensure_ascii=False, sort_keys=True) != before


def list_bank_keys(s3) -> list[str]:
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
    return keys


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    excludes = load_review_excludes()
    s3 = boto3.client(
        "s3", endpoint_url=ENDPOINT,
        region_name=os.getenv("AWS_DEFAULT_REGION", "ru-central1"),
        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
    )

    keys = list_bank_keys(s3)
    print(f"Банков отзывов в бакете: {len(keys)}; фрагментов-исключений: {len(excludes)}")
    stats = {"changed": 0, "dropped": 0, "examples": []}
    changed_files = 0
    for key in keys:
        raw = s3.get_object(Bucket=BUCKET, Key=key)["Body"].read()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            print(f"  ПРОПУСК (не JSON): {key}")
            continue
        if not isinstance(payload, dict):
            continue
        file_stats = {"changed": 0, "dropped": 0, "examples": []}
        if not clean_payload(payload, excludes, file_stats):
            continue
        changed_files += 1
        for field in ("changed", "dropped"):
            stats[field] += file_stats[field]
        stats["examples"] += file_stats["examples"]
        print(f"  {key}: поправлено {file_stats['changed']}, выброшено {file_stats['dropped']}")
        if not dry_run:
            s3.put_object(
                Bucket=BUCKET, Key=key,
                Body=json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
                ContentType="application/json; charset=utf-8",
                CacheControl="public, max-age=3600",
                ACL="public-read",
            )

    if stats["examples"]:
        print("\nЧто именно (без текстов отзывов):")
        for line in stats["examples"][:MAX_EXAMPLES]:
            print(f"  {line}")
        if len(stats["examples"]) > MAX_EXAMPLES:
            print(f"  … и ещё {len(stats['examples']) - MAX_EXAMPLES}")

    print(f"\nИтог: файлов изменено {changed_files}, текстов поправлено {stats['changed']}, "
          f"выброшено {stats['dropped']}"
          + (" (пробный прогон, ничего не записано)" if dry_run else ""))
    if changed_files and not dry_run:
        print("Не забудь почистить кэш CDN, чтобы гости получили чистые версии.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
