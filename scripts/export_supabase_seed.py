import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, unquote, urlparse
from typing import Optional

ROOT = Path('/Users/darya_botova/Documents/New project')
INDEX_FILE = ROOT / 'index.html'
KVARTIRA_JSON = ROOT / 'kvartira_cards.json'
CURRENT_PAGES = ROOT / 'output' / 'current_pages.json'
HOTELS_DIR = ROOT / 'hotels'
OUT_FILE = ROOT / 'output' / 'supabase_seed.json'
STORAGE_BUCKET = 'site-media'
SITE_BASE = 'https://абхазберег.рф'


def clean(text: Optional[str]) -> str:
    if not text:
        return ''
    text = html.unescape(text)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def first(pattern: str, text: str) -> str:
    match = re.search(pattern, text, flags=re.S | re.I)
    return clean(match.group(1)) if match else ''


def many(pattern: str, text: str) -> list[str]:
    return [clean(item) for item in re.findall(pattern, text, flags=re.S | re.I)]


def guess_city(text: str) -> str:
    text = clean(text)
    if not text:
        return ''
    if '📍' in text:
        return text.split('📍', 1)[1].strip(' ,')
    head = text.split('.', 1)[0].strip()
    return head[:120]


def parse_index_cards() -> dict[str, dict]:
    html_text = INDEX_FILE.read_text(encoding='utf-8')
    cards = {}
    pattern = re.compile(
        r'<a class="catalog-card"(?P<attrs>[^>]*)href="/hotels/(?P<slug>[^/]+)/"[^>]*>(?P<body>.*?)</a>',
        flags=re.S | re.I,
    )
    for match in pattern.finditer(html_text):
        body = match.group('body')
        attrs = match.group('attrs')
        slug = match.group('slug')
        cards[slug] = {
            'slug': slug,
            'title': first(r'<h3>(.*?)</h3>', body),
            'summary': first(r'<p>(.*?)</p>', body),
            'card_image': first(r'<img[^>]+src="([^"]+)"', body),
            'filters': {
                'distance': first(r'data-filter-distance="([^"]*)"', attrs),
                'food': first(r'data-filter-food="([^"]*)"', attrs),
                'price': first(r'data-filter-price="([^"]*)"', attrs),
                'city': first(r'data-filter-city="([^"]*)"', attrs),
                'beach': first(r'data-filter-beach="([^"]*)"', attrs),
                'room': first(r'data-filter-room="([^"]*)"', attrs),
                'stay': first(r'data-filter-stay="([^"]*)"', attrs),
            },
        }
    return cards


def hotel_listing(slug: str, source_id: int, card: dict) -> tuple[dict, list[dict]]:
    page_path = HOTELS_DIR / slug / 'index.html'
    html_text = page_path.read_text(encoding='utf-8')
    title = first(r'<h1>(.*?)</h1>', html_text) or card.get('title') or slug
    lead = first(r'<p class="lead">(.*?)</p>', html_text) or card.get('summary')
    published_at = first(r'<time datetime="([^"]+)"', html_text)
    canonical = first(r'<link rel="canonical" href="([^"]+)"', html_text)
    location_block = first(r'<article class="card accent">.*?<h2>Локация</h2>(.*?)</article>', html_text)
    location_lines = many(r'<p>(.*?)</p>', location_block)
    photo_paths = re.findall(r'<img src="(/media/hotels/[^"]+)"', html_text, flags=re.I)
    video_paths = re.findall(r'<source src="(/media/videos/[^"]+)"', html_text, flags=re.I)

    listing = {
        'source_kind': 'hotel',
        'source_channel': 'abhazbooking',
        'source_message_id': source_id,
        'source_topic_id': None,
        'slug': slug,
        'title': title,
        'summary': card.get('summary') or lead,
        'excerpt': lead,
        'city': guess_city(card.get('summary') or lead),
        'location_text': location_lines[0] if len(location_lines) > 0 else '',
        'distance_text': location_lines[1] if len(location_lines) > 1 else '',
        'beach_text': location_lines[1] if len(location_lines) > 1 else '',
        'capacity_text': location_lines[2] if len(location_lines) > 2 else '',
        'page_url': canonical or f'{SITE_BASE}/hotels/{slug}/',
        'telegram_url': f'https://t.me/abhazbooking/{source_id}',
        'published_at': published_at or None,
        'has_video': bool(video_paths),
        'cover_url': public_url_from_storage(normalize_storage_path(card.get('card_image') or (photo_paths[0] if photo_paths else ''))),
        'is_active': True,
        'details': {
            'filters': card.get('filters', {}),
            'lead': lead,
            'page_path': str(page_path),
        },
    }

    media = []
    if card.get('card_image'):
        storage_path = normalize_storage_path(card['card_image'])
        local = local_path_from_source(card['card_image'])
        media.append({
            'listing_slug': slug,
            'source_kind': 'hotel',
            'source_channel': 'abhazbooking',
            'source_message_id': source_id,
            'media_role': 'card',
            'sort_order': 0,
            'mime_type': 'image/jpeg',
            'source_url': card['card_image'],
            'storage_bucket': STORAGE_BUCKET,
            'storage_path': storage_path,
            'public_url': public_url_from_storage(storage_path),
            'local_path': str(local) if local else '',
            'details': {},
        })
    for index, media_path in enumerate(photo_paths, start=1):
        local = local_path_from_source(media_path) or (ROOT / media_path.lstrip('/'))
        media.append({
            'listing_slug': slug,
            'source_kind': 'hotel',
            'source_channel': 'abhazbooking',
            'source_message_id': source_id,
            'media_role': 'gallery',
            'sort_order': index,
            'mime_type': 'image/jpeg',
            'source_url': media_path,
            'storage_bucket': STORAGE_BUCKET,
            'storage_path': normalize_storage_path(media_path),
            'public_url': public_url_from_storage(normalize_storage_path(media_path)),
            'local_path': str(local) if local else '',
            'details': {},
        })
    for index, media_path in enumerate(video_paths, start=1):
        local = local_path_from_source(media_path) or (ROOT / media_path.lstrip('/'))
        media.append({
            'listing_slug': slug,
            'source_kind': 'hotel',
            'source_channel': 'abhazbooking',
            'source_message_id': source_id,
            'media_role': 'video',
            'sort_order': index,
            'mime_type': 'video/mp4',
            'source_url': media_path,
            'storage_bucket': STORAGE_BUCKET,
            'storage_path': normalize_storage_path(media_path),
            'public_url': public_url_from_storage(normalize_storage_path(media_path)),
            'local_path': str(local) if local else '',
            'details': {},
        })
    return listing, media


