#!/usr/bin/env python3
"""Rebuild catalog HTML from data/catalog-snapshot.json without Supabase API."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from rebuild_from_supabase import rebuild_catalog  # noqa: E402

SNAPSHOT_PATH = ROOT / "data" / "catalog-snapshot.json"


def load_snapshot_rows() -> list[dict[str, Any]]:
    if not SNAPSHOT_PATH.exists():
        raise FileNotFoundError(f"Snapshot not found: {SNAPSHOT_PATH}")
    payload = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    rows = payload.get("listings") or []
    if not rows:
        raise RuntimeError("Snapshot has no listings")
    return rows


def main() -> int:
    rows = load_snapshot_rows()
    rebuild_catalog(rows)
    print(f"snapshot={SNAPSHOT_PATH.name} generated_at={json.loads(SNAPSHOT_PATH.read_text(encoding='utf-8')).get('generated_at')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
