#!/usr/bin/env python3
"""Перелинковка статей блога по тематическим кластерам.

Робот Яндекса не видит блок «Может быть полезно по теме»: он собирается
скриптом уже в браузере. Поэтому в HTML статьи добавляется статический блок
«Читайте по теме» со ссылками на соседей по кластеру
(data/blog-clusters.json) и, где это уместно, кнопка перехода в каталог.

Тексты статей не меняются: блок вставляется перед разделом «Как бронировать».
Скрипт идемпотентен — свой блок он каждый раз пересобирает заново.

Запуск:
    python3 scripts/inject_blog_related_links.py [--check]
"""
from __future__ import annotations

import argparse
import html as html_mod
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLOG_ROOT = ROOT / "blog"
CLUSTERS_PATH = ROOT / "data" / "blog-clusters.json"

RELATED_RX = re.compile(r'\s*<section class="blog-related".*?</section>', re.S)
ANCHOR_RX = re.compile(r'<section class="site-concept__section-block" id="guide">', re.I)
H1_RX = re.compile(r"<h1[^>]*>(.*?)</h1>", re.S | re.I)
MAX_LINKS = 3


def load_clusters() -> dict:
    data = json.loads(CLUSTERS_PATH.read_text(encoding="utf-8"))
    return data.get("clusters", {})


def article_title(slug: str) -> str:
    path = BLOG_ROOT / slug / "index.html"
    if not path.is_file():
        return ""
    match = H1_RX.search(path.read_text(encoding="utf-8"))
    if not match:
        return ""
    return html_mod.unescape(re.sub(r"<[^>]+>", "", match.group(1))).strip()


def build_block(cluster_title: str, links: list[tuple[str, str]], cta: dict | None) -> str:
    items = "".join(
        f'<li><a href="/blog/{slug}/">{html_mod.escape(title)}</a></li>' for slug, title in links
    )
    cta_html = ""
    if cta:
        cta_html = (
            '<p class="blog-catalog-cta">'
            f'<a class="btn-book" data-goal="blog_catalog_cta_click" href="{html_mod.escape(cta["href"], quote=True)}">'
            f'{html_mod.escape(cta["text"])}</a></p>'
        )
    return (
        f'\n<section class="blog-related" aria-label="Другие статьи по теме: {html_mod.escape(cluster_title)}">'
        f'<h2 class="blog-related__title">Читайте по теме — {html_mod.escape(cluster_title)}</h2>'
        f'<ul class="blog-related__list">{items}</ul>{cta_html}</section>\n'
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="ничего не записывать")
    args = parser.parse_args()

    clusters = load_clusters()
    titles = {slug: article_title(slug) for cluster in clusters.values() for slug in cluster["slugs"]}

    changed = 0
    skipped: list[str] = []
    for cluster_key, cluster in clusters.items():
        slugs = [s for s in cluster["slugs"] if (BLOG_ROOT / s / "index.html").is_file()]
        for position, slug in enumerate(slugs):
            # Ссылки берём по кругу от текущей статьи, иначе весь кластер
            # ссылался бы на одни и те же три страницы.
            rotated = slugs[position + 1:] + slugs[:position]
            neighbours = [(s, titles.get(s, "")) for s in rotated if s != slug and titles.get(s)]
            if len(neighbours) < 2:
                continue
            block = build_block(cluster["title"], neighbours[:MAX_LINKS], cluster.get("cta"))
            path = BLOG_ROOT / slug / "index.html"
            text = path.read_text(encoding="utf-8")
            cleaned = RELATED_RX.sub("", text)
            anchor = ANCHOR_RX.search(cleaned)
            if not anchor:
                skipped.append(slug)
                continue
            updated = cleaned[: anchor.start()] + block + cleaned[anchor.start():]
            if updated == text:
                continue
            changed += 1
            print(f"{cluster_key}: {slug} → {len(neighbours[:MAX_LINKS])} ссылок"
                  f"{' + CTA' if cluster.get('cta') else ''}")
            if not args.check:
                path.write_text(updated, encoding="utf-8")

    if skipped:
        print(f"Пропущены (нет якоря «Как бронировать»): {', '.join(skipped)}")
    print(f"Статей обновлено: {changed}{' (проверка, без записи)' if args.check else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
