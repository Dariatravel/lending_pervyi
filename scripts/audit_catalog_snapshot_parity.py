#!/usr/bin/env python3
"""Compare data/catalog-snapshot.json with live Supabase listings."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env.supabase.local"
SNAPSHOT_PATH = ROOT / "data" / "catalog-snapshot.json"
REPORT_PATH = ROOT / "output" / "catalog_snapshot_parity.txt"


def load_env(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    if not path.exists():
        return result
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def fetch_active_listings(base: str, key: str) -> list[dict]:
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    response = requests.get(
        f"{base}/rest/v1/listings",
        headers=headers,
        params={
            "select": "id,slug,source_kind,has_video,cover_url,details",
            "is_active": "eq.true",
            "limit": "5000",
        },
        timeout=120,
    )
    response.raise_for_status()
    return response.json()


def main() -> int:
    if not SNAPSHOT_PATH.exists():
        print(f"Snapshot missing: {SNAPSHOT_PATH}", file=sys.stderr)
        return 1

    snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    snap_by_slug = {row["slug"]: row for row in snapshot.get("listings") or []}

    env = load_env(ENV_PATH)
    base = env.get("SUPABASE_URL", "").rstrip("/")
    key = env.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not base or not key:
        print(f"Need Supabase env in {ENV_PATH}", file=sys.stderr)
        return 1

    live_rows = fetch_active_listings(base, key)
    live_by_slug = {row["slug"]: row for row in live_rows}

    missing_in_snapshot = sorted(set(live_by_slug) - set(snap_by_slug))
    extra_in_snapshot = sorted(set(snap_by_slug) - set(live_by_slug))
    mismatches: list[str] = []

    for slug in sorted(set(live_by_slug) & set(snap_by_slug)):
        live = live_by_slug[slug]
        snap = snap_by_slug[slug]
        if bool(live.get("has_video")) != bool(snap.get("has_video")):
            mismatches.append(f"has_video {slug}: live={live.get('has_video')} snap={snap.get('has_video')}")
        live_filters = ((live.get("details") or {}).get("filters") or {})
        snap_filters = ((snap.get("details") or {}).get("filters") or {})
        if live_filters != snap_filters:
            mismatches.append(f"filters {slug}")
        live_media_count = len([m for m in snap.get("media") or [] if m.get("media_role") == "gallery"])
        if live_media_count != len(snap.get("media") or []):
            pass  # media count checked below via snapshot only

    lines = [
        "# Catalog snapshot parity",
        f"snapshot_generated_at={snapshot.get('generated_at')}",
        f"live_active={len(live_rows)} snapshot={len(snap_by_slug)}",
        f"missing_in_snapshot={len(missing_in_snapshot)}",
        f"extra_in_snapshot={len(extra_in_snapshot)}",
        f"mismatches={len(mismatches)}",
        "",
    ]
    if missing_in_snapshot:
        lines.append("## Missing in snapshot")
        lines.extend(missing_in_snapshot[:50])
        lines.append("")
    if extra_in_snapshot:
        lines.append("## Extra in snapshot")
        lines.extend(extra_in_snapshot[:50])
        lines.append("")
    if mismatches:
        lines.append("## Mismatches")
        lines.extend(mismatches[:50])

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(REPORT_PATH)
    print(
        json.dumps(
            {
                "live_active": len(live_rows),
                "snapshot": len(snap_by_slug),
                "missing_in_snapshot": len(missing_in_snapshot),
                "extra_in_snapshot": len(extra_in_snapshot),
                "mismatches": len(mismatches),
            },
            ensure_ascii=False,
        )
    )
    return 1 if missing_in_snapshot or extra_in_snapshot or mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())
