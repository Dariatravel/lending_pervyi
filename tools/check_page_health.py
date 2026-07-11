#!/usr/bin/env python3
"""Guardrails for generated static pages before deploy."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OBJECT_ROOTS = (ROOT / "hotels", ROOT / "kvartira")
FORBIDDEN_CLIENT_STRINGS = (
    "image-lite",
    "review_text_bank",
    "catalog-snapshot.json",
    "supabase",
    "logo-emblem" + ".png",
)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def asset_version() -> str:
    match = re.search(r'const\s+ASSET_VERSION\s*=\s*"([^"]+)"', read_text(ROOT / "scripts.js"))
    if not match:
        raise RuntimeError("Не найден ASSET_VERSION в scripts.js")
    return match.group(1)


def html_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*.html"):
        rel = path.relative_to(ROOT).as_posix()
        if rel.startswith((".git/", "node_modules/", "output/", "media/")):
            continue
        if rel.startswith("concept-"):
            continue
        files.append(path)
    return sorted(files)


def object_pages() -> list[Path]:
    pages: list[Path] = []
    for root in OBJECT_ROOTS:
        if root.exists():
            pages.extend(sorted(root.glob("*/index.html")))
    return pages


def check_html_versions(version: str, errors: list[str]) -> None:
    values: set[str] = set()
    for path in html_files():
        text = read_text(path)
        rel = path.relative_to(ROOT).as_posix()
        if "styles.css?v=" in text or "scripts.js?v=" in text:
            errors.append(f"{rel}: подключён неминифицированный CSS/JS с версией")
        for value in re.findall(r"\?v=(\d{10,14})", text):
            values.add(value)
            if value != version:
                errors.append(f"{rel}: версия ?v={value}, ожидалась {version}")
        for forbidden in FORBIDDEN_CLIENT_STRINGS:
            if forbidden in text:
                errors.append(f"{rel}: найден запрещённый клиентский маркер {forbidden}")
    if values != {version}:
        errors.append(f"HTML должен содержать ровно одну версию ?v=, найдено: {sorted(values)}")


def check_object_meta(errors: list[str]) -> None:
    for path in object_pages():
        text = read_text(path)
        rel = path.relative_to(ROOT).as_posix()
        if "favicon-48.png" not in text:
            errors.append(f"{rel}: favicon должен быть favicon-48.png")
        if 'property="og:image"' in text and "site-cover.jpg" not in text:
            errors.append(f"{rel}: og:image должен указывать на site-cover.jpg")


def check_sitemap(errors: list[str]) -> None:
    sitemap = ROOT / "sitemap.xml"
    if not sitemap.exists():
        errors.append("sitemap.xml отсутствует")
        return
    text = read_text(sitemap)
    catalog_path = ROOT / "data" / "catalog-index.json"
    if not catalog_path.exists():
        errors.append("data/catalog-index.json отсутствует")
        return
    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    for item in payload.get("listings") or []:
        expected = str(item.get("page_url") or "").strip()
        if not expected:
            slug = str(item.get("slug") or "").strip()
            source_kind = str(item.get("source_kind") or "")
            prefix = "kvartira" if source_kind == "kvartira" else "hotels"
            expected = f"/{prefix}/{slug}/"
        if expected and expected not in text:
            errors.append(f"sitemap.xml: нет страницы {expected}")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_minified_freshness(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        js_tmp = tmpdir / "scripts.min.js"
        css_tmp = tmpdir / "styles.min.css"
        subprocess.run(
            [
                "npx",
                "--yes",
                "terser",
                str(ROOT / "scripts.js"),
                "--compress",
                "--mangle",
                "--output",
                str(js_tmp),
            ],
            cwd=ROOT,
            check=True,
            stdout=subprocess.DEVNULL,
        )
        subprocess.run(
            [
                "npx",
                "--yes",
                "esbuild",
                str(ROOT / "styles.css"),
                "--minify",
                "--outfile=" + str(css_tmp),
            ],
            cwd=ROOT,
            check=True,
            stdout=subprocess.DEVNULL,
        )
        if sha256(js_tmp) != sha256(ROOT / "scripts.min.js"):
            errors.append("scripts.min.js устарел относительно scripts.js")
        if sha256(css_tmp) != sha256(ROOT / "styles.min.css"):
            errors.append("styles.min.css устарел относительно styles.css")


def check_review_banks(errors: list[str]) -> None:
    source_candidates = [
        ROOT / "media" / "reviews" / "global.json",
        Path("/Users/darya_botova/Documents/GitHub/lending_pervyi/media/reviews/global.json"),
        Path("/Users/darya_botova/Documents/New project/media/reviews/global.json"),
    ]
    if not any(path.exists() for path in source_candidates):
        errors.append("Не найден локальный источник media/reviews/global.json для CDN-банка отзывов")


def html_attr(tag: str, name: str) -> str:
    match = re.search(rf'\b{name}\s*=\s*(["\'])(.*?)\1', tag, flags=re.I | re.S)
    return match.group(2) if match else ""


def check_catalog_card_srcsets(errors: list[str]) -> None:
    for path in html_files():
        text = read_text(path)
        rel = path.relative_to(ROOT).as_posix()
        cards = re.findall(r'<a\b[^>]*class=["\'][^"\']*\bcatalog-card\b[^"\']*["\'][\s\S]*?</a>', text, flags=re.I)
        for index, card in enumerate(cards, start=1):
            img_match = re.search(r"<img\b[^>]*>", card, flags=re.I | re.S)
            if not img_match:
                continue
            img = img_match.group(0)
            src = html_attr(img, "src")
            if "storage.yandexcloud.net/abhazbereg-media/media/" not in src:
                continue
            if "/media/branding/" in src:
                continue
            srcset = html_attr(img, "srcset")
            if "-480.webp" not in srcset:
                errors.append(f"{rel}: catalog-card #{index} без srcset с -480.webp")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-minify-check", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    errors: list[str] = []
    version = asset_version()
    check_html_versions(version, errors)
    check_object_meta(errors)
    check_sitemap(errors)
    check_review_banks(errors)
    check_catalog_card_srcsets(errors)
    if not args.skip_minify_check:
        check_minified_freshness(errors)

    payload = {"status": "ok" if not errors else "failed", "asset_version": version, "errors": errors}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif errors:
        print("Проверка страниц не прошла:")
        for error in errors:
            print(f"- {error}")
    else:
        print(f"Проверка страниц прошла. ASSET_VERSION={version}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
