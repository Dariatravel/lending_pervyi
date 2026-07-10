#!/usr/bin/env python3
"""Smoke-check production pages and critical CDN files after deploy."""

from __future__ import annotations

import argparse
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


def head_ok(url: str, timeout: int) -> tuple[bool, int | None]:
    request = Request(network_url(url), method="GET", headers={"User-Agent": "abhazbereg-smoke/1.0"})
    try:
        with urlopen(request, timeout=timeout) as response:
            response.read(1)
            return 200 <= int(response.status) < 300, int(response.status)
    except Exception:
        return False, None


def extract_asset_urls(base_url: str, html: str) -> list[str]:
    urls: list[str] = []
    for value in re.findall(r'''(?:href|src)=["']([^"']+\.(?:css|js)(?:\?v=\d+)?)["']''', html, flags=re.I):
        urls.append(urljoin(base_url, value))
    urls.extend(re.findall(r'''https://storage\.yandexcloud\.net/abhazbereg-media/media/reviews/[^"']+\.json(?:\?v=\d+)?''', html))
    return sorted(set(urls))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE)
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--hotel-path", default="/hotels/parus-vidovoy-otel-s-basseynom-i-stolovoy-2602/")
    parser.add_argument("--kvartira-path", default="/kvartira/amor-apartamenty-studiya-gagra-1322/")
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
            ok, asset_status = head_ok(asset_url, args.timeout)
            asset_results.append({"url": asset_url, "status": asset_status, "ok": ok})
            if not ok:
                page_errors.append(f"asset недоступен: {asset_url} status={asset_status}")
        checks.append({"url": url, "status": status, "errors": page_errors, "assets": asset_results})
        errors.extend(f"{url}: {error}" for error in page_errors)

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
