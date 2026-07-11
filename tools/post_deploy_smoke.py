#!/usr/bin/env python3
"""Smoke-check production pages and critical CDN files after deploy."""

from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "output"
DEFAULT_BASE = "https://абхазберег.рф"
FORBIDDEN_HTML = ("image-lite", "catalog-snapshot.json", "review_text_bank", "supabase")
YANDEX_MEDIA = "https://storage.yandexcloud.net/abhazbereg-media/media/"
SIZE_BUDGETS = {
    "index_html_gzip": 45 * 1024,
    "styles_min_css": 150 * 1024,
    "scripts_min_js": 110 * 1024,
}


def first_object_path(root: str) -> str:
    base = ROOT / root
    pages = sorted(base.glob("*/index.html"))
    if not pages:
        return "/"
    return "/" + pages[0].parent.relative_to(ROOT).as_posix() + "/"


def network_url(url: str) -> str:
    parsed = urlsplit(url)
    host = parsed.hostname or ""
    try:
        host = host.encode("idna").decode("ascii")
    except UnicodeError:
        pass
    netloc = host
    if parsed.port:
        netloc = f"{netloc}:{parsed.port}"
    if parsed.username:
        auth = parsed.username
        if parsed.password:
            auth = f"{auth}:{parsed.password}"
        netloc = f"{auth}@{netloc}"
    return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))


def fetch(url: str, timeout: int) -> tuple[int, str]:
    request = Request(network_url(url), headers={"User-Agent": "abhazbereg-smoke/1.0", "Cache-Control": "no-cache"})
    with urlopen(request, timeout=timeout) as response:
        body = response.read(1_500_000).decode("utf-8", errors="replace")
        return int(response.status), body


def fetch_bytes(url: str, timeout: int, *, accept_gzip: bool = False) -> tuple[int, bytes]:
    headers = {"User-Agent": "abhazbereg-smoke/1.0", "Cache-Control": "no-cache"}
    if accept_gzip:
        headers["Accept-Encoding"] = "gzip"
    request = Request(network_url(url), headers=headers)
    with urlopen(request, timeout=timeout) as response:
        return int(response.status), response.read()


def head_ok(url: str, timeout: int) -> tuple[bool, int | None, int | None]:
    request = Request(network_url(url), method="GET", headers={"User-Agent": "abhazbereg-smoke/1.0"})
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read(1)
            size = int(response.headers.get("Content-Length") or len(body) or 0)
            return 200 <= int(response.status) < 300, int(response.status), size
    except Exception:
        return False, None, None


def extract_asset_urls(base_url: str, html: str) -> list[str]:
    urls: list[str] = []
    for value in re.findall(r'''(?:href|src)=["']([^"']+\.(?:css|js)(?:\?v=\d+)?)["']''', html, flags=re.I):
        urls.append(urljoin(base_url, value))
    urls.extend(re.findall(r'''https://storage\.yandexcloud\.net/abhazbereg-media/media/reviews/[^"']+\.json(?:\?v=\d+)?''', html))
    return sorted(set(urls))


def slug_sort_key(slug: str) -> int:
    match = re.search(r"-(\d+)$", slug)
    return int(match.group(1)) if match else -1


def recent_catalog_items(limit: int) -> list[dict[str, object]]:
    catalog_path = ROOT / "data" / "catalog-index.json"
    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    items = sorted(payload.get("listings") or [], key=lambda item: slug_sort_key(str(item.get("slug") or "")), reverse=True)
    selected = items[:limit]
    regina = next((item for item in items if str(item.get("slug")) == "regina-pervyy-korpus-otel-s-zavtrakami-4957"), None)
    if regina and all(item.get("slug") != regina.get("slug") for item in selected):
        selected = [regina, *selected[: max(0, limit - 1)]]
    return selected


def webp_variants(url: str) -> list[str]:
    clean = url.split("?", 1)[0]
    if clean.endswith("-cover.jpg"):
        stem = clean[:-4]
    elif clean.lower().endswith((".jpg", ".jpeg", ".png")):
        stem = re.sub(r"\.(?:jpe?g|png)$", "", clean, flags=re.I)
    else:
        return []
    return [f"{stem}-480.webp", f"{stem}-960.webp"]


def extract_media_checks(html: str, item: dict[str, object]) -> list[str]:
    urls: list[str] = []
    cover = str(item.get("cover_url") or "")
    urls.extend(webp_variants(cover))
    for srcset in re.findall(r'\bsrcset=["\']([^"\']+)["\']', html):
        for value in re.findall(r"(https://storage\.yandexcloud\.net/abhazbereg-media/media/[^,\s]+-(?:480|960)\.webp)", srcset):
            urls.append(value)
    urls.extend(re.findall(r"https://storage\.yandexcloud\.net/abhazbereg-media/media/videos/[^\"'\s]+\.mp4", html))
    if item.get("has_video") and not any(".mp4" in url for url in urls):
        slug = item.get("slug")
        urls.append(f"MISSING_VIDEO:{slug}")
    return sorted(set(urls))


