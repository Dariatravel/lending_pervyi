"""Photo URLs for site HTML: Yandex Object Storage. Videos stay on Supabase."""

from __future__ import annotations

from urllib.parse import unquote

YANDEX_MEDIA_BASE = "https://storage.yandexcloud.net/abhazbereg-media"
STORAGE_PUBLIC_IMAGE_MARKER = "/storage/v1/object/public/site-media/"
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".gif")


def _media_relative_path(url: str) -> str | None:
    raw = (url or "").strip()
    if not raw:
        return None
    if STORAGE_PUBLIC_IMAGE_MARKER in raw:
        relative = raw.split(STORAGE_PUBLIC_IMAGE_MARKER, 1)[1].split("?", 1)[0]
    elif raw.startswith(f"{YANDEX_MEDIA_BASE}/media/"):
        relative = raw[len(f"{YANDEX_MEDIA_BASE}/media/") :].split("?", 1)[0]
    elif raw.startswith("/media/"):
        relative = raw[len("/media/") :].split("?", 1)[0]
    elif raw.startswith("media/"):
        relative = raw[len("media/") :].split("?", 1)[0]
    else:
        for prefix in ("../../media/", "../media/", "./media/"):
            if raw.startswith(prefix):
                relative = raw[len(prefix) :].split("?", 1)[0]
                break
        else:
            return None
    relative = unquote(relative)
    if not relative.lower().endswith(IMAGE_EXTENSIONS):
        return None
    return relative


def yandex_photo_url(url: str) -> str:
    """Return absolute Yandex URL for a photo; pass through non-image and video URLs."""
    raw = (url or "").strip()
    if not raw:
        return raw
    if raw.startswith(("http://", "https://")) and STORAGE_PUBLIC_IMAGE_MARKER not in raw:
        if raw.startswith(f"{YANDEX_MEDIA_BASE}/"):
            return raw
        if _media_relative_path(raw) is None:
            return raw
    relative = _media_relative_path(raw)
    if relative is not None:
        return f"{YANDEX_MEDIA_BASE}/media/{relative}"
    return raw
