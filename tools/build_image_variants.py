#!/usr/bin/env python3
"""Generate WebP variants for local media images."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIRS = (
    ROOT / "media" / "cards",
    ROOT / "media" / "kvartira-cards",
)
WIDTHS = (480, 960, 1440)
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def iter_sources(paths: list[Path]) -> list[Path]:
    sources: list[Path] = []
    for path in paths:
        if not path.exists():
            continue
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS and not path.name.endswith(".webp"):
            sources.append(path)
            continue
        if path.is_dir():
            sources.extend(
                item
                for item in path.rglob("*")
                if item.is_file() and item.suffix.lower() in IMAGE_EXTENSIONS and not item.name.endswith(".webp")
            )
    return sorted(set(sources))


def variant_path(source: Path, width: int) -> Path:
    return source.with_name(f"{source.stem}-{width}.webp")


def build_variants_for_image(source: Path, *, quality: int, force: bool, dry_run: bool) -> tuple[int, int]:
    created = 0
    skipped = 0
    with Image.open(source) as original:
        image = ImageOps.exif_transpose(original).convert("RGB")
        for width in WIDTHS:
            if width > image.width:
                skipped += 1
                continue
            destination = variant_path(source, width)
            if destination.exists() and not force:
                skipped += 1
                continue
            created += 1
            if dry_run:
                continue
            ratio = width / image.width
            height = max(1, round(image.height * ratio))
            resized = image.resize((width, height), Image.Resampling.LANCZOS)
            resized.save(destination, "WEBP", quality=quality, method=6)
    return created, skipped


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", help="Files or directories to process")
    parser.add_argument("--quality", type=int, default=78)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    targets = [Path(path) if Path(path).is_absolute() else ROOT / path for path in args.paths]
    if not targets:
        targets = list(DEFAULT_DIRS)

    sources = iter_sources(targets)
    created = 0
    skipped = 0
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = [
            pool.submit(build_variants_for_image, source, quality=args.quality, force=args.force, dry_run=args.dry_run)
            for source in sources
        ]
        for future in as_completed(futures):
            image_created, image_skipped = future.result()
            created += image_created
            skipped += image_skipped

    print(
        f"sources={len(sources)} created={created} skipped={skipped} "
        f"quality={args.quality} dry_run={int(args.dry_run)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
