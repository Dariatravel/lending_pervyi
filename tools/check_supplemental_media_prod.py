#!/usr/bin/env python3
"""Проверка медиа из блоков «Дополнительные материалы» на живом сайте.

Эти фото и видео приезжают из комментариев к постам Telegram и заливаются
отдельно от основной галереи объекта, поэтому именно здесь чаще всего
попадается битая ссылка: блок на странице есть, а файла в бакете нет
(22.08.2026 так сломалось «Меню 2026 Гастробар 151» у пляжного комплекса).

Источник ссылок — data/supplemental-blocks.json, то есть ровно то, что
генератор вставляет в страницы. У каждого URL проверяются код ответа, тип
содержимого, размер и первые байты тела (сигнатура формата) — заголовок
может быть правильным при пустом или чужом файле. Ключ --slug сужает
проверку до одного объекта.

Запускать можно только оттуда, где открыт доступ к CDN (GitHub Actions).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
BLOCKS_PATH = ROOT / "data" / "supplemental-blocks.json"
MEDIA_URL_RE = re.compile(r'(?:src|href)="(https://[^"]+)"')
IMAGE_EXT = (".jpg", ".jpeg", ".png", ".webp")
VIDEO_EXT = (".mp4", ".webm", ".mov")


def network_url(url: str) -> str:
    """Кириллический домен → punycode: urlopen не умеет IDN сам."""
    parsed = urlsplit(url)
    host = parsed.hostname or ""
    try:
        host = host.encode("idna").decode("ascii")
    except UnicodeError:
        pass
    netloc = f"{host}:{parsed.port}" if parsed.port else host
    return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))


# Заголовок может прийти правильный, а тело — пустое или чужое, поэтому
# читаем начало файла и сверяем сигнатуру: так «фото не открывается»
# подтверждается или опровергается по-настоящему.
MAGIC = {
    "jpg": (b"\xff\xd8\xff",),
    "jpeg": (b"\xff\xd8\xff",),
    "png": (b"\x89PNG\r\n\x1a\n",),
    "webp": (b"RIFF",),
    "mp4": (b"ftyp",),
    "mov": (b"ftyp",),
    "webm": (b"\x1a\x45\xdf\xa3",),
}


def probe_bytes(url: str, timeout: int = 25) -> tuple[int, str, int, bytes]:
    """Загружает первые байты файла: код, тип, размер по заголовку, начало тела."""
    request = Request(
        network_url(url),
        headers={
            "User-Agent": "abhazbereg-supplemental-check/1.0",
            "Cache-Control": "no-cache",
            "Range": "bytes=0-1023",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            head_bytes = response.read(1024)
            length = response.headers.get("Content-Range", "").rsplit("/", 1)[-1]
            if not length.isdigit():
                length = response.headers.get("Content-Length", "0")
            return response.status, response.headers.get("Content-Type", ""), int(length) if length.isdigit() else 0, head_bytes
    except HTTPError as error:
        return error.code, "", 0, b""
    except (URLError, OSError, ValueError) as error:
        return 0, f"{type(error).__name__}: {error}", 0, b""


def collect_urls(slug_filter: str | None) -> list[tuple[str, str]]:
    try:
        blocks = json.loads(BLOCKS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"Не читается {BLOCKS_PATH.name}: {error}")
        return []

    pairs: list[tuple[str, str]] = []
    seen: set[str] = set()
    for slug, payload in blocks.items():
        if slug_filter and slug_filter not in slug:
            continue
        html = str((payload or {}).get("section_html") or "")
        for url in MEDIA_URL_RE.findall(html):
            lowered = url.lower().split("?", 1)[0]
            if not lowered.endswith(IMAGE_EXT + VIDEO_EXT):
                continue
            if url in seen:
                continue
            seen.add(url)
            pairs.append((slug, url))
    return pairs


def expected_kind(url: str) -> str:
    lowered = url.lower().split("?", 1)[0]
    return "video" if lowered.endswith(VIDEO_EXT) else "image"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slug", help="проверить только объекты, в слаге которых есть эта подстрока")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    pairs = collect_urls(args.slug)
    if not pairs:
        print("Нечего проверять: подходящих блоков не нашлось.")
        return 0

    print(f"Проверяю {len(pairs)} файлов из блоков «Дополнительные материалы»…\n")

    def probe(pair: tuple[str, str]) -> tuple[str, str, int, str, int, bytes]:
        slug, url = pair
        status, ctype, length, head_bytes = probe_bytes(url)
        return slug, url, status, ctype, length, head_bytes

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        results = list(pool.map(probe, pairs))

    failures: list[str] = []
    by_slug: dict[str, list[str]] = {}
    for slug, url, status, ctype, length, head_bytes in results:
        name = url.rsplit("/", 1)[-1]
        kind = expected_kind(url)
        ext = name.lower().rsplit(".", 1)[-1]
        reasons: list[str] = []
        # 206 — нормальный ответ на запрос куска файла, 200 — если сервер отдал целиком.
        if status not in (200, 206):
            reasons.append(f"код {status}")
        if not ctype.startswith(kind + "/"):
            reasons.append(f"тип {ctype or '—'}")
        if not length:
            reasons.append("пустой файл")
        signatures = MAGIC.get(ext, ())
        if head_bytes and signatures and not any(sig in head_bytes[:16] for sig in signatures):
            reasons.append("содержимое не похоже на " + ext)
        size = f"{length // 1024} КБ" if length else "0"
        mark = "ПРОВАЛ" if reasons else "OK"
        by_slug.setdefault(slug, []).append(f"  {mark:6} {name} ({size}, {ctype or '—'})")
        if reasons:
            failures.append(f"{slug}: {url} — " + ", ".join(reasons))

    for slug in sorted(by_slug):
        print(slug)
        for line in by_slug[slug]:
            print(line)
        print()

    print(f"Итог: файлов {len(results)}, провалов {len(failures)}")
    for line in failures:
        print(f"  ! {line}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
