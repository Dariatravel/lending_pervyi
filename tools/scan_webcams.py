#!/usr/bin/env python3
"""Разведчик веб-камер Абхазии: APSNY.CAMERA и A-MOBILE.CAMERA.

Обходит страницы обоих источников, собирает камеры (название страницы,
адрес, ссылка на видеопоток) и проверяет каждый поток — отвечает ли и
похож ли ответ на HLS-плейлист. Результат — JSON-список кандидатов, из
которого вручную отбираются камеры для data/webcams.json.

Запускать из GitHub Actions (workflow webcams-scan.yml): из песочниц
агента внешние сайты закрыты, с раннеров — открыты.

    python3 tools/scan_webcams.py                  # обход и проверка
    python3 tools/scan_webcams.py --dump-html      # + куски HTML для отладки
"""

from __future__ import annotations

import argparse
import html as html_mod
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "webcams-scan.json"

SOURCES = {
    "apsny.camera": "https://apsny.camera/",
    "a-mobile.camera": "https://a-mobile.camera/",
}
# Сколько внутренних страниц обходить на источник — каталоги камер небольшие,
# запас на пагинацию и разделы городов.
MAX_PAGES_PER_SOURCE = 120
TIMEOUT = 25
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36 abhazbereg-webcam-scan"

STREAM_RE = re.compile(r'["\'(]([^"\'()\s]+\.(?:m3u8|mpd)[^"\'()\s]*)["\')]', re.I)
IFRAME_RE = re.compile(r'<iframe[^>]+src=["\']([^"\']+)["\']', re.I)
VIDEO_SRC_RE = re.compile(r'<(?:video|source)[^>]+src=["\']([^"\']+)["\']', re.I)
LINK_RE = re.compile(r'<a[^>]+href=["\']([^"\'#]+)["\']', re.I)
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.I | re.S)


def fetch(url: str) -> tuple[int, str]:
    request = Request(url, headers={"User-Agent": UA, "Accept-Language": "ru"})
    try:
        with urlopen(request, timeout=TIMEOUT) as response:
            body = response.read(2_000_000)
            return response.status, body.decode("utf-8", errors="replace")
    except HTTPError as error:
        return error.code, ""
    except (URLError, OSError, ValueError) as error:
        return 0, f"__error__ {type(error).__name__}: {error}"


def clean_text(value: str) -> str:
    return " ".join(html_mod.unescape(re.sub("<[^>]+>", " ", value)).split())


def same_host(url: str, base: str) -> bool:
    try:
        return urlsplit(url).netloc in ("", urlsplit(base).netloc)
    except ValueError:
        return False


def probe_stream(url: str) -> str:
    """ok / пусто / код ошибки — жив ли поток."""
    request = Request(url, headers={"User-Agent": UA})
    try:
        with urlopen(request, timeout=TIMEOUT) as response:
            head = response.read(4096).decode("utf-8", errors="replace")
    except HTTPError as error:
        return f"http {error.code}"
    except (URLError, OSError, ValueError) as error:
        return f"{type(error).__name__}"
    if "#EXTM3U" in head:
        return "ok"
    if head.strip():
        return "отвечает, но не HLS"
    return "пустой ответ"


def crawl_source(name: str, base: str, dump_html: bool) -> list[dict]:
    status, home = fetch(base)
    print(f"\n=== {name}: главная — код {status}, {len(home)} байт", flush=True)
    if dump_html and home:
        print(home[:2500])
    if not home or home.startswith("__error__"):
        print(f"    не открылась: {home[:200]}")
        return []

    queue: list[str] = [base]
    seen: set[str] = set()
    cameras: list[dict] = []
    while queue and len(seen) < MAX_PAGES_PER_SOURCE:
        url = queue.pop(0)
        norm = url.rstrip("/")
        if norm in seen:
            continue
        seen.add(norm)
        status, page = fetch(url)
        if not page or page.startswith("__error__"):
            continue

        title_m = H1_RE.search(page) or TITLE_RE.search(page)
        title = clean_text(title_m.group(1)) if title_m else ""

        streams = set(STREAM_RE.findall(page))
        embeds = set(IFRAME_RE.findall(page)) | set(VIDEO_SRC_RE.findall(page))
        if streams or embeds:
            cameras.append(
                {
                    "source": name,
                    "page_url": url,
                    "title": title,
                    "streams": sorted(urljoin(url, s) for s in streams),
                    "embeds": sorted(urljoin(url, e) for e in embeds),
                }
            )

        for link in LINK_RE.findall(page):
            link = urljoin(url, link.strip())
            if not link.startswith("http"):
                continue
            if not same_host(link, base):
                continue
            if re.search(r"\.(?:css|js|png|jpe?g|webp|svg|ico|pdf|zip|xml)(?:\?|$)", link, re.I):
                continue
            if link.rstrip("/") not in seen:
                queue.append(link)

    print(f"    обойдено страниц: {len(seen)}, страниц с видео: {len(cameras)}")
    return cameras


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dump-html", action="store_true")
    args = parser.parse_args()

    all_cameras: list[dict] = []
    for name, base in SOURCES.items():
        all_cameras.extend(crawl_source(name, base, args.dump_html))

    stream_urls = sorted({s for cam in all_cameras for s in cam["streams"]})
    print(f"\nПроверяю {len(stream_urls)} потоков…")
    with ThreadPoolExecutor(max_workers=8) as pool:
        stream_status = dict(zip(stream_urls, pool.map(probe_stream, stream_urls)))

    for cam in all_cameras:
        cam["stream_status"] = {s: stream_status.get(s, "?") for s in cam["streams"]}

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(all_cameras, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\n===== СВОДКА ({len(all_cameras)} страниц с видео) =====")
    for cam in all_cameras:
        marks = ", ".join(f"{s} [{cam['stream_status'][s]}]" for s in cam["streams"]) or "потоков нет"
        print(f"[{cam['source']}] {cam['title'][:70]}\n    {cam['page_url']}\n    {marks}")
        for embed in cam["embeds"][:3]:
            print(f"    embed: {embed}")
    live = sum(1 for cam in all_cameras if any(v == "ok" for v in cam["stream_status"].values()))
    print(f"\nИтог: страниц с видео {len(all_cameras)}, из них с живым HLS-потоком {live}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
