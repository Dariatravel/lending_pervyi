#!/usr/bin/env python3
"""Audit remaining Supabase references in production-facing site files."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "output" / "migration_stage7_prod_audit.json"

PROD_GLOBS = ("*.html", "*.js", "*.css", "*.json")
SKIP_PARTS = {"node_modules", "output", "media", ".git", "supabase", "scripts", "tools", "collab_bot", "cashback_tracker"}
LEGACY_FALLBACK_JS = {"scripts.js", "image-lite.js"}
PATTERNS = {
    "supabase.co_url": re.compile(r"https?://[^\s\"']*supabase\.co", re.I),
    "site_media_storage": re.compile(r"storage/v1/object/public/site-media", re.I),
    "createClient": re.compile(r"createClient\s*\(", re.I),
    "supabase_js_cdn": re.compile(r"@supabase/supabase-js", re.I),
}


def iter_prod_files() -> list[Path]:
    files: list[Path] = []
    for pattern in PROD_GLOBS:
        for path in ROOT.rglob(pattern):
            rel = path.relative_to(ROOT)
            if any(part in SKIP_PARTS for part in rel.parts):
                continue
            if rel.name == "catalog-snapshot.json":
                continue
            files.append(path)
    return sorted(set(files))


def main() -> int:
    findings: dict[str, list[str]] = {key: [] for key in PATTERNS}
    for path in iter_prod_files():
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = str(path.relative_to(ROOT))
        for name, pattern in PATTERNS.items():
            if pattern.search(text):
                if name == "site_media_storage" and path.name in LEGACY_FALLBACK_JS:
                    continue
                findings[name].append(rel)

    payload = {
        "prod_files_scanned": len(iter_prod_files()),
        "issues_by_kind": {k: len(v) for k, v in findings.items()},
        "files": findings,
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(payload["issues_by_kind"], ensure_ascii=False))
    for kind, files in findings.items():
        if not files:
            continue
        print(f"\n{kind}:")
        for rel in files[:20]:
            print(f"  - {rel}")
        if len(files) > 20:
            print(f"  ... +{len(files) - 20} more")

    blocking = sum(payload["issues_by_kind"].values())
    return 1 if blocking else 0


if __name__ == "__main__":
    raise SystemExit(main())
