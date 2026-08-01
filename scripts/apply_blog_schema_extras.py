#!/usr/bin/env python3
"""Расширенная schema.org-разметка статей блога.

Делает две вещи и ничего больше — тексты статей не трогает:
  1) дописывает publisher в Article JSON-LD (Яндекс без издателя не берёт
     статью в быстрые ответы Алисы);
  2) вставляет второй блок JSON-LD с FAQPage / HowTo из
     data/blog-schema-extras.json.

Скрипт идемпотентен: повторный запуск переписывает свой блок
(data-schema="extras") и не плодит дубли.

Запуск:
    python3 scripts/apply_blog_schema_extras.py           # все статьи
    python3 scripts/apply_blog_schema_extras.py --check   # только показать
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLOG_ROOT = ROOT / "blog"
EXTRAS_PATH = ROOT / "data" / "blog-schema-extras.json"
SITE = "https://абхазберег.рф"

PUBLISHER = {
    "@type": "Organization",
    "name": "АБХАЗБЕРЕГ",
    "url": f"{SITE}/",
}

ANY_LD_RX = re.compile(
    r'<script(?![^>]*data-schema)[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', re.S
)
EXTRAS_LD_RX = re.compile(
    r'\s*<script data-schema="extras" type="application/ld\+json">.*?</script>', re.S
)


def load_extras() -> dict:
    if not EXTRAS_PATH.is_file():
        return {}
    data = json.loads(EXTRAS_PATH.read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if not k.startswith("_")}


def build_faq(slug: str, items: list[dict]) -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": item["q"],
                "acceptedAnswer": {"@type": "Answer", "text": item["a"]},
            }
            for item in items
        ],
        "url": f"{SITE}/blog/{slug}/",
    }


def build_howto(slug: str, spec: dict) -> dict:
    blob = {
        "@context": "https://schema.org",
        "@type": "HowTo",
        "name": spec["name"],
        "step": [
            {
                "@type": "HowToStep",
                "position": i,
                "name": step["name"],
                "text": step["text"],
            }
            for i, step in enumerate(spec.get("steps", []), start=1)
        ],
        "url": f"{SITE}/blog/{slug}/",
    }
    if spec.get("totalTime"):
        blob["totalTime"] = spec["totalTime"]
    return blob


def add_publisher(html: str) -> tuple[str, bool]:
    """Дописывает publisher в блок Article, не трогая остальные блоки JSON-LD."""
    changed = False

    def patch(match: re.Match) -> str:
        nonlocal changed
        try:
            blob = json.loads(match.group(1))
        except json.JSONDecodeError:
            return match.group(0)
        if not isinstance(blob, dict) or blob.get("@type") != "Article" or blob.get("publisher"):
            return match.group(0)
        ordered: dict = {}
        for key, value in blob.items():
            ordered[key] = value
            if key == "author":
                ordered["publisher"] = PUBLISHER
        ordered.setdefault("publisher", PUBLISHER)
        changed = True
        dumped = json.dumps(ordered, ensure_ascii=False)
        return match.group(0).replace(match.group(1), dumped, 1)

    return ANY_LD_RX.sub(patch, html), changed


def apply_extras(html: str, slug: str, spec: dict) -> tuple[str, list[str]]:
    blobs: list[dict] = []
    kinds: list[str] = []
    if spec.get("howTo"):
        blobs.append(build_howto(slug, spec["howTo"]))
        kinds.append("HowTo")
    if spec.get("faq"):
        blobs.append(build_faq(slug, spec["faq"]))
        kinds.append("FAQPage")
    html = EXTRAS_LD_RX.sub("", html)
    if not blobs:
        return html, []
    payload = json.dumps(blobs if len(blobs) > 1 else blobs[0], ensure_ascii=False)
    payload = payload.replace("<", "\\u003c")
    tag = f'\n<script data-schema="extras" type="application/ld+json">{payload}</script>'
    if "</head>" not in html:
        return html, []
    return html.replace("</head>", f"{tag}\n</head>", 1), kinds


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="ничего не записывать")
    parser.add_argument("--slug", action="append", default=[], help="только эти статьи")
    args = parser.parse_args()

    extras = load_extras()
    touched = 0
    for path in sorted(BLOG_ROOT.glob("*/index.html")):
        slug = path.parent.name
        if args.slug and slug not in args.slug:
            continue
        html = path.read_text(encoding="utf-8")
        original = html
        html, publisher_added = add_publisher(html)
        html, kinds = apply_extras(html, slug, extras.get(slug, {}))
        if html == original:
            continue
        touched += 1
        marks = []
        if publisher_added:
            marks.append("publisher")
        marks.extend(kinds)
        print(f"{'[check] ' if args.check else ''}{slug}: {', '.join(marks) or 'очистка'}")
        if not args.check:
            path.write_text(html, encoding="utf-8")
    print(f"Страниц изменено: {touched}{' (проверка, без записи)' if args.check else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
