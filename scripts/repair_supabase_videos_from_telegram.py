#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import re
import tempfile
from pathlib import Path
from typing import Any

import requests
from telethon import TelegramClient

from sync_catalog_from_telegram import (  # noqa: E402
    API_HASH,
    API_ID,
    ENV_FILE,
    MAX_VIDEO_UPLOAD_MB,
    SESSION,
    STORAGE_BUCKET,
    SupabaseClient,
    VIDEO_BITRATES,
    download_message_media,
    ensure_dir,
    transcode_video,
)

_POINTER_PREFIX = b"version https://git-lfs.github.com/spec/v1"
_POST_RE = re.compile(r"^([A-Za-z0-9_]+)/(\d+)$")
_TG_URL_RE = re.compile(r"t\.me/([^/?#]+)/(\d+)", re.I)
_STORAGE_PUBLIC_RE = re.compile(r"/storage/v1/object/public/[^/]+/(.+)$")


def load_env(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip()
    return data


def parse_telegram_post(media_row: dict[str, Any], listing_row: dict[str, Any] | None) -> str:
    details = media_row.get("details") or {}
    post = str(details.get("telegram_post") or "").strip()
    if _POST_RE.match(post):
        return post
    tg_url = str(details.get("telegram_url") or media_row.get("source_url") or "").strip()
    match = _TG_URL_RE.search(tg_url)
    if match:
        return f"{match.group(1)}/{match.group(2)}"
    if listing_row:
        channel = str(listing_row.get("source_channel") or "").strip()
        message_id = listing_row.get("source_message_id")
        if channel and message_id:
            return f"{channel}/{int(message_id)}"
    return ""


def parse_storage_path(media_row: dict[str, Any]) -> str:
    storage_path = str(media_row.get("storage_path") or "").strip()
    if storage_path:
        return storage_path
    source_url = str(media_row.get("source_url") or "").strip()
    match = _STORAGE_PUBLIC_RE.search(source_url)
    if not match:
        return ""
    return match.group(1)


def is_lfs_payload(url: str) -> bool:
    if not url:
        return False
    try:
        response = requests.get(url, headers={"Range": "bytes=0-80"}, timeout=25)
        response.raise_for_status()
        head = response.content[:80]
        return head.startswith(_POINTER_PREFIX)
    except Exception:
        return False


async def main() -> None:
    env = load_env(ENV_FILE)
    supa = SupabaseClient(url=env["SUPABASE_URL"].rstrip("/"), service_key=env["SUPABASE_SERVICE_ROLE_KEY"])

    listings = supa.fetch_listings()
    listings_by_id = {row["id"]: row for row in listings}

    media_rows = supa.request(
        "GET",
        "/rest/v1/listing_media",
        params={
            "select": "id,listing_id,media_role,mime_type,source_url,storage_path,public_url,details",
            "order": "id.asc",
            "limit": "10000",
        },
    ) or []

    candidates: list[dict[str, Any]] = []
    for row in media_rows:
        mime = str(row.get("mime_type") or "")
        role = str(row.get("media_role") or "")
        if role != "gallery":
            continue
        if "video" not in mime and mime != "application/x-telegram-embed":
            continue
        public_url = str(row.get("public_url") or row.get("source_url") or "").strip()
        if mime == "application/x-telegram-embed" or is_lfs_payload(public_url):
            candidates.append(row)

    print(f"Видео-кандидатов к восстановлению: {len(candidates)}", flush=True)
    if not candidates:
        return

    client = TelegramClient(SESSION, API_ID, API_HASH)
    await client.connect()
    entity_cache: dict[str, Any] = {}
    ok = 0
    failed = 0
    max_bytes = MAX_VIDEO_UPLOAD_MB * 1024 * 1024

    with tempfile.TemporaryDirectory(prefix="tg-video-repair-") as tmp_root:
        tmp_dir = Path(tmp_root)
        ensure_dir(tmp_dir)
        for idx, row in enumerate(candidates, start=1):
            listing = listings_by_id.get(row["listing_id"])
            post = parse_telegram_post(row, listing)
            storage_path = parse_storage_path(row)
            if not post or not storage_path:
                failed += 1
                print(f"[{idx}/{len(candidates)}] skip media#{row['id']}: нет post/storage_path", flush=True)
                continue
            channel, message_id_text = post.split("/", 1)
            try:
                message_id = int(message_id_text)
            except ValueError:
                failed += 1
                print(f"[{idx}/{len(candidates)}] skip media#{row['id']}: bad message id", flush=True)
                continue
            try:
                if channel not in entity_cache:
                    entity_cache[channel] = await client.get_entity(channel)
                message = await client.get_messages(entity_cache[channel], ids=message_id)
            except Exception as error:  # noqa: BLE001
                failed += 1
                print(f"[{idx}/{len(candidates)}] fail media#{row['id']}: telegram fetch error: {error}", flush=True)
                continue
            if not message or not message.media:
                failed += 1
                print(f"[{idx}/{len(candidates)}] fail media#{row['id']}: message has no media", flush=True)
                continue

            file_name = Path(storage_path).name
            local_file = tmp_dir / f"{row['id']}-{file_name}"
            downloaded = await download_message_media(client, message, local_file)
            if not downloaded or not Path(downloaded).exists():
                failed += 1
                print(f"[{idx}/{len(candidates)}] fail media#{row['id']}: download failed", flush=True)
                continue
            downloaded_path = Path(downloaded)
            if downloaded_path.suffix.lower() != ".mp4":
                target = downloaded_path.with_suffix(".mp4")
                try:
                    downloaded_path.rename(target)
                    downloaded_path = target
                except OSError:
                    pass
            uploaded_path: Path | None = None
            public_url = ""

            def try_upload(candidate: Path) -> bool:
                nonlocal public_url, uploaded_path
                if not candidate.exists() or candidate.stat().st_size <= 0:
                    return False
                if candidate.stat().st_size > max_bytes:
                    return False
                try:
                    public_url = supa.upload_file(candidate, storage_path, "video/mp4")
                except Exception:
                    return False
                uploaded_path = candidate
                return True

            if not try_upload(downloaded_path):
                for bitrate in VIDEO_BITRATES:
                    compressed = downloaded_path.with_name(f"{downloaded_path.stem}-{bitrate}.mp4")
                    if not compressed.exists() or compressed.stat().st_size == 0:
                        if not transcode_video(downloaded_path, compressed, bitrate):
                            continue
                    if try_upload(compressed):
                        break

            if not public_url:
                failed += 1
                print(f"[{idx}/{len(candidates)}] fail media#{row['id']}: upload error (all variants)", flush=True)
                continue

            details = dict(row.get("details") or {})
            details["telegram_post"] = post
            details["telegram_url"] = f"https://t.me/{post}"
            supa.request(
                "PATCH",
                "/rest/v1/listing_media",
                params={"id": f"eq.{row['id']}"},
                payload={
                    "mime_type": "video/mp4",
                    "source_url": public_url,
                    "public_url": public_url,
                    "storage_bucket": STORAGE_BUCKET,
                    "storage_path": storage_path,
                    "details": details,
                },
                extra_headers={"Prefer": "return=minimal"},
            )
            ok += 1
            used = uploaded_path or downloaded_path
            size_mb = used.stat().st_size / (1024 * 1024)
            print(f"[{idx}/{len(candidates)}] ok media#{row['id']} {storage_path} ({size_mb:.1f} MB)", flush=True)

    await client.disconnect()
    print({"ok": ok, "failed": failed, "total": len(candidates)}, flush=True)


if __name__ == "__main__":
    asyncio.run(main())