def kvartira_listing(card: dict) -> tuple[dict, list[dict]]:
    slug = card['slug']
    listing = {
        'source_kind': 'kvartira',
        'source_channel': 'abhkvartira',
        'source_message_id': card['message_id'],
        'source_topic_id': card.get('topic_id'),
        'slug': slug,
        'title': clean(card['title']),
        'summary': clean(card.get('excerpt')),
        'excerpt': clean(card.get('excerpt')),
        'city': guess_city(card['title']),
        'location_text': '',
        'distance_text': '',
        'beach_text': '',
        'capacity_text': '',
        'page_url': f'{SITE_BASE}/kvartira/',
        'telegram_url': card['url'],
        'published_at': None,
        'has_video': bool(card.get('has_video')),
        'cover_url': public_url_from_storage(normalize_storage_path(card.get('image') or '')), 
        'is_active': True,
        'details': {
            'topic_id': card.get('topic_id'),
            'excerpt': clean(card.get('excerpt')),
        },
    }
    media = []
    image_path = card.get('image') or ''
    if image_path:
        ext = Path(image_path).suffix.lower() or '.jpg'
        mime_type = 'image/jpeg'
        if ext == '.png':
            mime_type = 'image/png'
        elif ext == '.webp':
            mime_type = 'image/webp'
        storage_path = normalize_storage_path(image_path)
        local = local_path_from_source(image_path)
        media.append({
            'listing_slug': slug,
            'source_kind': 'kvartira',
            'source_channel': 'abhkvartira',
            'source_message_id': card['message_id'],
            'media_role': 'card',
            'sort_order': 0,
            'mime_type': mime_type,
            'source_url': image_path,
            'storage_bucket': STORAGE_BUCKET,
            'storage_path': storage_path,
            'public_url': public_url_from_storage(storage_path),
            'local_path': str(local) if local else '',
            'details': {'has_video': bool(card.get('has_video'))},
        })
    return listing, media


def main() -> None:
    cards = parse_index_cards()
    current_pages = json.loads(CURRENT_PAGES.read_text(encoding='utf-8'))
    kvartira_cards = json.loads(KVARTIRA_JSON.read_text(encoding='utf-8'))

    listings = []
    media = []

    for item in current_pages:
        slug = item['slug']
        card = cards.get(slug, {'slug': slug, 'title': item.get('title', slug), 'summary': '', 'card_image': '', 'filters': {}})
        listing, media_items = hotel_listing(slug, item['source_id'], card)
        listings.append(listing)
        media.extend(media_items)

    for card in kvartira_cards:
        listing, media_items = kvartira_listing(card)
        listings.append(listing)
        media.extend(media_items)

    payload = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'listings': listings,
        'media': media,
    }
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Готово: {len(listings)} listings, {len(media)} media -> {OUT_FILE}')


if __name__ == '__main__':
    main()
