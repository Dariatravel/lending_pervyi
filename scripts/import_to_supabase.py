import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path('/Users/darya_botova/Documents/New project')
SEED_FILE = ROOT / 'output' / 'supabase_seed.json'

SUPABASE_URL = os.getenv('SUPABASE_URL', '').rstrip('/')
SERVICE_ROLE = os.getenv('SUPABASE_SERVICE_ROLE_KEY', '')


def require_env() -> None:
    if not SUPABASE_URL or not SERVICE_ROLE:
        raise RuntimeError('Нужны SUPABASE_URL и SUPABASE_SERVICE_ROLE_KEY в окружении.')


def request_json(method: str, path: str, payload=None):
    url = f'{SUPABASE_URL}{path}'
    data = None
    headers = {
        'apikey': SERVICE_ROLE,
        'Authorization': f'Bearer {SERVICE_ROLE}',
    }
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=120) as response:
        raw = response.read().decode('utf-8')
        return json.loads(raw) if raw else None


def chunks(items, size):
    for index in range(0, len(items), size):
        yield items[index:index + size]


def upsert_listings(listings: list[dict]):
    rows = []
    for item in listings:
        row = {k: v for k, v in item.items() if k != 'local_path'}
        rows.append(row)
    for part in chunks(rows, 200):
        encoded = urllib.parse.quote('source_kind,source_channel,source_message_id', safe=',')
        path = f'/rest/v1/listings?on_conflict={encoded}'
        headers = {
            'apikey': SERVICE_ROLE,
            'Authorization': f'Bearer {SERVICE_ROLE}',
            'Content-Type': 'application/json',
            'Prefer': 'resolution=merge-duplicates,return=representation',
        }
        req = urllib.request.Request(
            f'{SUPABASE_URL}{path}',
            data=json.dumps(part, ensure_ascii=False).encode('utf-8'),
            headers=headers,
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=120) as response:
            response.read()


def fetch_listing_map() -> dict[tuple[str, str, int], int]:
    rows = request_json('GET', '/rest/v1/listings?select=id,slug,source_kind,source_channel,source_message_id')
    result = {}
    for row in rows:
        result[(row['source_kind'], row['source_channel'], row['source_message_id'])] = row['id']
    return result


def upsert_media(media: list[dict], listing_map: dict[tuple[str, str, int], int]):
    rows = []
    for item in media:
        listing_id = listing_map.get((item['source_kind'], item['source_channel'], item['source_message_id']))
        if not listing_id:
            continue
        rows.append({
            'listing_id': listing_id,
            'media_role': item['media_role'],
            'sort_order': item['sort_order'],
            'mime_type': item.get('mime_type'),
            'source_url': item.get('source_url'),
            'storage_bucket': item.get('storage_bucket'),
            'storage_path': item.get('storage_path'),
            'public_url': item.get('public_url'),
            'details': item.get('details', {}),
        })
    for part in chunks(rows, 200):
        encoded = urllib.parse.quote('listing_id,media_role,sort_order', safe=',')
        path = f'/rest/v1/listing_media?on_conflict={encoded}'
        headers = {
            'apikey': SERVICE_ROLE,
            'Authorization': f'Bearer {SERVICE_ROLE}',
            'Content-Type': 'application/json',
            'Prefer': 'resolution=merge-duplicates,return=minimal',
        }
        req = urllib.request.Request(
            f'{SUPABASE_URL}{path}',
            data=json.dumps(part, ensure_ascii=False).encode('utf-8'),
            headers=headers,
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=120) as response:
            response.read()


def main() -> None:
    require_env()
    payload = json.loads(SEED_FILE.read_text(encoding='utf-8'))
    listings = payload['listings']
    media = payload['media']
    upsert_listings(listings)
    listing_map = fetch_listing_map()
    upsert_media(media, listing_map)
    print(f'Импорт завершен: {len(listings)} listings, {len(media)} media')


if __name__ == '__main__':
    main()
