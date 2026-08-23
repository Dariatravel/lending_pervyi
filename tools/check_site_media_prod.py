#!/usr/bin/env python3
"""Полная проверка фото и видео сайта на живом домене.

Смоук проверяет выборочные страницы, а блоки «Дополнительные материалы»
проверяет check_supplemental_media_prod. Здесь — сплошной обход: все ссылки
на медиа со всех собранных страниц (объекты, квартиры, подборки, экскурсии,
блог, главная), включая WebP-варианты из srcset.

У каждого файла проверяются код ответа, тип содержимого, ненулевой размер и
первые байты тела: 22.08.2026 нашёлся файл, который сервер отдавал как
картинку, а внутри лежал документ Word.

Запускать оттуда, где открыт доступ к CDN (GitHub Actions).
"""

from __future__ import annotations

import argparse
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from check_supplemental_media_prod import (  # noqa: E402
    IMAGE_EXT,
    VIDEO_EXT,
    content_problem,
    expected_kind,
    probe_bytes,
)

MEDIA_URL_RE = re.compile(
    r'https://(?:media\.xn--80aacbklan7f0b\.xn--p1ai|storage\.yandexcloud\.net)/[^"\'\s>)]+'
)
PAGE_GLOBS = (
    "index.html",
    "hotels/*/index.html",
    "kvartira/*/index.html",
    "podborki/*/index.html",
    "vezu/*/index.html",
    "blog/*/index.html",
    "blog/index.html",
    "karta/index.html",
)


def collect(limit: int | None) -> list[tuple[str, str]]:
    """Пары «страница → ссылка на медиа». Каждый файл проверяем один раз."""
    pairs: list[tuple[str, str]] = []
    seen: set[str] = set()
    for pattern in PAGE_GLOBS:
        for page in sorted(ROOT.glob(pattern)):
            try:
                html = page.read_text(encoding="utf-8")
            except OSError:
                continue
            # Страницы-переезды медиа не содержат, но и проверять там нечего.
            if 'http-equiv="refresh"' in html:
                continue
            where = page.parent.relative_to(ROOT).as_posix() or "/"
            for url in MEDIA_URL_RE.findall(html):
                url = url.rstrip(".,;")
                if not url.lower().split("?", 1)[0].endswith(IMAGE_EXT + VIDEO_EXT):
                    continue
                if url in seen:
                    continue
                seen.add(url)
                pairs.append((where, url))
                if limit and len(pairs) >= limit:
                    return pairs
    return pairs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=24)
    parser.add_argument("--limit", type=int, default=0, help="проверить только первые N файлов")
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="печатать только провалы (иначе выводятся все проверенные файлы)",
    )
    args = parser.parse_args()

    pairs = collect(args.limit or None)
    if not pairs:
        print("Медиа на страницах не найдено — проверять нечего.")
        return 0

    print(f"Проверяю {len(pairs)} файлов на живом домене…\n", flush=True)

    def probe(pair: tuple[str, str]):
        where, url = pair
        return (where, url, *probe_bytes(url))

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        results = list(pool.map(probe, pairs))

    failures: list[str] = []
    notes: list[str] = []
    checked_ok = 0
    for where, url, status, ctype, length, head_bytes in results:
        name = url.rsplit("/", 1)[-1]
        kind = expected_kind(url)
        ext = name.lower().rsplit(".", 1)[-1]
        reasons: list[str] = []
        if status not in (200, 206):
            reasons.append(f"код {status}")
        if not ctype.startswith(kind + "/"):
            reasons.append(f"тип {ctype or '—'}")
        if not length:
            reasons.append("пустой файл")
        warnings: list[str] = []
        mismatch = content_problem(kind, ext, head_bytes)
        if mismatch:
            (reasons if mismatch[1] else warnings).append(mismatch[0])
        if reasons:
            failures.append(f"{where}: {url}\n      " + ", ".join(reasons))
            continue
        checked_ok += 1
        if warnings:
            notes.append(f"{where}: {url}\n      " + ", ".join(warnings))
        elif not args.quiet:
            print(f"  OK  {where}/{name} ({length // 1024} КБ)")

    print(
        f"\nИтог: файлов {len(results)}, целых {checked_ok}, "
        f"провалов {len(failures)}, замечаний {len(notes)}"
    )
    for line in failures:
        print(f"  ! {line}")
    for line in notes:
        print(f"  ~ {line}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
