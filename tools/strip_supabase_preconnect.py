#!/usr/bin/env python3
"""Remove Supabase preconnect links from HTML (no longer needed after catalog snapshot)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERN = re.compile(
    r'\s*<link rel="preconnect" href="https://chnyazvybzzryduhgopa\.supabase\.co" crossorigin />\s*\n?',
    re.I,
)
SKIP = {"node_modules", "output", "media", ".git"}


def iter_html_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*.html"):
        if any(part in SKIP for part in path.relative_to(ROOT).parts):
            continue
        files.append(path)
    return sorted(files)


def main() -> int:
    changed = 0
    for path in iter_html_files():
        original = path.read_text(encoding="utf-8")
        updated = PATTERN.sub("\n", original)
        if updated != original:
            path.write_text(updated, encoding="utf-8")
            changed += 1
    print(f"files_changed={changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
