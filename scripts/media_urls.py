"""Photo and video URLs for site HTML: Yandex Object Storage."""

from __future__ import annotations

from urllib.parse import unquote

YANDEX_MEDIA_BASE = "https://storage.yandexcloud.net/abhazbereg-media"
STORAGE_PUBLIC_MARKER = "/storage/v1/object/public/site-media/"
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".gif")
VIDEO_EXTENSIONS = (".mp4", ".webm", ".mov", ".m4v")


def _strip_query(url: str) -> str:
    return (url or "").split("?", 1)[0]


def _media_relative_path(url: str, *, video: bool = False) -> str | None:
    raw = (url or "").strip()
    if not raw:
        return None
    extensions = VIDEO_EXTENSIONS if video else IMAGE_EXTENSIONS
    if STORAGE_PUBLIC_MARKER in raw:
        relative = raw.split(STORAGE_PUBLIC_MARKER, 1)[1].split("?", 1)[0]
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
    if not relative.lower().endswith(extensions):
        return None
    return relative


def yandex_photo_url(url: str) -> str:
    """Return absolute Yandex URL for a photo; pass through non-image URLs."""
    raw = (url or "").strip()
    if not raw:
        return raw
    if raw.startswith(("http://", "https://")) and STORAGE_PUBLIC_MARKER not in raw:
        if raw.startswith(f"{YANDEX_MEDIA_BASE}/"):
            return _strip_query(raw)
        if _media_relative_path(raw) is None:
            return raw
    relative = _media_relative_path(raw)
    if relative is not None:
        return f"{YANDEX_MEDIA_BASE}/media/{relative}"
    return raw


def yandex_video_url(url: str) -> str:
    """Return absolute Yandex URL for a video; pass through non-video URLs."""
    raw = (url or "").strip()
    if not raw:
        return raw
    if raw.startswith(("http://", "https://")) and STORAGE_PUBLIC_MARKER not in raw:
        if raw.startswith(f"{YANDEX_MEDIA_BASE}/"):
            return _strip_query(raw)
        if _media_relative_path(raw, video=True) is None:
            return raw
    relative = _media_relative_path(raw, video=True)
    if relative is not None:
        return f"{YANDEX_MEDIA_BASE}/media/{relative}"
    return raw


def to_yandex_media_url(url: str) -> str:
    """Map photo or video path/URL to Yandex Object Storage."""
    raw = (url or "").strip()
    if not raw:
        return raw
    lower = _strip_query(raw).lower()
    if lower.endswith(VIDEO_EXTENSIONS):
        return yandex_video_url(raw)
    if lower.endswith(IMAGE_EXTENSIONS):
        return yandex_photo_url(raw)
    return raw


def media_src_for_html(url: str, *, mime_type: str = "") -> str:
    """Pick Yandex URL helper for HTML img/video src."""
    mime = (mime_type or "").lower()
    if mime.startswith("video/"):
        return yandex_video_url(url)
    if mime.startswith("image/"):
        return yandex_photo_url(url)
    return to_yandex_media_url(url)
