#!/usr/bin/env python3
"""Мини-проверка парсинга обложки статьи блога."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_blog_posts_manifest import extract_cover_image


def main() -> int:
    valid = '<img class="blog-article__cover-inline" loading="eager" src="https://storage.yandexcloud.net/abhazbereg-media/media/blog/telegram-bereg-2411.jpg"/>'
    image = extract_cover_image(valid)
    if image != "telegram-bereg-2411.jpg":
        print(f"Ожидалась telegram-bereg-2411.jpg, получено: {image!r}")
        return 1

    empty = '<img class="blog-article__cover-inline" loading="eager" src="https://storage.yandexcloud.net/abhazbereg-media/media/blog/"/>'
    try:
        extract_cover_image(empty)
    except ValueError:
        pass
    else:
        print("Пустая обложка media/blog/ не была отклонена")
        return 1

    print("Парсер обложек блога прошёл проверку")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
