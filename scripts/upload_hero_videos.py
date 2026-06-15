#!/usr/bin/env python3
"""
Upload hero intro MP4s to Yandex Object Storage at media/videos/hero/...

Requires .env.yandex.local in repo root (see .env.yandex.example).

Usage:
  cd repo && python3 scripts/upload_hero_videos.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from yandex_storage import upload_file, yandex_public_url  # noqa: E402

FILES = (
    "darya-intro-vertical-low.mp4",
    "darya-intro-vertical-high.mp4",
)
OBJECT_PREFIX = "videos/hero"


def main() -> int:
    hero_dir = ROOT / "media" / "videos" / "hero"
    any_ok = False

    for name in FILES:
        path = hero_dir / name
        if not path.is_file():
            print(f"Skip (missing): {path}", file=sys.stderr)
            continue
        if path.stat().st_size < 5000:
            print(f"Skip (too small, likely Git LFS pointer): {path}", file=sys.stderr)
            continue

        storage_path = f"{OBJECT_PREFIX}/{name}"
        size_mb = path.stat().st_size / (1024 * 1024)
        print(f"Uploading {name} ({size_mb:.1f} MiB) …", flush=True)
        try:
            public = upload_file(path, storage_path, "video/mp4")
        except Exception as error:
            print(f"Failed {name}: {error}", file=sys.stderr)
            return 1
        print(f"OK: {public or yandex_public_url(storage_path)}", flush=True)
        any_ok = True

    return 0 if any_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
