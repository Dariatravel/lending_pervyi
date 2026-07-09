#!/usr/bin/env python3
"""Add responsive image attributes to existing generated HTML files."""

from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from media_urls import yandex_photo_url  # noqa: E402
from responsive_images import is_responsive_candidate, responsive_image_attrs  # noqa: E402

IMG_TAG_RE = re.compile(r"<img\b[^>]*>", re.I)


def normalize_attr_value(value: Any) -> str:
    if isinstance(value, list):
        return " ".join(str(item) for item in value)
    if value is True:
        return ""
    return str(value)


def render_img_tag(attrs: dict[str, Any]) -> str:
    ordered: list[tuple[str, str]] = []
    for name in ("src", "srcset", "sizes", "width", "height", "alt", "loading"):
        if name in attrs:
            ordered.append((name, normalize_attr_value(attrs.pop(name))))
    ordered.extend((name, normalize_attr_value(value)) for name, value in attrs.items())
    rendered = " ".join(
        name if value == "" else f'{name}="{html.escape(value, quote=True)}"'
        for name, value in ordered
        if value is not None
    )
    return f"<img {rendered} />"


def update_img_tag(tag: str, *, folders: tuple[str, ...], sizes: str) -> str:
    soup = BeautifulSoup(tag, "html.parser")
    img = soup.find("img")
    if not img:
        return tag
    src = normalize_attr_value(img.get("src") or "")
    if not src:
        return tag
    yandex_src = yandex_photo_url(src)
    if not is_responsive_candidate(yandex_src, folders=folders):
        return tag
    responsive_attrs = responsive_image_attrs(yandex_src, sizes=sizes, root=ROOT)
    if not responsive_attrs.get("srcset"):
        return tag
    attrs = dict(img.attrs)
    attrs["src"] = yandex_src
    attrs.update(responsive_attrs)
    if "loading" not in attrs:
        attrs["loading"] = "lazy"
    return render_img_tag(attrs)


def update_file(path: Path, *, folders: tuple[str, ...], sizes: str) -> bool:
    text = path.read_text(encoding="utf-8")
    changed = False

    def replace(match: re.Match[str]) -> str:
        nonlocal changed
        original = match.group(0)
        updated = update_img_tag(original, folders=folders, sizes=sizes)
        if updated != original:
            changed = True
        return updated

    updated_text = IMG_TAG_RE.sub(replace, text)
    if changed:
        path.write_text(updated_text, encoding="utf-8")
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", default=["hotels"], help="HTML files or directories")
    parser.add_argument("--folder", action="append", dest="folders", default=["hotels/"])
    parser.add_argument("--sizes", default="(max-width: 720px) 92vw, (max-width: 1180px) 45vw, 520px")
    args = parser.parse_args()

    targets = [Path(path) if Path(path).is_absolute() else ROOT / path for path in args.paths]
    files: list[Path] = []
    for target in targets:
        if target.is_file() and target.suffix.lower() == ".html":
            files.append(target)
        elif target.is_dir():
            files.extend(target.rglob("*.html"))

    changed = 0
    folders = tuple(args.folders)
    for path in sorted(set(files)):
        if update_file(path, folders=folders, sizes=args.sizes):
            changed += 1
    print(f"files={len(set(files))} changed={changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
