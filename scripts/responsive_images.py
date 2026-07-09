"""Responsive image helpers for Yandex-hosted static media."""

from __future__ import annotations

import html
from pathlib import Path
from urllib.parse import unquote

from PIL import Image

from media_urls import YANDEX_MEDIA_BASE, yandex_photo_url

ROOT = Path(__file__).resolve().parents[1]
RESPONSIVE_WIDTHS = (480, 960, 1440)
RESPONSIVE_FOLDERS = ("cards/", "kvartira-cards/", "hotels/", "kvartira/")
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png")


def media_relative_path(url: str) -> str:
    raw = (url or "").strip().split("?", 1)[0]
    if not raw:
        return ""
    if raw.startswith(f"{YANDEX_MEDIA_BASE}/media/"):
        rel = raw[len(f"{YANDEX_MEDIA_BASE}/media/") :]
    elif raw.startswith("/media/"):
        rel = raw[len("/media/") :]
    elif raw.startswith("media/"):
        rel = raw[len("media/") :]
    else:
        return ""
    return unquote(rel).lstrip("/")


def is_responsive_candidate(url: str, *, folders: tuple[str, ...] = RESPONSIVE_FOLDERS) -> bool:
    rel = media_relative_path(url)
    lower = rel.lower()
    return bool(rel and lower.endswith(IMAGE_EXTENSIONS) and any(lower.startswith(folder) for folder in folders))


def variant_url(url: str, width: int) -> str:
    rel = media_relative_path(url)
    if not rel:
        return ""
    path = Path(rel)
    variant_rel = f"{path.with_suffix('')}-{width}.webp"
    return f"{YANDEX_MEDIA_BASE}/media/{variant_rel}"


def srcset_for_image(url: str, *, widths: tuple[int, ...] = RESPONSIVE_WIDTHS, root: Path = ROOT) -> str:
    src = yandex_photo_url(url)
    if not is_responsive_candidate(src):
        return ""
    dimensions = image_dimensions(src, root=root)
    if dimensions:
        widths = tuple(width for width in widths if width <= dimensions[0])
    if not widths:
        return ""
    return ", ".join(f"{variant_url(src, width)} {width}w" for width in widths)


def local_media_path(url: str, *, root: Path = ROOT) -> Path | None:
    rel = media_relative_path(url)
    if not rel:
        return None
    path = root / "media" / rel
    return path if path.is_file() else None


def image_dimensions(url: str, *, root: Path = ROOT) -> tuple[int, int] | None:
    path = local_media_path(url, root=root)
    if not path:
        return None
    try:
        with Image.open(path) as image:
            return image.size
    except OSError:
        return None


def responsive_image_attrs(
    src: str,
    *,
    sizes: str,
    root: Path = ROOT,
    include_dimensions: bool = True,
) -> dict[str, str]:
    attrs: dict[str, str] = {}
    srcset = srcset_for_image(src, root=root)
    if srcset:
        attrs["srcset"] = srcset
        attrs["sizes"] = sizes
    if include_dimensions:
        dimensions = image_dimensions(src, root=root)
        if dimensions:
            attrs["width"] = str(dimensions[0])
            attrs["height"] = str(dimensions[1])
    return attrs


def attrs_to_html(attrs: dict[str, str]) -> str:
    return "".join(f' {name}="{html.escape(value, quote=True)}"' for name, value in attrs.items() if value)


def responsive_img_html(src: str, alt: str, *, loading: str, sizes: str, root: Path = ROOT) -> str:
    escaped_src = html.escape(yandex_photo_url(src), quote=True)
    escaped_alt = html.escape(alt, quote=True)
    attrs = responsive_image_attrs(src, sizes=sizes, root=root)
    return f'<img src="{escaped_src}"{attrs_to_html(attrs)} alt="{escaped_alt}" loading="{html.escape(loading, quote=True)}" />'
