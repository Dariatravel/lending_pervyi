#!/usr/bin/env python3
"""Технический SEO-аудит по рекомендациям Яндекс.Вебмастера.

Проверяет то, за что Вебмастер снимает страницы с показа: одинаковые title и
description, отсутствие canonical, битые og:image, неполный Article JSON-LD и
расхождения между sitemap.xml и реальными страницами.

Запуск:
    python3 tools/audit_yandex_webmaster_seo.py            # отчёт в файл и в консоль
    python3 tools/audit_yandex_webmaster_seo.py --strict   # выход 1, если есть FAIL

Отчёт: output/yandex_webmaster_seo_audit.txt
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import unquote, urlparse
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = ROOT / "output" / "yandex_webmaster_seo_audit.txt"
SITEMAP_PATH = ROOT / "sitemap.xml"
CANON_ORIGIN = "https://абхазберег.рф"
PUNY_ORIGIN = "https://xn--80aacbklan7f0b.xn--p1ai"

SECTIONS = ("blog", "hotels", "kvartira", "podborki")
IMAGE_EXT = (".jpg", ".jpeg", ".png", ".webp", ".gif")

TITLE_RX = re.compile(r"<title[^>]*>(.*?)</title>", re.S | re.I)
META_RX = re.compile(r"<meta\b[^>]*>", re.I)
ATTR_RX = re.compile(r'(\w[\w:-]*)\s*=\s*"([^"]*)"|(\w[\w:-]*)\s*=\s*\'([^\']*)\'')
CANONICAL_RX = re.compile(r'<link\b[^>]*rel=["\']canonical["\'][^>]*>', re.I)
HREF_RX = re.compile(r'href=["\']([^"\']+)["\']', re.I)
JSONLD_RX = re.compile(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.S | re.I)
TIME_RX = re.compile(r'<time[^>]*datetime=["\'](\d{4}-\d{2}-\d{2})', re.I)


def meta_map(html: str) -> dict[str, str]:
    """name/property → content для всех <meta> страницы."""
    found: dict[str, str] = {}
    for tag in META_RX.findall(html):
        attrs: dict[str, str] = {}
        for m in ATTR_RX.finditer(tag):
            key = (m.group(1) or m.group(3) or "").lower()
            attrs[key] = m.group(2) if m.group(2) is not None else (m.group(4) or "")
        key = attrs.get("name") or attrs.get("property")
        if key:
            found.setdefault(key.lower(), attrs.get("content", ""))
    return found


def canonical_of(html: str) -> str:
    tag = CANONICAL_RX.search(html)
    if not tag:
        return ""
    href = HREF_RX.search(tag.group(0))
    return href.group(1).strip() if href else ""


def title_of(html: str) -> str:
    m = TITLE_RX.search(html)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""


def json_ld_blocks(html: str) -> list[dict]:
    blocks: list[dict] = []
    for raw in JSONLD_RX.findall(html):
        try:
            data = json.loads(raw.strip())
        except Exception:  # noqa: BLE001 — битый JSON-LD ловим отдельной проверкой
            blocks.append({"@type": "__broken__", "raw": raw[:120]})
            continue
        blocks.extend(data if isinstance(data, list) else [data])
    return blocks


def page_url(path: Path) -> str:
    rel = path.parent.relative_to(ROOT).as_posix()
    return f"{CANON_ORIGIN}/" if rel == "." else f"{CANON_ORIGIN}/{rel}/"


def collect_pages() -> list[Path]:
    pages: list[Path] = []
    root_index = ROOT / "index.html"
    if root_index.is_file():
        pages.append(root_index)
    for section in SECTIONS:
        base = ROOT / section
        if not base.is_dir():
            continue
        index = base / "index.html"
        if index.is_file():
            pages.append(index)
        pages.extend(sorted(base.glob("*/index.html")))
    return pages


def sitemap_urls() -> set[str]:
    if not SITEMAP_PATH.is_file():
        return set()
    try:
        tree = ET.parse(SITEMAP_PATH)
    except ET.ParseError:
        return set()
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls: set[str] = set()
    for loc in tree.getroot().findall(".//sm:loc", ns):
        raw = (loc.text or "").strip().replace(PUNY_ORIGIN, CANON_ORIGIN)
        if raw:
            urls.add(raw)
    return urls


def local_path_for_url(url: str) -> Path:
    rel = unquote(urlparse(url).path or "/").strip("/")
    return (ROOT / rel / "index.html") if rel else (ROOT / "index.html")


class Report:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.fails = 0
        self.warns = 0

    def block(self, level: str, title: str, items: list[str], limit: int = 40) -> None:
        if level == "FAIL":
            self.fails += 1
        elif level == "WARN":
            self.warns += 1
        self.lines.append(f"[{level}] {title}: {len(items)}" if items else f"[OK] {title}")
        for item in items[:limit]:
            self.lines.append(f"    - {item}")
        if len(items) > limit:
            self.lines.append(f"    … и ещё {len(items) - limit}")
        self.lines.append("")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="выход 1 при наличии FAIL")
    args = parser.parse_args()

    pages = collect_pages()
    titles: dict[str, list[str]] = defaultdict(list)
    descriptions: dict[str, list[str]] = defaultdict(list)
    no_canonical: list[str] = []
    bad_canonical: list[str] = []
    bad_og: list[str] = []
    no_publisher: list[str] = []
    stale_modified: list[str] = []
    broken_ld: list[str] = []
    dead_redirects: list[str] = []
    empty_title: list[str] = []
    indexable: list[Path] = []

    for path in pages:
        html = path.read_text(encoding="utf-8", errors="ignore")
        url = page_url(path)
        metas = meta_map(html)
        robots = metas.get("robots", "")
        if "noindex" in robots.lower():
            # Страница-редирект короткой ссылки: проверяем только, что цель жива.
            target = HREF_RX.search(CANONICAL_RX.search(html).group(0)) if CANONICAL_RX.search(html) else None
            if target and not local_path_for_url(target.group(1)).is_file():
                dead_redirects.append(f"{url} → {target.group(1)} (страницы нет)")
            continue
        indexable.append(path)

        title = title_of(html)
        if not title:
            empty_title.append(url)
        else:
            titles[title].append(url)
        description = re.sub(r"\s+", " ", metas.get("description", "")).strip()
        if description:
            descriptions[description].append(url)

        canonical = canonical_of(html)
        if not canonical:
            no_canonical.append(url)
        elif canonical.replace(PUNY_ORIGIN, CANON_ORIGIN).rstrip("/") != url.rstrip("/"):
            bad_canonical.append(f"{url} → {canonical}")

        og_image = metas.get("og:image", "").strip()
        if not og_image:
            bad_og.append(f"{url}: og:image отсутствует")
        elif not og_image.lower().startswith("http"):
            bad_og.append(f"{url}: og:image не абсолютный ({og_image})")
        elif not og_image.lower().split("?")[0].endswith(IMAGE_EXT):
            bad_og.append(f"{url}: og:image без файла картинки ({og_image})")

        page_time = max(TIME_RX.findall(html), default="")
        for block in json_ld_blocks(html):
            if block.get("@type") == "__broken__":
                broken_ld.append(f"{url}: {block.get('raw', '')}")
                continue
            if block.get("@type") != "Article":
                continue
            if not block.get("publisher"):
                no_publisher.append(url)
            published = str(block.get("datePublished", ""))
            modified = str(block.get("dateModified", ""))
            if published and modified == published and page_time and page_time > modified:
                stale_modified.append(f"{url}: JSON-LD {modified}, на странице {page_time}")

    sm = sitemap_urls()
    site_pages = {page_url(p) for p in indexable}
    sitemap_without_html = sorted(u for u in sm if not local_path_for_url(u).is_file())
    html_without_sitemap = sorted(
        u for u in site_pages
        if u not in sm and any(f"/{s}/" in u for s in SECTIONS)
    )

    rep = Report()
    rep.lines.append("SEO-аудит по рекомендациям Яндекс.Вебмастера")
    rep.lines.append(f"Страниц проверено: {len(pages)} (индексируемых {len(indexable)}, "
                     f"редиректов {len(pages) - len(indexable)})")
    rep.lines.append(f"URL в sitemap.xml: {len(sm)}")
    rep.lines.append("")

    dup_titles = [f"«{t}» — {len(u)} стр.: {', '.join(u[:4])}" for t, u in sorted(titles.items()) if len(u) > 1]
    dup_desc = [f"«{d[:70]}…» — {len(u)} стр.: {', '.join(u[:4])}" for d, u in sorted(descriptions.items()) if len(u) > 1]

    rep.block("FAIL" if dup_titles else "OK", "Дубли title", dup_titles)
    rep.block("FAIL" if dup_desc else "OK", "Дубли description", dup_desc)
    rep.block("FAIL" if empty_title else "OK", "Страницы без title", empty_title)
    rep.block("FAIL" if no_canonical else "OK", "Страницы без canonical", no_canonical)
    rep.block("WARN" if bad_canonical else "OK", "Canonical не совпадает с адресом страницы", bad_canonical)
    rep.block("FAIL" if bad_og else "OK", "Проблемы с og:image", bad_og)
    rep.block("FAIL" if broken_ld else "OK", "Битый JSON-LD", broken_ld)
    rep.block("WARN" if no_publisher else "OK", "Article JSON-LD без publisher", no_publisher)
    rep.block("WARN" if stale_modified else "OK", "dateModified отстаёт от даты на странице", stale_modified)
    rep.block("WARN" if dead_redirects else "OK", "Редиректы на несуществующие страницы", dead_redirects)
    rep.block("FAIL" if sitemap_without_html else "OK", "URL в sitemap без страницы в репозитории", sitemap_without_html)
    rep.block("WARN" if html_without_sitemap else "OK", "Страницы разделов вне sitemap", html_without_sitemap)

    rep.lines.append(f"ИТОГО: FAIL-групп {rep.fails}, WARN-групп {rep.warns}")
    text = "\n".join(rep.lines)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(text + "\n", encoding="utf-8")
    print(text)
    print(f"\nОтчёт: {OUT_PATH.relative_to(ROOT)}")
    return 1 if (args.strict and rep.fails) else 0


if __name__ == "__main__":
    sys.exit(main())
