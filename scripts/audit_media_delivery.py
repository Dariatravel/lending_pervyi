#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Iterable
from urllib.parse import unquote, urljoin, urlparse

import requests

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SITE = "https://xn--80aacbklan7f0b.xn--p1ai/"
VIDEO_LIMIT_MB = 20
IMAGE_LIMIT_KB = 700
NETWORK_VIDEO_LIMIT_MB = 20
NETWORK_IMAGE_LIMIT_KB = 700

SRC_RE = re.compile(r"""(?:src|href)=["']([^"']+)["']""", re.I)
SUPABASE_RE = re.compile(r"https://[^\"'\\s]+supabase\\.co/storage/v1/object/public/[^\"'\\s]+", re.I)
MEDIA_RE = re.compile(r"/media/[^\"'\\s<>)]+", re.I)
TELEGRAM_WIDGET_RE = re.compile(r"telegram-widget\\.js|data-telegram-post=", re.I)


def iter_pages() -> Iterable[Path]:
    yield ROOT / "index.html"
    for base in ("hotels", "kvartira"):
        for page in sorted((ROOT / base).glob("*/index.html")):
            yield page


def collect_urls(site_base: str) -> tuple[dict[str, set[str]], list[str]]:
    urls_by_page: dict[str, set[str]] = {}
    telegram_pages: list[str] = []
    for page in iter_pages():
        if not page.exists():
            continue
        text = page.read_text(encoding="utf-8", errors="ignore")
        urls: set[str] = set()
        for match in SRC_RE.finditer(text):
            value = match.group(1).strip()
            if value.startswith(("data:", "mailto:", "tel:", "#")):
                continue
            if value.startswith("/media/"):
                urls.add(urljoin(site_base, value))
            elif value.startswith("media/"):
                urls.add(urljoin(site_base, value))
            elif value.startswith("https://") and ("supabase.co/storage" in value or "/media/" in value):
                urls.add(value)
        for match in SUPABASE_RE.finditer(text):
            urls.add(match.group(0))
        for match in MEDIA_RE.finditer(text):
            urls.add(urljoin(site_base, match.group(0)))
        if TELEGRAM_WIDGET_RE.search(text):
            telegram_pages.append(str(page.relative_to(ROOT)))
        if urls:
            urls_by_page[str(page.relative_to(ROOT))] = urls
    return urls_by_page, telegram_pages


def media_url_to_local_path(url: str, site_base: str) -> str | None:
    parsed = urlparse(urljoin(site_base, url))
    path = unquote(parsed.path.lstrip("/"))
    if path.startswith("media/"):
        return path
    return None


def build_local_usage(urls_by_page: dict[str, set[str]], site_base: str) -> dict[str, list[str]]:
    usage: dict[str, set[str]] = {}
    for page, urls in urls_by_page.items():
        for url in urls:
            local_path = media_url_to_local_path(url, site_base)
            if not local_path:
                continue
            usage.setdefault(local_path, set()).add(page)
    return {path: sorted(pages) for path, pages in usage.items()}


def build_url_usage(urls_by_page: dict[str, set[str]]) -> dict[str, list[str]]:
    usage: dict[str, set[str]] = {}
    for page, urls in urls_by_page.items():
        for url in urls:
            usage.setdefault(url, set()).add(page)
    return {url: sorted(pages) for url, pages in usage.items()}


def local_media_size_issues(local_usage: dict[str, list[str]]) -> list[dict[str, object]]:
    issues: list[dict[str, object]] = []
    for path in (ROOT / "media").rglob("*"):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        size = path.stat().st_size
        relative_path = str(path.relative_to(ROOT))
        pages = local_usage.get(relative_path, [])
        usage_fields = {
            "page_count": len(pages),
            "pages": pages[:10],
        }
        if suffix in {".mp4", ".mov"} and size > VIDEO_LIMIT_MB * 1024 * 1024:
            issues.append({
                "kind": "large_video",
                "path": relative_path,
                "size_mb": round(size / 1024 / 1024, 1),
                **usage_fields,
            })
        elif suffix in {".jpg", ".jpeg", ".png"} and size > IMAGE_LIMIT_KB * 1024:
            issues.append({
                "kind": "large_image",
                "path": relative_path,
                "size_kb": round(size / 1024),
                **usage_fields,
            })
    return issues


