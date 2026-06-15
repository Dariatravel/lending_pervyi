#!/usr/bin/env python3
"""Inventory Supabase/media dependencies in site source files."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "migration_stage1_site_links.json"
GLOBS = ("*.html", "*.js", "*.json", "*.css", "*.py", "*.md")
SKIP_DIRS = {"node_modules", "output", "media", "tmp", ".git"}

PATTERNS = {
    "supabase_domain": re.compile(r"supabase\.co", re.I),
    "site_media_videos": re.compile(r"site-media/videos", re.I),
    "site_media_photos": re.compile(
        r"site-media/(cards|hotels|kvartira|kvartira-cards|branding|blog|reviews)",
        re.I,
    ),
    "fetch_listings": re.compile(r"fetchListings|fetchListingBySlug", re.I),
    "supabase_client": re.compile(r"createClient|@supabase/supabase-js|ABHAZBEREG_SUPABASE", re.I),
    "yandex_media": re.compile(r"storage\.yandexcloud\.net/abhazbereg-media", re.I),
}


def iter_files() -> list[Path]:
    files: list[Path] = []
    for pattern in GLOBS:
        for path in ROOT.rglob(pattern):
            if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
                continue
            files.append(path)
    return sorted(set(files))


def main() -> int:
    totals = Counter()
    by_pattern_files: dict[str, list[str]] = defaultdict(list)

    for path in iter_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        rel = str(path.relative_to(ROOT))
        for name, pattern in PATTERNS.items():
            matches = pattern.findall(text)
            if matches:
                totals[name] += len(matches)
                if len(by_pattern_files[name]) < 30:
                    by_pattern_files[name].append(rel)

    report = {
        "totals": dict(totals),
        "sample_files": by_pattern_files,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
