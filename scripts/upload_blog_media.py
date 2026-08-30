#!/usr/bin/env python3
"""Залить обложки статей блога в Яндекс вместе с WebP-вариантами.

Страницы блога ссылаются на -480/-960/-1440.webp через srcset, поэтому
просто скопировать JPG недостаточно — без вариантов фото «пропадает»
(железное правило №3 в CLAUDE.md).

    TARGET_BLOG_POST_IDS=2460,2461 python3 scripts/upload_blog_media.py
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from image_variants import build_webp_variants_for_file, variant_key  # noqa: E402
from sync_blog_from_abhazbereg import CHANNEL, post_channel  # noqa: E402
from yandex_storage import upload_file  # noqa: E402

MEDIA_DIR = ROOT / "media" / "blog"


def cover_name(post_id: int) -> str:
    """То же правило имён, что в sync_posts: посты не из @abhazbereg
    получают имя с каналом (telegram-abhazbooking-5252.jpg)."""
    channel = post_channel(post_id)
    if channel == CHANNEL:
        return f"telegram-bereg-{post_id}.jpg"
    return f"telegram-{channel}-{post_id}.jpg"


def upload_cover(post_id: int) -> bool:
    local_path = MEDIA_DIR / cover_name(post_id)
    if not local_path.is_file():
        print(f"ПЛОХО #{post_id}: нет файла {local_path.relative_to(ROOT)}", file=sys.stderr)
        return False
    storage_path = f"media/blog/{local_path.name}"
    url = upload_file(local_path, storage_path, "image/jpeg")
    print(f"OK   {url}")
    for width, blob in build_webp_variants_for_file(local_path):
        with tempfile.NamedTemporaryFile(suffix=".webp", delete=False) as tmp:
            tmp.write(blob)
            tmp_path = Path(tmp.name)
        try:
            variant_url = upload_file(tmp_path, variant_key(storage_path, width), "image/webp")
            print(f"OK   {variant_url}")
        finally:
            tmp_path.unlink(missing_ok=True)
    return True


def main() -> int:
    raw_ids = os.getenv("TARGET_BLOG_POST_IDS", "").strip()
    if not raw_ids:
        print("Задайте TARGET_BLOG_POST_IDS, например 2460,2461", file=sys.stderr)
        return 2
    failures = 0
    for part in raw_ids.split(","):
        if not part.strip():
            continue
        # Допускаем формат "abhazbooking:5252" — канал берётся из POST_META.
        if not upload_cover(int(part.strip().rpartition(":")[2])):
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
