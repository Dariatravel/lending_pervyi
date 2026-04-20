#!/usr/bin/env python3
"""
Проверка: фото и видео на страницах отелей/квартир ссылаются на папки того же slug,
что и страница (отсечь перепутанные медиа между объектами).

Запуск из корня: python3 tools/verify_object_media.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# URL или путь → нормализованный путь (без домена, lower)
_URL_RE = re.compile(r"https?://[^/]+", re.I)
_SRC_RE = re.compile(r'\b(?:src|content)=["\']([^"\']+)["\']', re.I)
_META_OG_IMAGE = re.compile(
    r'<meta\s+property=["\']og:image["\']\s+content=["\']([^"\']+)["\']',
    re.I,
)

# Сегмент пути после которого идёт slug объекта
_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"/media/hotels/([^/]+)/", re.I), "hotel gallery"),
    (re.compile(r"/media/kvartira/([^/]+)/", re.I), "kvartira gallery"),
    (re.compile(r"/media/cards/([^/.?#]+)\.", re.I), "hotel card cover"),
    (re.compile(r"/media/kvartira-cards/([^/.?#]+)-cover\.", re.I), "kvartira card cover"),
    (re.compile(r"/videos/hotels/([^/]+)/", re.I), "hotel video"),
    (re.compile(r"/videos/kvartira/([^/]+)/", re.I), "kvartira video"),
]


def normalize_to_path(url: str) -> str:
    u = url.strip()
    u = _URL_RE.sub("", u)
    if u.startswith("//"):
        u = u[1:]
    u = u.split("?")[0].split("#")[0]
    if not u.startswith("/"):
        u = "/" + u.lstrip("/")
    return u


def extract_media_urls(html: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for m in _META_OG_IMAGE.finditer(html):
        u = m.group(1)
        if u not in seen:
            seen.add(u)
            out.append(u)
    for m in _SRC_RE.finditer(html):
        u = m.group(1)
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def slug_from_object_url(path_norm: str) -> tuple[str, str] | None:
    low = path_norm.lower()
    for rx, _label in _PATTERNS:
        m = rx.search(low)
        if m:
            return m.group(1), _label
    return None


def is_probably_global_asset(path_norm: str) -> bool:
    low = path_norm.lower()
    if "/fonts." in low or "fonts.googleapis" in low:
        return True
    if low.endswith("styles.css"):
        return True
    if "telegram.org" in low or "t.me/" in low:
        return True
    if "/media/branding/" in low:
        return True
    if "/media/hero" in low or "/media/site" in low:
        return True
    return False


def check_page(kind: str, slug: str, html: str) -> list[str]:
    issues: list[str] = []
    for raw in extract_media_urls(html):
        if not raw or raw.startswith("data:"):
            continue
        p = normalize_to_path(raw)
        if is_probably_global_asset(p):
            continue
        # og:image иногда склеен с доменом дважды
        if "абхазберег.рфhttps://" in raw or "абхазберег.рфhttp://" in raw:
            issues.append(f"битый og:image/URL (двойной домен): {raw[:120]}...")
            continue
        parsed = slug_from_object_url(p)
        if not parsed:
            continue
        media_slug, label = parsed
        if media_slug != slug:
            issues.append(
                f"{label}: в URL slug «{media_slug}», ожидался «{slug}»: …{p[-80:]}"
            )
    return issues


def verify_kvartira_json() -> list[str]:
    path = REPO / "kvartira_cards.json"
    if not path.is_file():
        return []
    issues: list[str] = []
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return [f"kvartira_cards.json: не читается ({e})"]
    for row in rows:
        slug = row.get("slug")
        img = (row.get("image") or "").strip()
        if not slug or not img:
            continue
        p = normalize_to_path(img)
        parsed = slug_from_object_url(p)
        if parsed and parsed[0] != slug:
            issues.append(
                f"kvartira_cards.json: slug {slug} — image указывает на {parsed[0]} ({img})"
            )
        elif "/kvartira-cards/" in p.lower() and f"{slug}-cover" not in p.lower():
            issues.append(
                f"kvartira_cards.json: slug {slug} — подозрительный cover: {img}"
            )
    return issues


def check_local_gallery_exists(kind: str, slug: str) -> list[str]:
    """Проверка, что основное фото галереи есть в репозитории (опционально)."""
    if kind == "hotel":
        photo = REPO / "media" / "hotels" / slug / "photo-01.jpg"
    else:
        photo = REPO / "media" / "kvartira" / slug / "photo-01.jpg"
    if not photo.is_file():
        return [f"нет файла галереи {photo.relative_to(REPO)}"]
    return []


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--check-files",
        action="store_true",
        help="проверить наличие media/.../photo-01.jpg для каждой страницы",
    )
    args = ap.parse_args()

    all_issues: list[str] = []

    for base, kind in (("hotels", "hotel"), ("kvartira", "kvartira")):
        root = REPO / base
        if not root.is_dir():
            continue
        for sub in sorted(root.iterdir()):
            if not sub.is_dir():
                continue
            idx = sub / "index.html"
            if not idx.is_file():
                continue
            slug = sub.name
            html = idx.read_text(encoding="utf-8")
            for msg in check_page(kind, slug, html):
                all_issues.append(f"{base}/{slug}/index.html: {msg}")
            if args.check_files:
                for msg in check_local_gallery_exists(kind, slug):
                    all_issues.append(f"{base}/{slug}/index.html: {msg}")

    all_issues.extend(verify_kvartira_json())

    if not all_issues:
        print("OK: все проверенные URL объектных медиа согласованы со slug страницы.")
        print("    (Проверены пути /media/hotels/, /media/kvartira/, /media/cards/, "
              "/media/kvartira-cards/*-cover*, /videos/hotels|kvartira/ в URL.)")
        return 0

    print("Найдены несоответствия или битые URL:\n", file=sys.stderr)
    for line in all_issues:
        print(line, file=sys.stderr)
    print(f"\nВсего: {len(all_issues)}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
