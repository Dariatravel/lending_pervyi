#!/usr/bin/env python3
"""Собирает data/blog-posts.json из опубликованных страниц blog/*/index.html."""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLOG_DIR = ROOT / "blog"
OUT_PATH = ROOT / "data" / "blog-posts.json"


def parse_article(path: Path) -> dict[str, object]:
    slug = path.parent.name
    text = path.read_text(encoding="utf-8")

    title_match = re.search(r"<h1>(.*?)</h1>", text, re.S)
    title = html.unescape(re.sub(r"<[^>]+>", "", title_match.group(1)).strip()) if title_match else slug

    lead_match = re.search(r'class="blog-hero__lead">(.*?)</p>', text, re.S)
    excerpt = html.unescape(re.sub(r"<[^>]+>", "", lead_match.group(1)).strip()) if lead_match else ""

    time_match = re.search(r'<time datetime="([^"]+)"', text)
    iso_date = time_match.group(1) if time_match else ""

    tags_block = re.search(r'<div class="blog-tags">(.*?)</div>', text, re.S)
    tag_spans = re.findall(r"<span>([^<]+)</span>", tags_block.group(1)) if tags_block else []
    tag_spans = [html.unescape(tag.strip()) for tag in tag_spans if tag.strip()]

    eyebrow_match = re.search(r'class="site-concept__eyebrow">([^<]+)</p>', text)
    card_tag = tag_spans[0] if tag_spans else (eyebrow_match.group(1).strip() if eyebrow_match else "")

    img_match = re.search(r'class="blog-article__cover-inline" src="([^"]+)"', text)
    img_src = img_match.group(1) if img_match else ""
    if "/media/blog/" in img_src:
        image = img_src.split("/media/blog/", 1)[1]
    else:
        image = img_src.rsplit("/", 1)[-1]

    return {
        "slug": slug,
        "title": title,
        "excerpt": excerpt[:220],
        "iso_date": iso_date,
        "card_tag": card_tag,
        "tags": tag_spans,
        "image": image,
    }


def build_manifest() -> list[dict[str, object]]:
    posts = [parse_article(path) for path in sorted(BLOG_DIR.glob("*/index.html"))]
    posts.sort(key=lambda item: str(item.get("iso_date") or ""), reverse=True)
    return posts


def main() -> int:
    posts = build_manifest()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(posts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"blog-posts.json: {len(posts)} статей → {OUT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
