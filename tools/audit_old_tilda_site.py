#!/usr/bin/env python3
"""Разведка старого сайта на Тильде (abhazbereg.ru) перед переездом домена.

Собирает: robots.txt, sitemap.xml (включая вложенные), по каждой странице —
код ответа, <title> и description. Результат — таблица для составления
карты редиректов «старая ссылка → страница абхазберег.рф».

    OLD_SITE=https://abhazbereg.ru python3 tools/audit_old_tilda_site.py
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_JSON = ROOT / "output" / "old-site-audit.json"
ORIGIN = os.getenv("OLD_SITE", "https://abhazbereg.ru").rstrip("/")
TIMEOUT = 30
UA = "Mozilla/5.0 (compatible; abhazbereg-migration-audit/1.0)"


def fetch(url: str) -> tuple[int, str]:
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return response.status, response.read().decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as error:
        return error.code, ""
    except Exception as error:  # noqa: BLE001
        print(f"  сеть: {url} — {error}", file=sys.stderr)
        return 0, ""


def sitemap_urls(robots: str = "") -> list[str]:
    urls: list[str] = []
    queue = [f"{ORIGIN}/sitemap.xml"]
    # Тильда объявляет дополнительные карты (например sitemap-store.xml
    # с карточками каталога) только в robots.txt — читаем и их.
    for line in robots.splitlines():
        if line.lower().startswith("sitemap:"):
            declared = line.split(":", 1)[1].strip().replace("http://", "https://")
            queue.append(declared)
    seen = set()
    while queue:
        sm = queue.pop(0)
        if sm in seen:
            continue
        seen.add(sm)
        status, text = fetch(sm)
        print(f"sitemap {sm}: код {status}, {len(text)} байт")
        if status != 200:
            continue
        locs = re.findall(r"<loc>\s*(.*?)\s*</loc>", text)
        for loc in locs:
            if loc.endswith(".xml"):
                queue.append(loc)
            else:
                urls.append(loc)
    return list(dict.fromkeys(urls))


def page_info(url: str) -> dict:
    status, text = fetch(url)
    title = re.search(r"<title[^>]*>(.*?)</title>", text, re.S | re.I)
    desc = re.search(r'<meta[^>]+name="description"[^>]+content="([^"]*)"', text, re.I)
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", text, re.S | re.I)
    clean = lambda s: re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s or "")).strip()  # noqa: E731
    return {
        "url": url,
        "status": status,
        "title": clean(title.group(1) if title else "")[:160],
        "h1": clean(h1.group(1) if h1 else "")[:160],
        "description": clean(desc.group(1) if desc else "")[:200],
        "bytes": len(text),
    }


def main() -> int:
    print(f"Разведка {ORIGIN}\n")
    status, robots = fetch(f"{ORIGIN}/robots.txt")
    print(f"robots.txt: код {status}\n{robots.strip()[:800]}\n")

    urls = sitemap_urls(robots)
    print(f"\nСтраниц в sitemap: {len(urls)}")
    if not urls:
        # Тильда без sitemap — возьмём хотя бы главную и ссылки с неё
        status, home = fetch(ORIGIN + "/")
        links = sorted(set(re.findall(r'href="(' + re.escape(ORIGIN) + r'[^"#?]*|/[a-z0-9\-/]*)"', home)))
        urls = [ORIGIN + link if link.startswith("/") else link for link in links]
        urls = [u for u in dict.fromkeys(urls) if not re.search(r"\.(css|js|png|jpg|svg|ico)$", u)]
        print(f"Ссылок с главной: {len(urls)}")

    pages: list[dict] = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        for future in as_completed(pool.submit(page_info, url) for url in urls[:300]):
            pages.append(future.result())
    pages.sort(key=lambda p: p["url"])

    print("\n=== Страницы ===")
    for page in pages:
        print(f"[{page['status']}] {page['url']}")
        if page["title"]:
            print(f"      title: {page['title']}")
        if page["h1"] and page["h1"] != page["title"]:
            print(f"      h1:    {page['h1']}")

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(
        json.dumps({"origin": ORIGIN, "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "robots": robots, "pages": pages}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"\nСтраниц опрошено: {len(pages)}; отчёт: {OUT_JSON.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
