from __future__ import annotations

import asyncio
import json
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path('/Users/darya_botova/Documents/New project')
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(ROOT))

from telethon import TelegramClient
from telethon.tl.types import MessageMediaDocument, MessageMediaPhoto

from sync_abhazbooking_2026 import (
    HOTELS_DIR,
    INDEX_FILE,
    MEDIA_CARDS_DIR,
    MEDIA_HOTELS_DIR,
    MEDIA_VIDEOS_DIR,
    OUTPUT_DIR,
    REPORT_FILE,
    SITEMAP_FILE,
    build_slug,
    city_label,
    clean_line,
    extract_existing_pages,
    format_human_date,
    is_object_post,
    parse_post,
    render_page,
    summary_text,
    update_index,
    update_sitemap,
)
from telegram_runtime import connected_telegram_client, run_async_entrypoint

CURRENT_PAGES = OUTPUT_DIR / 'current_pages.json'
API_ID = 27444661
API_HASH = '1e4696782f7d5f6214f3264f3884f291'
CHANNEL = 'abhazbooking'
CUTOFF_DATE = '2026-01-01'
SESSION = 'tg_session'


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def build_current_pages(all_pages: list[dict[str, Any]]) -> None:
    rows = []
    for page in sorted(all_pages, key=lambda item: item['source_id']):
        rows.append({
            'slug': page['slug'],
            'source_id': page['source_id'],
            'title': page['title'],
        })
    write_json(CURRENT_PAGES, rows)




def normalize_for_parser(text: str) -> str:
    normalized = []
    for raw_line in (text or '').splitlines():
        line = clean_line(raw_line)
        if not line:
            continue
        matched = False
        for marker in ('📍', '🏖', '🏝', '👥'):
            if line.startswith(marker):
                value = clean_line(line[len(marker):])
                normalized.append(marker)
                if value:
                    normalized.append(value)
                matched = True
                break
        if not matched:
            normalized.append(line)
    return "\n".join(normalized)

def media_kind(message) -> str:
    if isinstance(message.media, MessageMediaPhoto):
        return 'photo'
    if isinstance(message.media, MessageMediaDocument):
        mime = getattr(message.media.document, 'mime_type', '') or ''
        if mime.startswith('video/'):
            return 'video'
    return ''


async def fetch_candidate_posts(client: TelegramClient, entity) -> list:
    posts = []
    async for message in client.iter_messages(entity, limit=300):
        if not message.date:
            continue
        if str(message.date.date()) < CUTOFF_DATE:
            break
        text = normalize_for_parser(message.raw_text or message.text or '')
        if not text or not is_object_post(text):
            continue
        posts.append(message)
    posts.sort(key=lambda item: item.id)
    return posts


async def fetch_group_media(client: TelegramClient, entity, message) -> tuple[list, list]:
    if not getattr(message, 'grouped_id', None):
        return ([message] if media_kind(message) == 'photo' else [], [message] if media_kind(message) == 'video' else [])

    grouped = []
    async for item in client.iter_messages(entity, limit=50):
        if item.grouped_id == message.grouped_id:
            grouped.append(item)
        elif grouped and item.id < message.id:
            break
    grouped.sort(key=lambda item: item.id)
    photos = [item for item in grouped if media_kind(item) == 'photo']
    videos = [item for item in grouped if media_kind(item) == 'video']
    return photos, videos


async def download_media_set(client: TelegramClient, photos: list, videos: list, slug: str) -> tuple[int, str, int | None]:
    media_dir = MEDIA_HOTELS_DIR / slug
    media_dir.mkdir(parents=True, exist_ok=True)
    photo_count = 0
    for index, item in enumerate(photos, start=1):
        target = media_dir / f'photo-{index:02d}.jpg'
        await client.download_media(item, file=str(target))
        if target.exists() and target.stat().st_size > 0:
            photo_count += 1

    video_filename = ''
    video_post_id = None
    if videos:
        video = videos[-1]
        video_filename = f'{slug}-{video.id}.mp4'
        target = MEDIA_VIDEOS_DIR / video_filename
        await client.download_media(video, file=str(target))
        if not target.exists() or target.stat().st_size == 0:
            video_filename = ''
        else:
            video_post_id = video.id
    return photo_count, video_filename, video_post_id


async def main() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    existing_pages = extract_existing_pages()
    existing_ids = {page['source_id'] for page in existing_pages}
    existing_slugs = {page['slug'] for page in existing_pages}
    pages_by_source = {page['source_id']: page for page in existing_pages}

    async with connected_telegram_client(SESSION, API_ID, API_HASH, receive_updates=False) as client:
        entity = await client.get_entity(CHANNEL)
        candidate_posts = await fetch_candidate_posts(client, entity)

        report_posts = []
        created = []
        managed_ids: set[int] = set()
        if REPORT_FILE.exists():
            try:
                managed_ids = {item['source_id'] for item in json.loads(REPORT_FILE.read_text(encoding='utf-8')).get('created', [])}
            except Exception:
                managed_ids = set()

        for message in candidate_posts:
            parsed = parse_post(normalize_for_parser(message.raw_text or message.text or ''))
            report_posts.append({
                'id': message.id,
                'date': str(message.date.date()),
                'text': normalize_for_parser(message.raw_text or message.text or ''),
                'title': parsed['title'],
                'grouped_id': message.grouped_id,
            })

            if message.id in existing_ids and message.id not in managed_ids:
                continue
            if not parsed['title']:
                continue

            existing_page = pages_by_source.get(message.id)
            slug = existing_page['slug'] if existing_page else build_slug(parsed['title'], message.id, existing_slugs)
            existing_slugs.add(slug)

            photos, videos = await fetch_group_media(client, entity, message)
            photo_count, video_filename, video_post_id = await download_media_set(client, photos, videos, slug)
            if photo_count == 0:
                continue

            MEDIA_CARDS_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(MEDIA_HOTELS_DIR / slug / 'photo-01.jpg', MEDIA_CARDS_DIR / f'{slug}.jpg')

            page_dir = HOTELS_DIR / slug
            page_dir.mkdir(parents=True, exist_ok=True)
            page_html = render_page(
                slug,
                message.id,
                str(message.date.date()),
                parsed,
                photo_count,
                video_filename,
                video_post_id,
            )
            (page_dir / 'index.html').write_text(page_html, encoding='utf-8')

            created.append({
                'slug': slug,
                'source_id': message.id,
                'title': parsed['title'],
                'location': parsed['location'],
                'beach': parsed['beach'],
                'capacity': parsed['capacity'],
                'location_text': parsed['location'],
                'summary': summary_text(parsed['location'], parsed['beach'], parsed['capacity']),
                'has_video': bool(video_filename),
                'video_post_id': video_post_id,
            })

    all_pages = [page for page in existing_pages if page['source_id'] not in {item['source_id'] for item in created}] + created
    update_index(all_pages)
    update_sitemap(all_pages)
    build_current_pages(all_pages)
    write_json(OUTPUT_DIR / 'abhazbooking_2026_posts.json', report_posts)

    report = {
        'created_count': len(created),
        'created': created,
        'existing_count': len(existing_pages),
        'current_total': len(all_pages),
        'removed_count': 0,
        'removed': [],
    }
    write_json(REPORT_FILE, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    raise SystemExit(run_async_entrypoint(main(), name='sync_new_abhazbooking_from_telegram', default_timeout=1800))
