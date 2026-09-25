#!/usr/bin/env python3
"""Лёгкие WebP-копии оформления главной: иконки мессенджеров и обложка видео.

25.09.2026 Lighthouse главной: иконки контактов показываются 42×42 px, а
файлы — крупные PNG (ВК 68 КБ, Telegram 35 КБ); обложка видео-приветствия —
JPEG 100 КБ. Всё это грузится, пока идёт главная картинка первого экрана,
и отъедает у неё медленный мобильный канал.

Скрипт скачивает исходники с медиа-CDN, делает WebP нужного размера и кладёт
РЯДОМ с исходником под новым именем (…-128.webp, …-web.webp). Старые файлы не
трогаются: пока стили ссылаются на них, всё работает как раньше. Существующий
файл с тем же новым именем не перезаписывается без --force.

Запуск в GitHub Actions (ключи YANDEX_S3_* → AWS_* в env):
    python3 tools/optimize_branding_assets.py            # сделать и залить
    python3 tools/optimize_branding_assets.py --dry-run  # только посчитать
"""
from __future__ import annotations

import io
import os
import sys
import urllib.request

from PIL import Image

BUCKET = os.getenv("YANDEX_S3_BUCKET", "abhazbereg-media")
ENDPOINT = os.getenv("ENDPOINT", "https://storage.yandexcloud.net")
CDN = "https://media.xn--80aacbklan7f0b.xn--p1ai"

# (исходник, новое имя, наибольшая сторона в px, качество WebP)
# Иконки: 42 px на экране × DPR 3 = 126 → 128 px.
JOBS = [
    ("media/branding/icon-vk-circle.png", "media/branding/icon-vk-circle-128.webp", 128, 90),
    ("media/branding/icon-tg-circle.png", "media/branding/icon-tg-circle-128.webp", 128, 90),
    ("media/branding/icon-wa-circle.png", "media/branding/icon-wa-circle-128.webp", 128, 90),
    ("media/branding/icon-max-circle.png", "media/branding/icon-max-circle-128.webp", 128, 90),
    # Обложка видео: размер прежний, меняется только формат.
    ("media/branding/hero-video-poster.jpg", "media/branding/hero-video-poster-web.webp", 0, 80),
]


def fetch(key: str) -> bytes:
    request = urllib.request.Request(f"{CDN}/{key}", headers={"User-Agent": "abhazbereg-branding-optimizer"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def convert(data: bytes, max_side: int, quality: int) -> tuple[bytes, tuple[int, int], tuple[int, int]]:
    image = Image.open(io.BytesIO(data))
    before = image.size
    image = image.convert("RGBA" if image.mode in ("RGBA", "LA", "P") else "RGB")
    if max_side and max(image.size) > max_side:
        image.thumbnail((max_side, max_side), Image.LANCZOS)
    out = io.BytesIO()
    image.save(out, "WEBP", quality=quality, method=6)
    return out.getvalue(), before, image.size


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    force = "--force" in sys.argv
    s3 = None
    if not dry_run:
        import boto3

        s3 = boto3.client("s3", endpoint_url=ENDPOINT,
                          region_name=os.getenv("AWS_DEFAULT_REGION", "ru-central1"))
    failures = 0
    for source, target, max_side, quality in JOBS:
        try:
            raw = fetch(source)
            webp, before, after = convert(raw, max_side, quality)
        except Exception as error:  # noqa: BLE001
            failures += 1
            print(f"  ОШИБКА {source}: {error}")
            continue
        line = (f"  {source}: {len(raw) // 1024} КБ {before[0]}×{before[1]} → "
                f"{target.rsplit('/', 1)[-1]}: {len(webp) // 1024} КБ {after[0]}×{after[1]}")
        if dry_run:
            print(line + " (пробный прогон)")
            continue
        if not force:
            try:
                s3.head_object(Bucket=BUCKET, Key=target)
                print(line + " — уже есть, не перезаписываю")
                continue
            except Exception:  # noqa: BLE001 — нет файла, заливаем
                pass
        s3.put_object(Bucket=BUCKET, Key=target, Body=webp, ContentType="image/webp",
                      CacheControl="public, max-age=31536000, immutable", ACL="public-read")
        print(line + " — залито")
    print(f"\nИтог: файлов {len(JOBS)}, ошибок {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
