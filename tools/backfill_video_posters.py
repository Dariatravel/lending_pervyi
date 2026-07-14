#!/usr/bin/env python3
"""Дозаливка кадров-обложек (-poster.jpg) для всех видео сайта.

Видео, залитые до появления автогенерации постеров (июль 2026), играют без
обложки: до нажатия ▶ плитка тёмная. Инструмент проходит по каталогу и по
блокам «Дополнительные обзоры», для каждого видео без постера вытягивает
кадр ffmpeg'ом прямо из бакета (по HTTPS, качается только начало файла),
заливает `<имя>-poster.jpg` рядом с видео и прописывает постер в данные:
- каталог: details.poster_url в data/catalog-snapshot.json;
- блоки обзоров: атрибут poster= в section_html (data/supplemental-blocks.json).

После инструмента страницы нужно пересобрать
(scripts/rebuild_from_catalog_snapshot.py) — workflow делает это сам.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from media_urls import YANDEX_MEDIA_BASE  # noqa: E402
from yandex_storage import _s3_client, load_yandex_env, upload_file, yandex_object_key, yandex_public_url  # noqa: E402

SNAPSHOT_PATH = ROOT / "data" / "catalog-snapshot.json"
MANIFEST_PATH = ROOT / "data" / "supplemental-blocks.json"
MEDIA_PREFIX = f"{YANDEX_MEDIA_BASE}/media/"

FFMPEG = shutil.which("ffmpeg")

created = 0
reused = 0
failed: list[str] = []


def poster_storage_path(video_storage_path: str) -> str:
    stem, _, _ = video_storage_path.rpartition(".")
    return f"{stem or video_storage_path}-poster.jpg"


def storage_path_from_url(url: str) -> str | None:
    if not url.startswith(MEDIA_PREFIX):
        return None
    return url[len(MEDIA_PREFIX):].split("?", 1)[0]


def object_exists(s3, bucket: str, storage_path: str) -> bool:
    try:
        s3.head_object(Bucket=bucket, Key=yandex_object_key(storage_path))
        return True
    except Exception:  # noqa: BLE001
        return False


def make_poster(video_url: str, poster_path: str, s3, bucket: str) -> str:
    """Вернуть публичный URL постера (создав его при необходимости), '' при неудаче."""
    global created, reused
    if object_exists(s3, bucket, poster_path):
        reused += 1
        return yandex_public_url(poster_path)
    if not FFMPEG:
        failed.append(f"{poster_path}: нет ffmpeg")
        return ""
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        for seek in ("1", "0"):
            proc = subprocess.run(
                [FFMPEG, "-y", "-ss", seek, "-i", video_url, "-frames:v", "1", "-q:v", "4", str(tmp_path)],
                capture_output=True, timeout=240, check=False,
            )
            if proc.returncode == 0 and tmp_path.exists() and tmp_path.stat().st_size > 0:
                url = upload_file(tmp_path, poster_path, "image/jpeg")
                created += 1
                print(f"[ok] {poster_path}")
                return url
        failed.append(f"{poster_path}: ffmpeg не смог достать кадр")
        return ""
    except Exception as error:  # noqa: BLE001
        failed.append(f"{poster_path}: {error}")
        return ""
    finally:
        tmp_path.unlink(missing_ok=True)


def process_snapshot(s3, bucket: str) -> bool:
    from catalog_snapshot import save_listings

    data = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    listings = data["listings"]
    changed = False
    for row in listings:
        if row.get("is_active") is False:
            continue
        for media in row.get("media") or []:
            mime = str(media.get("mime_type") or "")
            if not mime.startswith("video/"):
                continue
            details = media.get("details")
            if not isinstance(details, dict):
                details = {}
                media["details"] = details
            if str(details.get("poster_url") or "").startswith("http"):
                continue
            url = str(media.get("public_url") or media.get("source_url") or "")
            storage_path = str(media.get("storage_path") or "") or storage_path_from_url(url)
            if not storage_path or not url.startswith("http"):
                continue
            poster_url = make_poster(url, poster_storage_path(storage_path), s3, bucket)
            if poster_url:
                details["poster_url"] = poster_url
                changed = True
    if changed:
        save_listings(listings)
    return changed


VIDEO_TAG_RE = re.compile(r"<video\b[^>]*>\s*<source\s+src=\"([^\"]+\.mp4)\"[^>]*/?>", re.I)


def process_supplemental(s3, bucket: str) -> bool:
    try:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    if not isinstance(manifest, dict):
        return False
    changed = False
    for slug, section in manifest.items():
        if not isinstance(section, dict):
            continue
        html = str(section.get("section_html") or "")
        if "<video" not in html:
            continue

        def add_poster(match: re.Match) -> str:
            nonlocal changed
            tag = match.group(0)
            video_url = match.group(1)
            if "poster=" in tag.split(">", 1)[0]:
                return tag
            storage_path = storage_path_from_url(video_url)
            if not storage_path:
                return tag
            poster_url = make_poster(video_url, poster_storage_path(storage_path), s3, bucket)
            if not poster_url:
                return tag
            changed = True
            head, rest = tag.split(">", 1)
            return f'{head} poster="{poster_url}">{rest}'

        new_html = VIDEO_TAG_RE.sub(add_poster, html)
        if new_html != html:
            section["section_html"] = new_html
    if changed:
        MANIFEST_PATH.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=1, sort_keys=True),
            encoding="utf-8",
        )
    return changed


def main() -> int:
    load_yandex_env()
    import os

    bucket = os.environ.get("YANDEX_S3_BUCKET", "abhazbereg-media")
    s3 = _s3_client()
    snap_changed = process_snapshot(s3, bucket)
    supp_changed = process_supplemental(s3, bucket)
    print(
        f"posters: created={created} reused={reused} failed={len(failed)} "
        f"snapshot_changed={snap_changed} supplemental_changed={supp_changed}"
    )
    for item in failed[:30]:
        print(f"[warn] {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
