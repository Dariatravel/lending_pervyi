from __future__ import annotations

import asyncio
import argparse
import re
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
    storage_kind_prefix,
    transcode_video,
)

ROOT = Path.cwd()
VIDEOS_DIR = ROOT / 'media' / 'videos'


def load_env(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        data[key.strip()] = value.strip()
    return data


def parse_telegram_post(row: dict[str, Any]) -> str:
    details = row.get('details') or {}
    post = str(details.get('telegram_post') or '').strip()
    if post and '/' in post:
        return post
    source = str(row.get('source_url') or '').strip()
    match = re.search(r't\.me/([^/?#]+)/(\d+)', source)
    if match:
        return f'{match.group(1)}/{match.group(2)}'
    return ''


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument('--slug', help='Обработать только один объект по slug')
    parser.add_argument('--limit', type=int, default=0, help='Ограничить число видео за запуск')
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    env = load_env(ENV_FILE)
    supa = SupabaseClient(url=env['SUPABASE_URL'].rstrip('/'), service_key=env['SUPABASE_SERVICE_ROLE_KEY'])

    listings = supa.fetch_listings()
    listing_map = {row['id']: row for row in listings}

    media_rows = supa.request(
        'GET',
        '/rest/v1/listing_media',
        params={
            'select': 'id,listing_id,mime_type,source_url,storage_path,public_url,details',
            'mime_type': 'eq.application/x-telegram-embed',
            'order': 'id.asc',
            'limit': '10000',
        },
    ) or []

    if args.slug:
        listing_ids = {row['id'] for row in listings if row.get('slug') == args.slug}
        media_rows = [row for row in media_rows if row.get('listing_id') in listing_ids]

    if args.limit and args.limit > 0:
        media_rows = media_rows[: args.limit]

    if not media_rows:
        print('Нет Telegram-embed видео для миграции.')
        return

    print(f'К миграции видео: {len(media_rows)}', flush=True)

    client = TelegramClient(SESSION, API_ID, API_HASH)
    await client.connect()

    max_bytes = MAX_VIDEO_UPLOAD_MB * 1024 * 1024
    entity_cache: dict[str, Any] = {}
    converted = 0
    failed = 0

    for index, media in enumerate(media_rows, start=1):
        listing = listing_map.get(media['listing_id'])
        if not listing:
            failed += 1
            print(f'[{index}/{len(media_rows)}] skip media#{media["id"]}: listing not found', flush=True)
            continue

        post = parse_telegram_post(media)
        if not post:
            failed += 1
            print(f'[{index}/{len(media_rows)}] skip media#{media["id"]}: telegram_post empty', flush=True)
            continue

        channel, message_id_text = post.split('/', 1)
        try:
            message_id = int(message_id_text)
        except ValueError:
            failed += 1
            print(f'[{index}/{len(media_rows)}] skip media#{media["id"]}: bad message id', flush=True)
            continue

        try:
            if channel not in entity_cache:
                entity_cache[channel] = await client.get_entity(channel)
            message = await client.get_messages(entity_cache[channel], ids=message_id)
        except Exception as error:  # noqa: BLE001
            failed += 1
            print(f'[{index}/{len(media_rows)}] fail media#{media["id"]}: telegram fetch error: {error}', flush=True)
            continue

        if not message or not message.media:
            failed += 1
            print(f'[{index}/{len(media_rows)}] fail media#{media["id"]}: no media in message', flush=True)
            continue

        slug = listing['slug']
        source_kind = listing['source_kind']
        video_dir = VIDEOS_DIR / storage_kind_prefix(source_kind) / slug
        ensure_dir(video_dir)
        source_file = video_dir / f'video-{media["id"]}-source.mp4'

        downloaded = await download_message_media(client, message, source_file)
        if not downloaded:
            failed += 1
            print(f'[{index}/{len(media_rows)}] fail media#{media["id"]}: download failed', flush=True)
            continue
        if downloaded != source_file:
            downloaded.rename(source_file)

        uploaded_public_url = ''
        uploaded_storage_path = ''
        uploaded_file: Path | None = None

        def try_upload(candidate: Path) -> bool:
            nonlocal uploaded_public_url, uploaded_storage_path, uploaded_file
            if not candidate.exists() or candidate.stat().st_size <= 0:
                return False
            if candidate.stat().st_size > max_bytes:
                return False
            storage_path = f'videos/{storage_kind_prefix(source_kind)}/{slug}/{candidate.name}'
            try:
                public_url = supa.upload_file(candidate, storage_path, 'video/mp4')
            except Exception:  # noqa: BLE001
                return False
            uploaded_public_url = public_url
            uploaded_storage_path = storage_path
            uploaded_file = candidate
            return True

        if not try_upload(source_file):
            for bitrate in VIDEO_BITRATES:
                candidate = video_dir / f'video-{media["id"]}-{bitrate}.mp4'
                if not candidate.exists() or candidate.stat().st_size == 0:
                    if not transcode_video(source_file, candidate, bitrate):
                        continue
                if try_upload(candidate):
                    break

        if not uploaded_public_url:
            failed += 1
            print(f'[{index}/{len(media_rows)}] fail media#{media["id"]}: upload failed for all candidates', flush=True)
            continue

        details = dict(media.get('details') or {})
        details['telegram_post'] = post
        details['telegram_url'] = f'https://t.me/{post}'
        patch_payload = {
            'mime_type': 'video/mp4',
            'source_url': uploaded_public_url,
            'storage_bucket': STORAGE_BUCKET,
            'storage_path': uploaded_storage_path,
            'public_url': uploaded_public_url,
            'details': details,
        }
        supa.request(
            'PATCH',
            '/rest/v1/listing_media',
            params={'id': f'eq.{media["id"]}'},
            payload=patch_payload,
            extra_headers={'Prefer': 'return=minimal'},
        )
        converted += 1
        size_mb = uploaded_file.stat().st_size / (1024 * 1024) if uploaded_file else 0
        print(
            f'[{index}/{len(media_rows)}] ok media#{media["id"]} {slug} -> {uploaded_file.name if uploaded_file else "unknown"} ({size_mb:.1f} MB)',
            flush=True,
        )

    await client.disconnect()
    print({'converted': converted, 'failed': failed, 'total': len(media_rows)}, flush=True)


if __name__ == '__main__':
    asyncio.run(main())
