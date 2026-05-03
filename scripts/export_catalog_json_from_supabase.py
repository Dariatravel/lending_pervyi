#!/usr/bin/env python3
"""Пересобирает output/current_pages.json и kvartira_cards.json из активных listings в Supabase."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / '.env.supabase.local'
OUTPUT_DIR = ROOT / 'output'
CURRENT_PAGES_PATH = OUTPUT_DIR / 'current_pages.json'
KV_CARDS_PATH = ROOT / 'kvartira_cards.json'


def load_env(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    if not path.exists():
        return result
    for raw in path.read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        if '=' not in line:
            continue
        key, value = line.split('=', 1)
        result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def kv_cover_image_path(slug: str, cover_url: str | None) -> str:
    if cover_url and '/kvartira-cards/' in cover_url:
        tail = cover_url.split('/kvartira-cards/', 1)[-1].split('?', 1)[0]
        return f'/media/kvartira-cards/{tail}'
    return f'/media/kvartira-cards/{slug}-cover.jpg'


def main() -> int:
    env = load_env(ENV_PATH)
    base = env.get('SUPABASE_URL', '').rstrip('/')
    key = env.get('SUPABASE_SERVICE_ROLE_KEY', '')
    if not base or not key:
        print(f'Нужны SUPABASE_URL и SUPABASE_SERVICE_ROLE_KEY в {ENV_PATH}', file=sys.stderr)
        return 1

    headers = {'apikey': key, 'Authorization': f'Bearer {key}'}
    response = requests.get(
        f'{base}/rest/v1/listings',
        headers=headers,
        params={
            'select': ', '.join([
                'slug',
                'source_kind',
                'source_message_id',
                'source_topic_id',
                'title',
                'excerpt',
                'page_url',
                'telegram_url',
                'published_at',
                'has_video',
                'cover_url',
                'is_active',
            ]),
            'is_active': 'eq.true',
            'order': 'published_at.desc',
            'limit': '5000',
        },
        timeout=120,
    )
    response.raise_for_status()
    rows: list[dict] = response.json()

    hotels = [r for r in rows if r.get('source_kind') == 'hotel']
    kv = [r for r in rows if r.get('source_kind') == 'kvartira']

    current_pages = [
        {
            'slug': r['slug'],
            'source_id': int(r['source_message_id']),
            'title': r.get('title') or '',
        }
        for r in hotels
        if r.get('slug') and r.get('source_message_id') is not None
    ]
    current_pages.sort(key=lambda item: item['source_id'])

    kvartira_cards = []
    for r in kv:
        slug = r.get('slug') or ''
        msg_id = r.get('source_message_id')
        if not slug or msg_id is None:
            continue
        topic_raw = r.get('source_topic_id')
        kvartira_cards.append({
            'title': r.get('title') or '',
            'slug': slug,
            'topic_id': int(topic_raw) if topic_raw is not None else None,
            'message_id': int(msg_id),
            'url': r.get('page_url') or '',
            'telegram_url': r.get('telegram_url') or '',
            'image': kv_cover_image_path(slug, r.get('cover_url')),
            'has_video': bool(r.get('has_video')),
            'excerpt': (r.get('excerpt') or '').strip(),
        })
    kvartira_cards.sort(key=lambda item: item['message_id'], reverse=True)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CURRENT_PAGES_PATH.write_text(
        json.dumps(current_pages, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
    KV_CARDS_PATH.write_text(
        json.dumps(kvartira_cards, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
    print(f'Готово: отелей в current_pages: {len(current_pages)}, квартир в kvartira_cards: {len(kvartira_cards)}')
    print(f'  -> {CURRENT_PAGES_PATH.relative_to(ROOT)}')
    print(f'  -> {KV_CARDS_PATH.relative_to(ROOT)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