def check_url(url: str, timeout: int) -> dict[str, object]:
    result: dict[str, object] = {"url": url, "ok": False}
    try:
        response = requests.head(url, allow_redirects=True, timeout=timeout)
        if response.status_code in {403, 405}:
            response = requests.get(url, stream=True, allow_redirects=True, timeout=timeout)
        result.update({
            "status": response.status_code,
            "content_type": response.headers.get("content-type", ""),
            "content_length": int(response.headers.get("content-length") or 0),
            "cache_control": response.headers.get("cache-control", ""),
            "accept_ranges": response.headers.get("accept-ranges", ""),
            "ok": 200 <= response.status_code < 400,
        })
        response.close()

        content_type = str(result["content_type"]).lower()
        if content_type.startswith("video/"):
            range_response = requests.head(
                url,
                headers={"Range": "bytes=0-1023"},
                allow_redirects=True,
                timeout=timeout,
            )
            result["range_status"] = range_response.status_code
            result["range_ok"] = range_response.status_code == 206
            range_response.close()
    except Exception as error:  # noqa: BLE001
        result["error"] = str(error)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit website media delivery.")
    parser.add_argument("--site", default=DEFAULT_SITE, help="Public site base URL.")
    parser.add_argument("--network", action="store_true", help="Also check HTTP headers for public URLs.")
    parser.add_argument("--timeout", type=int, default=15)
    parser.add_argument("--limit", type=int, default=0, help="Limit network checks.")
    parser.add_argument("--json", dest="json_output", action="store_true")
    args = parser.parse_args()

    site_base = args.site.rstrip("/") + "/"
    urls_by_page, telegram_pages = collect_urls(site_base)
    local_usage = build_local_usage(urls_by_page, site_base)
    url_usage = build_url_usage(urls_by_page)
    all_urls = sorted({url for urls in urls_by_page.values() for url in urls})
    if args.limit:
        all_urls = all_urls[: args.limit]

    report: dict[str, object] = {
        "pages_with_media": len(urls_by_page),
        "media_urls": len(all_urls),
        "telegram_embed_pages": telegram_pages,
        "local_size_issues": local_media_size_issues(local_usage),
        "network": [],
    }

    if args.network and all_urls:
        rows: list[dict[str, object]] = []
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = {pool.submit(check_url, url, args.timeout): url for url in all_urls}
            for future in as_completed(futures):
                row = future.result()
                url = str(row.get("url", ""))
                pages = url_usage.get(url, [])
                row["page_count"] = len(pages)
                row["pages"] = pages[:10]
                rows.append(row)
        report["network"] = sorted(rows, key=lambda row: str(row.get("url")))

    if args.json_output:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    print(f"Pages with media: {report['pages_with_media']}")
    print(f"Media URLs: {report['media_urls']}")
    print(f"Telegram embed pages: {len(telegram_pages)}")
    for page in telegram_pages[:20]:
        print(f"  telegram embed: {page}")

    size_issues = report["local_size_issues"]
    assert isinstance(size_issues, list)
    print(f"Large local media: {len(size_issues)}")
    for issue in size_issues[:40]:
        print(f"  {issue}")

    network_rows = report["network"]
    assert isinstance(network_rows, list)
    if network_rows:
        bad = [row for row in network_rows if not row.get("ok") or row.get("range_ok") is False]
        no_cache = [row for row in network_rows if "no-cache" in str(row.get("cache_control", "")).lower()]
        large_network_media = []
        for row in network_rows:
            content_type = str(row.get("content_type", "")).lower()
            content_length = int(row.get("content_length") or 0)
            if content_type.startswith("video/") and content_length > NETWORK_VIDEO_LIMIT_MB * 1024 * 1024:
                large_network_media.append(row)
            elif content_type.startswith("image/") and content_length > NETWORK_IMAGE_LIMIT_KB * 1024:
                large_network_media.append(row)
        print(f"Network checked: {len(network_rows)}")
        print(f"Network issues: {len(bad)}")
        for row in bad[:40]:
            print(f"  bad: {row}")
        print(f"no-cache media: {len(no_cache)}")
        print(f"large network media: {len(large_network_media)}")
        for row in large_network_media[:40]:
            print(f"  large: {row}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
