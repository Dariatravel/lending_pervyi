#!/usr/bin/env python3
"""Проверка статей блога на живом домене глазами телефона.

Открывает страницы с мобильным User-Agent, убеждается, что страница отдаётся,
есть <meta viewport> (без него телефон показывает «десктоп в миниатюре»),
и что каждая картинка статьи — и оригинал, и WebP-копии из srcset —
существует в хранилище (иначе на телефоне вместо фото пустая рамка).

    TARGET_BLOG_POST_IDS=2460,2461 python3 tools/check_blog_pages_prod.py
"""
from __future__ import annotations

import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

ORIGIN = "https://xn--80aacbklan7f0b.xn--p1ai"  # абхазберег.рф
MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1"
)
TIMEOUT = 30


def fetch(url: str, *, head: bool = False) -> tuple[int, bytes, str]:
    request = urllib.request.Request(
        url, headers={"User-Agent": MOBILE_UA}, method="HEAD" if head else "GET"
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            body = b"" if head else response.read()
            return response.status, body, response.headers.get("Content-Type", "")
    except urllib.error.HTTPError as error:
        return error.code, b"", ""
    except Exception as error:  # noqa: BLE001
        print(f"    ошибка сети: {error}", file=sys.stderr)
        return 0, b"", ""


def page_image_urls(html_text: str) -> set[str]:
    urls: set[str] = set()
    for match in re.finditer(r'(?:src|href)="(https://(?:storage\.yandexcloud\.net|media\.xn--80aacbklan7f0b\.xn--p1ai)/[^"]+\.(?:jpg|jpeg|png|webp))"', html_text):
        urls.add(match.group(1))
    for match in re.finditer(r'srcset="([^"]+)"', html_text):
        for part in match.group(1).split(","):
            candidate = part.strip().split(" ")[0]
            if candidate.startswith(("https://storage.yandexcloud.net/", "https://media.xn--80aacbklan7f0b.xn--p1ai/")):
                urls.add(candidate)
    return urls


def check_article(slug: str) -> int:
    url = f"{ORIGIN}/blog/{slug}/"
    status, body, _ = fetch(url)
    text = body.decode("utf-8", errors="ignore")
    failures = 0

    page_ok = status == 200 and "</html>" in text
    print(f"{'OK  ' if page_ok else 'ПЛОХО'} {url} (код {status}, {len(body)} байт)")
    if not page_ok:
        return 1

    if re.search(r'<meta[^>]+name="viewport"', text, re.I):
        print("  OK   viewport для телефона на месте")
    else:
        print("  ПЛОХО нет <meta viewport> — телефон покажет десктоп в миниатюре")
        failures += 1

    images = sorted(page_image_urls(text))
    if not images:
        print("  ПЛОХО в статье не нашлось ни одной картинки из хранилища")
        return failures + 1
    for image_url in images:
        img_status, _, img_type = fetch(image_url, head=True)
        ok = img_status == 200 and img_type.startswith("image/")
        short = image_url.rsplit("/", 1)[-1]
        print(f"  {'OK  ' if ok else 'ПЛОХО'} фото {short} (код {img_status}, тип {img_type or '—'})")
        if not ok:
            failures += 1
    return failures


def main() -> int:
    raw_ids = os.getenv("TARGET_BLOG_POST_IDS", "").strip()
    if not raw_ids:
        print("Задайте TARGET_BLOG_POST_IDS, например 2460,2461", file=sys.stderr)
        return 2
    from sync_blog_from_abhazbereg import POST_META

    failures = 0
    checked = 0
    for part in raw_ids.split(","):
        if not part.strip():
            continue
        # Допускаем формат "abhazbooking:5252" — канал здесь не важен.
        post_id = int(part.strip().rpartition(":")[2])
        meta = POST_META.get(post_id)
        if not meta:
            print(f"#{post_id}: метаданных ещё нет — статья не опубликована, пропускаю.")
            continue
        checked += 1
        failures += check_article(str(meta["slug"]))

    if checked:
        print(f"\nИтог: статей проверено {checked}, провалов {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
