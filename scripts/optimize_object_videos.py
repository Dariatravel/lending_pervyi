#!/usr/bin/env python3
"""Create lightweight object videos, upload them to Supabase Storage, and relink pages.

This script is intentionally narrow: it changes only MP4 URLs / Telegram embed blocks in
object pages. It does not touch layout, CSS, text blocks, filters, or card structure.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable
from urllib.parse import quote, urlparse

import requests

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env.supabase.local"
BUCKET_DEFAULT = "site-media"
POST_MAX_BYTES = 40 * 1024 * 1024
MIN_REAL_VIDEO_BYTES = 5000
VIDEO_MAX_WIDTH = 720
VIDEO_BITRATE = "1200k"
VIDEO_MAXRATE = "1800k"
VIDEO_AUDIO_BITRATE = "64k"

PAGE_GLOBS = ("hotels/*/index.html", "kvartira/*/index.html")
SOURCE_RE = re.compile(r'(<source\b[^>]*\bsrc=")([^"]+\.mp4)("[^>]*>)', re.I)
VIDEO_BLOCK_RE = re.compile(r'<video\b[^>]*>.*?</video>', re.I | re.S)
TELEGRAM_EMBED_RE = re.compile(
    r'<div class="video-embed video-embed--telegram">\s*'
    r'<script async src="https://telegram\.org/js/telegram-widget\.js\?\d+"[^>]*data-telegram-post="([^"]+)"[^>]*></script>\s*'
    r'</div>',
    re.I | re.S,
)


def load_env_file(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.exists():
        return data
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def resolve_ffmpeg() -> str:
    candidates = [
        os.environ.get("FFMPEG_BIN", ""),
        "/Users/darya_botova/Library/Python/3.9/lib/python/site-packages/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1",
        "/opt/homebrew/bin/ffmpeg",
        "/usr/local/bin/ffmpeg",
        "ffmpeg",
    ]
    for candidate in candidates:
        if not candidate:
            continue
        if candidate == "ffmpeg":
            try:
                subprocess.run([candidate, "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                return candidate
            except Exception:
                continue
        path = Path(candidate)
        if path.exists() and os.access(path, os.X_OK):
            return str(path)
    raise RuntimeError("ffmpeg не найден")


def ensure_env() -> tuple[str, str, str]:
    for k, v in load_env_file(ENV_FILE).items():
        os.environ.setdefault(k, v)
    base = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or ""
    bucket = os.environ.get("SUPABASE_STORAGE_BUCKET") or BUCKET_DEFAULT
    if not base or not key:
        raise RuntimeError(f"Нужны SUPABASE_URL и SUPABASE_SERVICE_ROLE_KEY в {ENV_FILE}")
    return base, key, bucket


def kind_for_page(page: Path) -> str:
    if page.parts[-3] == "hotels":
        return "hotels"
    if page.parts[-3] == "kvartira":
        return "kvartira"
    raise ValueError(f"Неизвестный тип страницы: {page}")


def slug_for_page(page: Path) -> str:
    return page.parts[-2]


def media_kind_dir(kind: str) -> str:
    return "hotels" if kind == "hotels" else "kvartira"


def storage_path_for(kind: str, slug: str, filename: str) -> str:
    return f"videos/{media_kind_dir(kind)}/{slug}/{filename}"


def public_url(base: str, bucket: str, storage_path: str) -> str:
    encoded = "/".join(quote(part) for part in storage_path.split("/"))
    return f"{base}/storage/v1/object/public/{bucket}/{encoded}"


def source_local_path(kind: str, slug: str, source_url: str | None = None) -> Path | None:
    d = ROOT / "media" / "videos" / media_kind_dir(kind) / slug
    if not d.exists():
        return None
    if source_url:
        name = Path(urlparse(source_url).path).name
        candidate = d / name
        if candidate.exists() and candidate.stat().st_size >= MIN_REAL_VIDEO_BYTES:
            return candidate
    for name in ("video-01-source.mp4", "video-1-source.mp4"):
        candidate = d / name
        if candidate.exists() and candidate.stat().st_size >= MIN_REAL_VIDEO_BYTES:
            return candidate
    candidates = [p for p in sorted(d.glob("*.mp4")) if p.stat().st_size >= MIN_REAL_VIDEO_BYTES and "source" in p.name]
    if candidates:
        return candidates[0]
    candidates = [p for p in sorted(d.glob("*.mp4")) if p.stat().st_size >= MIN_REAL_VIDEO_BYTES]
    return candidates[0] if candidates else None


def transcode(ffmpeg: str, source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp.mp4")
    if tmp.exists():
        tmp.unlink()
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(source),
        "-vf",
        f"scale='min({VIDEO_MAX_WIDTH},iw)':-2",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-b:v",
        VIDEO_BITRATE,
        "-maxrate",
        VIDEO_MAXRATE,
        "-bufsize",
        "3600k",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        "-c:a",
        "aac",
        "-b:a",
        VIDEO_AUDIO_BITRATE,
        str(tmp),
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr[-1200:])
    tmp.replace(target)


def upload_post(session: requests.Session, base: str, bucket: str, local_path: Path, storage_path: str) -> str:
    encoded = "/".join(quote(part) for part in storage_path.split("/"))
    url = f"{base}/storage/v1/object/{bucket}/{encoded}"
    with local_path.open("rb") as f:
        response = session.post(
            url,
            data=f,
            headers={
                "Content-Type": "video/mp4",
                "Cache-Control": "public, max-age=31536000, immutable",
                "x-upsert": "true",
            },
            timeout=(60, 3600),
        )
    response.raise_for_status()
    return public_url(base, bucket, storage_path)


def upload_tus(base: str, key: str, bucket: str, local_path: Path, storage_path: str) -> str:
    try:
        from tusclient import client as tus_client
    except ImportError as error:
        raise RuntimeError("Для большого видео нужен tusclient: python3 -m pip install tusclient") from error
    match = re.match(r"https://([^.]+)\.supabase\.co/?$", base)
    if not match:
        raise RuntimeError(f"Неожиданный SUPABASE_URL: {base}")
    endpoint = f"https://{match.group(1)}.storage.supabase.co/storage/v1/upload/resumable"
    tus = tus_client.TusClient(
        endpoint,
        headers={"Authorization": f"Bearer {key}", "apikey": key, "x-upsert": "true"},
    )
    with local_path.open("rb") as fs:
        uploader = tus.uploader(
            file_stream=fs,
            chunk_size=6 * 1024 * 1024,
            metadata={
                "bucketName": bucket,
                "objectName": storage_path,
                "contentType": "video/mp4",
                "cacheControl": "31536000",
            },
        )
        uploader.upload()
    return public_url(base, bucket, storage_path)


def upload_video(session: requests.Session, base: str, key: str, bucket: str, local_path: Path, storage_path: str) -> str:
    if local_path.stat().st_size <= POST_MAX_BYTES:
        return upload_post(session, base, bucket, local_path, storage_path)
    return upload_tus(base, key, bucket, local_path, storage_path)


@dataclass
class ReportRow:
    page: str
    kind: str
    slug: str
    status: str
    old_url: str
    new_url: str
    source_file: str
    optimized_file: str
    source_mb: float
    optimized_mb: float
    note: str = ""


def pages() -> Iterable[Path]:
    for pattern in PAGE_GLOBS:
        yield from sorted(ROOT.glob(pattern))


def replace_telegram_embed(text: str, video_url: str) -> str:
    html = (
        '<div class="video-embed video-embed--local">\n'
        '              <video class="local-video" controls preload="none" playsinline webkit-playsinline>\n'
        f'                <source src="{video_url}" type="video/mp4" />\n'
        '              </video>\n'
        '            </div>'
    )
    return TELEGRAM_EMBED_RE.sub(html, text)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--slug")
    parser.add_argument("--skip-upload", action="store_true")
    args = parser.parse_args()

    base, key, bucket = ensure_env()
    ffmpeg = resolve_ffmpeg()
    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {key}", "apikey": key})

    rows: list[ReportRow] = []
    changed_pages = 0
    processed = 0

    for page in pages():
        kind = kind_for_page(page)
        slug = slug_for_page(page)
        if args.slug and slug != args.slug:
            continue
        text = page.read_text(encoding="utf-8", errors="ignore")
        has_embed = bool(TELEGRAM_EMBED_RE.search(text))
        matches = list(SOURCE_RE.finditer(text))
        source_matches = [m for m in matches if "source.mp4" in m.group(2)]
        optimized_matches = [m for m in matches if "1800k.mp4" in m.group(2)]
        if not has_embed and not source_matches and not optimized_matches:
            continue
        if args.limit and processed >= args.limit:
            break

        old_url = source_matches[0].group(2) if source_matches else (optimized_matches[0].group(2) if optimized_matches else "telegram-embed")
        src = source_local_path(kind, slug, old_url if source_matches else None)
        if not src:
            rows.append(ReportRow(str(page.relative_to(ROOT)), kind, slug, "missing-source", old_url, "", "", "", 0, 0, "нет локального исходника"))
            continue

        optimized = src.parent / "video-01-1800k.mp4"
        try:
            if not optimized.exists() or optimized.stat().st_size < MIN_REAL_VIDEO_BYTES:
                if not args.dry_run:
                    transcode(ffmpeg, src, optimized)
            # Some Telegram videos are already tiny. Do not replace a small source
            # with a larger transcode just because the filename says 1800k.
            if (
                not args.dry_run
                and optimized.exists()
                and src.stat().st_size <= 15 * 1024 * 1024
                and optimized.stat().st_size > src.stat().st_size * 1.1
            ):
                shutil.copy2(src, optimized)
        except Exception as error:  # noqa: BLE001
            rows.append(
                ReportRow(
                    str(page.relative_to(ROOT)),
                    kind,
                    slug,
                    "transcode-error",
                    old_url,
                    "",
                    str(src.relative_to(ROOT)),
                    str(optimized.relative_to(ROOT)),
                    round(src.stat().st_size / (1024 * 1024), 2),
                    round(optimized.stat().st_size / (1024 * 1024), 2) if optimized.exists() else 0,
                    str(error).replace("\n", " ")[:500],
                )
            )
            processed += 1
            print(f"[{processed}] {slug}: transcode error", flush=True)
            continue

        storage_path = storage_path_for(kind, slug, optimized.name)
        new_url = public_url(base, bucket, storage_path)
        try:
            if not args.skip_upload and not args.dry_run:
                # Upsert even if the object exists: this fixes stale/pointer uploads and keeps paths canonical.
                new_url = upload_video(session, base, key, bucket, optimized, storage_path)
        except Exception as error:  # noqa: BLE001
            rows.append(
                ReportRow(
                    str(page.relative_to(ROOT)),
                    kind,
                    slug,
                    "upload-error",
                    old_url,
                    new_url,
                    str(src.relative_to(ROOT)),
                    str(optimized.relative_to(ROOT)),
                    round(src.stat().st_size / (1024 * 1024), 2),
                    round(optimized.stat().st_size / (1024 * 1024), 2) if optimized.exists() else 0,
                    str(error).replace("\n", " ")[:500],
                )
            )
            processed += 1
            print(f"[{processed}] {slug}: upload error", flush=True)
            continue

        new_text = text
        for m in source_matches:
            new_text = new_text.replace(m.group(2), new_url)
        if has_embed:
            new_text = replace_telegram_embed(new_text, new_url)

        if new_text != text:
            changed_pages += 1
            if not args.dry_run:
                page.write_text(new_text, encoding="utf-8")

        rows.append(
            ReportRow(
                str(page.relative_to(ROOT)),
                kind,
                slug,
                "dry-run" if args.dry_run else "updated",
                old_url,
                new_url,
                str(src.relative_to(ROOT)),
                str(optimized.relative_to(ROOT)),
                round(src.stat().st_size / (1024 * 1024), 2),
                round(optimized.stat().st_size / (1024 * 1024), 2) if optimized.exists() else 0,
                "telegram embed replaced" if has_embed else "source url replaced",
            )
        )
        processed += 1
        print(f"[{processed}] {slug}: {rows[-1].source_mb} MB -> {rows[-1].optimized_mb} MB", flush=True)

    out_dir = ROOT / "output"
    out_dir.mkdir(exist_ok=True)
    json_path = out_dir / "object_video_optimization_report.json"
    csv_path = out_dir / "object_video_optimization_report.csv"
    if not args.dry_run:
        json_path.write_text(json.dumps([asdict(r) for r in rows], ensure_ascii=False, indent=2), encoding="utf-8")
        with csv_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(asdict(rows[0]).keys()) if rows else list(ReportRow.__annotations__.keys()))
            writer.writeheader()
            for r in rows:
                writer.writerow(asdict(r))

    print(json.dumps({"processed": processed, "changed_pages": changed_pages, "report_rows": len(rows)}, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
