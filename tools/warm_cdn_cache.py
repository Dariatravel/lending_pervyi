#!/usr/bin/env python3
"""Прогрев CDN-кэша после заливки: обойти все страницы из sitemap.

Первый запрос к редкой странице через холодный узел CDN отвечает 4–9 секунд —
гость решает, что сайт завис. Этот скрипт после каждой заливки сам открывает
каждую страницу sitemap (плюс ключевые данные для карты и каталога), чтобы
холодные секунды доставались роботу, а не гостю.

    python3 tools/warm_cdn_cache.py
"""
from __future__ import annotations

import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIVE_HOST = "https://xn--80aacbklan7f0b.xn--p1ai"  # абхазберег.рф
UNICODE_HOST = "https://абхазберег.рф"
EXTRA_PATHS = [
    "/data/catalog-index.json",
    "/data/objects-map-points.json",
    "/data/blog-posts.json",
    "/data/min-prices-today.json",
    "/offline.html",
    "/404.html",
]
TIMEOUT = 30
SLOW_MS = 2000
THREADS = 8


def warm(url: str) -> tuple[str, int, int]:
    request = urllib.request.Request(url, headers={"User-Agent": "abhazbereg-cdn-warmup"})
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            response.read()
            status = response.status
    except urllib.error.HTTPError as error:
        status = error.code
    except Exception:  # noqa: BLE001 — сеть/таймаут
        status = 0
    return url, status, int((time.monotonic() - started) * 1000)


def main() -> int:
    sitemap = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
    urls = []
    for loc in re.findall(r"<loc>(.*?)</loc>", sitemap):
        urls.append(loc.replace(UNICODE_HOST, LIVE_HOST))
    urls.extend(LIVE_HOST + path for path in EXTRA_PATHS)
    urls = list(dict.fromkeys(urls))

    print(f"Прогреваю {len(urls)} адресов через {LIVE_HOST}", flush=True)
    slow, failed = [], []
    with ThreadPoolExecutor(max_workers=THREADS) as pool:
        for future in as_completed(pool.submit(warm, url) for url in urls):
            url, status, ms = future.result()
            if status != 200:
                failed.append((url, status))
            elif ms > SLOW_MS:
                slow.append((url, ms))

    print(f"Готово. Были холодными (>{SLOW_MS} мс): {len(slow)}")
    for url, ms in sorted(slow, key=lambda x: -x[1])[:15]:
        print(f"  {ms:>6} мс  {url.replace(LIVE_HOST, '')}")
    if failed:
        print(f"Не ответили 200: {len(failed)}")
        for url, status in failed[:15]:
            print(f"  код {status}  {url.replace(LIVE_HOST, '')}")
    # Прогрев — сервисная процедура: сбой сети здесь не должен красить деплой,
    # поэтому неответившие страницы только показываем, выход всегда 0.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
