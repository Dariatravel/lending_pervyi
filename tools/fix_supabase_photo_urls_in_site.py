#!/usr/bin/env python3
"""Replace Supabase Storage photo URLs with Yandex CDN in site files."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from media_urls import yandex_photo_url  # noqa: E402

PHOTO_PREFIX = r"(?:cards|hotels|kvartira|kvartira-cards|branding|blog|reviews)"
SUPABASE_PHOTO_RE = re.compile(
    rf"https://chnyazvybzzryduhgopa\.supabase\.co/storage/v1/(?:object/public|render/image/public)/site-media/{PHOTO_PREFIX}/[^\s\"'<>]+",
    re.I,
)
GLOBS = ("*.html", "*.json", "*.js", "*.css")
SKIP_DIRS = {"media", "output", "node_modules", "tmp", ".git"}


def iter_site_files() -> list[Path]:
    files: list[Path] = []
    for pattern in GLOBS:
        for path in ROOT.rglob(pattern):
            if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
                continue
            files.append(path)
    return sorted(set(files))


def rewrite_text(text: str) -> tuple[str, int]:
    count = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal count
        old = match.group(0)
        new = yandex_photo_url(old.split("?", 1)[0])
        if new != old:
            count += 1
        return new

    return SUPABASE_PHOTO_RE.sub(repl, text), count


def main() -> int:
    total = 0
    touched: list[tuple[Path, int]] = []
    for path in iter_site_files():
        original = path.read_text(encoding="utf-8")
        updated, count = rewrite_text(original)
        if count:
            path.write_text(updated, encoding="utf-8")
            touched.append((path, count))
            total += count
    print(f"files_changed={len(touched)} replacements={total}")
    for path, count in touched[:20]:
        print(f"  {path.relative_to(ROOT)}: {count}")
    if len(touched) > 20:
        print(f"  ... and {len(touched) - 20} more files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
