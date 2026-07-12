"""Генерация адаптивных WebP-вариантов (-480/-960/-1440) для фото.

Страницы ссылаются на варианты через srcset (scripts/responsive_images.py),
поэтому каждый загружаемый JPG обязан приезжать в бакет вместе с вариантами:
битый кандидат в srcset не откатывается на src, и фото «пропадает».
Используется синком (при заливке) и tools/backfill_image_variants.py (дозаливка).
"""

from __future__ import annotations

import io
from pathlib import Path

RESPONSIVE_WIDTHS = (480, 960, 1440)
WEBP_QUALITY = 78


def variant_key(storage_path: str, width: int) -> str:
    stem, _, _ = storage_path.rpartition('.')
    return f"{stem or storage_path}-{width}.webp"


def build_webp_variants(jpeg_bytes: bytes, *, widths: tuple[int, ...] = RESPONSIVE_WIDTHS) -> list[tuple[int, bytes]]:
    """Вернуть [(width, webp_bytes), ...] для ширин, не превышающих оригинал."""
    from PIL import Image

    with Image.open(io.BytesIO(jpeg_bytes)) as im:
        im = im.convert("RGB")
        source_width = im.width
        out: list[tuple[int, bytes]] = []
        for width in widths:
            if width > source_width:
                continue
            ratio = width / float(source_width)
            resized = im.resize((width, max(1, round(im.height * ratio))), Image.LANCZOS)
            buf = io.BytesIO()
            resized.save(buf, format="WEBP", quality=WEBP_QUALITY, method=4)
            out.append((width, buf.getvalue()))
        return out


def build_webp_variants_for_file(local_path: Path, **kwargs) -> list[tuple[int, bytes]]:
    return build_webp_variants(Path(local_path).read_bytes(), **kwargs)