def check_size_budgets(base_url: str, timeout: int) -> tuple[list[dict[str, object]], list[str]]:
    errors: list[str] = []
    results: list[dict[str, object]] = []
    index_url = urljoin(base_url.rstrip("/") + "/", "/")
    status, body = fetch_bytes(index_url, timeout, accept_gzip=True)
    size = len(body) if status == 200 else 0
    if status == 200 and not body.startswith(b"\x1f\x8b"):
        size = len(gzip.compress(body, compresslevel=9))
    results.append({"name": "index_html_gzip", "url": index_url, "bytes": size, "budget": SIZE_BUDGETS["index_html_gzip"]})
    if status != 200 or size > SIZE_BUDGETS["index_html_gzip"]:
        errors.append(f"index.html gzip {size} байт, лимит {SIZE_BUDGETS['index_html_gzip']}")
    for name, path in (("styles_min_css", "/styles.min.css"), ("scripts_min_js", "/scripts.min.js")):
        url = urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
        asset_status, asset_body = fetch_bytes(url, timeout)
        asset_size = len(asset_body)
        results.append({"name": name, "url": url, "bytes": asset_size, "budget": SIZE_BUDGETS[name]})
        if asset_status != 200 or asset_size > SIZE_BUDGETS[name]:
            errors.append(f"{path} {asset_size} байт, лимит {SIZE_BUDGETS[name]}")
    return results, errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE)
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--hotel-path", default="/hotels/parus-vidovoy-otel-s-basseynom-i-stolovoy-2602/")
    parser.add_argument("--kvartira-path", default="/kvartira/amor-apartamenty-studiya-gagra-1322/")
    parser.add_argument("--recent-count", type=int, default=3)
    args = parser.parse_args()

    checks: list[dict[str, object]] = []
    errors: list[str] = []
    paths = ["/", args.hotel_path, args.kvartira_path]

    for path in paths:
        url = urljoin(args.base_url.rstrip("/") + "/", path.lstrip("/"))
        try:
            status, html = fetch(url, args.timeout)
        except Exception as exc:
            errors.append(f"{url}: не загрузилась HTML-страница: {exc}")
            checks.append({"url": url, "status": "error", "error": str(exc)})
            continue
        page_errors = []
        if status != 200:
            page_errors.append(f"HTML status={status}")
        if "favicon-48.png" not in html:
            page_errors.append("нет favicon-48.png")
        for forbidden in FORBIDDEN_HTML:
            if forbidden in html:
                page_errors.append(f"запрещённая строка: {forbidden}")
        asset_urls = extract_asset_urls(url, html)
        if path == "/":
            asset_urls.append("https://storage.yandexcloud.net/abhazbereg-media/media/reviews/global.json")
        else:
            slug = path.strip("/").split("/")[-1]
            asset_urls.append(f"https://storage.yandexcloud.net/abhazbereg-media/media/reviews/{slug}/bank.json")
        asset_results = []
        for asset_url in sorted(set(asset_urls)):
            ok, asset_status, asset_size = head_ok(asset_url, args.timeout)
            asset_results.append({"url": asset_url, "status": asset_status, "size": asset_size, "ok": ok})
            if not ok:
                page_errors.append(f"asset недоступен: {asset_url} status={asset_status}")
        checks.append({"url": url, "status": status, "errors": page_errors, "assets": asset_results})
        errors.extend(f"{url}: {error}" for error in page_errors)

    budget_results, budget_errors = check_size_budgets(args.base_url, args.timeout)
    checks.append({"kind": "size_budgets", "results": budget_results, "errors": budget_errors})
    errors.extend(budget_errors)

    recent_results = []
    for item in recent_catalog_items(args.recent_count):
        page_url = str(item.get("page_url") or "")
        if not page_url:
            continue
        try:
            status, html = fetch(page_url, args.timeout)
        except Exception as exc:
            errors.append(f"{page_url}: не загрузилась HTML-страница свежего объекта: {exc}")
            recent_results.append({"url": page_url, "status": "error", "error": str(exc)})
            continue
        media_errors: list[str] = []
        media_results = []
        for media_url in extract_media_checks(html, item):
            if media_url.startswith("MISSING_VIDEO:"):
                media_errors.append(f"{page_url}: не найдено видео для объекта с has_video")
                continue
            ok, media_status, media_size = head_ok(media_url, args.timeout)
            media_results.append({"url": media_url, "status": media_status, "size": media_size, "ok": ok})
            if not ok:
                media_errors.append(f"{page_url}: media недоступно: {media_url} status={media_status}")
        if status != 200:
            media_errors.append(f"{page_url}: HTML status={status}")
        recent_results.append(
            {
                "title": item.get("title"),
                "slug": item.get("slug"),
                "url": page_url,
                "status": status,
                "errors": media_errors,
                "media": media_results,
            }
        )
        errors.extend(media_errors)
    checks.append({"kind": "recent_media", "results": recent_results})

    OUTPUT_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    report_path = OUTPUT_DIR / f"post-deploy-smoke-{stamp}.json"
    report_path.write_text(
        json.dumps({"status": "ok" if not errors else "failed", "checks": checks, "errors": errors}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Отчёт: {report_path}")
    if errors:
        print("Smoke-check не прошёл:")
        for error in errors:
            print(f"- {error}")
    else:
        print("Smoke-check прошёл.")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
