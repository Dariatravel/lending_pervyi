#!/usr/bin/env python3
"""Stage 1 migration report (generated)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "output" / "supabase_archive_2026-06-13"
SITE_LINKS = ROOT / "output" / "migration_stage1_site_links.json"
REPORT = ROOT / "output" / "migration_stage1_report.txt"


def main() -> int:
    summary = json.loads((ARCHIVE / "summary.json").read_text(encoding="utf-8"))
    manifest = json.loads((ARCHIVE / "storage_manifest.json").read_text(encoding="utf-8"))
    site = json.loads(SITE_LINKS.read_text(encoding="utf-8"))

    lines = [
        "# Migration Stage 1 — Inventory & Archive",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Archive",
        f"- Path: {ARCHIVE.relative_to(ROOT)}",
        f"- Listings: {summary['listings_total']} (active {summary['listings_active']})",
        f"- Hotels: {summary['listings_hotels']}, Kvartira: {summary['listings_kvartira']}",
        f"- listing_media rows: {summary['listing_media_total']}",
        f"- Videos in DB: {summary['listing_media_video']}",
        f"- Images in DB: {summary['listing_media_image']}",
        "",
        "## Storage manifest (DB)",
        f"- Prefixes: {manifest['by_prefix_from_db']}",
        f"- MIME types: {manifest['by_mime_from_db']}",
        f"- URL sources in listing_media: {manifest['url_sources']}",
        "",
        "## Supabase bucket listing (API sample counts)",
    ]
    for prefix, info in manifest["bucket_prefix_listing"].items():
        lines.append(f"- {prefix}: listed_count={info.get('listed_count', 0)}")

    lines.extend(
        [
            "",
            "## Site link inventory",
            f"- Yandex media refs: {site['totals'].get('yandex_media', 0)}",
            f"- Supabase domain refs: {site['totals'].get('supabase_domain', 0)}",
            f"- site-media/videos refs: {site['totals'].get('site_media_videos', 0)}",
            f"- fetchListings refs: {site['totals'].get('fetch_listings', 0)}",
            f"- supabase client refs: {site['totals'].get('supabase_client', 0)}",
            "",
            "## Next step",
            "Stage 2: upload videos to Yandex, replace URLs in HTML/JS, update generators.",
            "",
            "## Notes",
            "- Archive JSON is not committed (large, contains catalog data).",
            "- Photo URLs in HTML already on Yandex; remaining Supabase refs are mostly videos.",
            "- listing_media.public_url still points to Supabase for all 2450 rows.",
        ]
    )

    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(REPORT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
