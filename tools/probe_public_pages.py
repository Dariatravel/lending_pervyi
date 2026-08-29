#!/usr/bin/env python3
"""Разведка публичных страниц (соцсети, карточки организаций) из GitHub Actions.

Из песочницы агента внешние сайты закрыты прокси, поэтому пробник запускается
на раннере Actions (workflow web-probe.yml): по каждому URL печатает конечный
адрес после редиректов, HTTP-статус, <title>, og:title/og:description и первые
строки видимого текста. Этого хватает, чтобы понять, как страница выглядит
для поисковых и ИИ-ботов, не открывая её глазами.

Запуск: python3 tools/probe_public_pages.py <url> [<url> ...]
"""

from __future__ import annotations

import html
import re
import sys
import urllib.error
import urllib.request

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
TIMEOUT = 30


def meta(page: str, needle: str) -> str:
    match = re.search(
        r'<meta[^>]+(?:property|name)=["\']' + re.escape(needle) + r'["\'][^>]+content=["\']([^"\']*)',
        page,
        re.I,
    ) or re.search(
        r'<meta[^>]+content=["\']([^"\']*)["\'][^>]+(?:property|name)=["\']' + re.escape(needle) + r'["\']',
        page,
        re.I,
    )
    return html.unescape(match.group(1)) if match else ""


def visible_text(page: str, limit: int = 600) -> str:
    page = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", " ", page, flags=re.S | re.I)
    page = re.sub(r"<[^>]+>", " ", page)
    page = html.unescape(re.sub(r"\s+", " ", page)).strip()
    return page[:limit]


def probe(url: str) -> None:
    print(f"\n=== {url}")
    request = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ru,en"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            body = response.read(2_000_000).decode("utf-8", errors="replace")
            print(f"  статус: {response.status}")
            print(f"  конечный URL: {response.url}")
    except urllib.error.HTTPError as error:
        print(f"  статус: {error.code} ({error.reason})")
        return
    except (urllib.error.URLError, OSError, ValueError) as error:
        print(f"  ошибка: {error}")
        return
    title = re.search(r"<title[^>]*>(.*?)</title>", body, re.S | re.I)
    if title:
        print(f"  title: {html.unescape(title.group(1)).strip()[:200]}")
    for field in ("og:title", "og:description", "description"):
        value = meta(body, field)
        if value:
            print(f"  {field}: {value[:300]}")
    print(f"  текст: {visible_text(body)}")
    org_links = sorted(
        {
            match
            for match in re.findall(r'https?://[^"\'\s<>]+', body)
            if "/maps/org/" in match or "2gis.ru/firm/" in match
        }
    )
    for link in org_links[:20]:
        print(f"  карточка: {link}")


def main() -> int:
    urls = sys.argv[1:]
    if not urls:
        print("Использование: probe_public_pages.py <url> [<url> ...]")
        return 2
    for url in urls:
        probe(url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
