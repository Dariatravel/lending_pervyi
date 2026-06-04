import json
import mimetypes
import os
import time
from pathlib import Path
from typing import Optional
from urllib.parse import quote

import requests

ROOT = Path('/Users/darya_botova/Documents/New project')
SEED_FILE = ROOT / 'output' / 'supabase_seed.json'

SUPABASE_URL = os.getenv('SUPABASE_URL', '').rstrip('/')
SERVICE_ROLE = os.getenv('SUPABASE_SERVICE_ROLE_KEY', '')
STORAGE_BUCKET = os.getenv('SUPABASE_STORAGE_BUCKET', 'site-media')


def require_env() -> None:
    if not SUPABASE_URL or not SERVICE_ROLE:
        raise RuntimeError('Нужны SUPABASE_URL и SUPABASE_SERVICE_ROLE_KEY в окружении.')


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        'apikey': SERVICE_ROLE,
        'Authorization': f'Bearer {SERVICE_ROLE}',
    })
    return s


def fetch_listing_map(s: requests.Session) -> dict[tuple[str, str, int], int]:
    response = s.get(
        f'{SUPABASE_URL}/rest/v1/listings',
        params={'select': 'id,source_kind,source_channel,source_message_id', 'limit': '5000'},
        timeout=120,
    )
    response.raise_for_status()
    rows = response.json()
    return {(row['source_kind'], row['source_channel'], row['source_message_id']): row['id'] for row in rows}


def public_url_for(storage_path: str) -> str:
    encoded_path = '/'.join(quote(part) for part in storage_path.split('/'))
    return f'{SUPABASE_URL}/storage/v1/object/public/{STORAGE_BUCKET}/{encoded_path}'


def object_exists(url: str) -> bool:
    try:
        response = requests.head(url, timeout=20, allow_redirects=True)
        if response.status_code == 200:
            return True
        if response.status_code in {404, 400}:
            return False
    except requests.RequestException:
        pass
    try:
        response = requests.get(url, timeout=20, stream=True)
        ok = response.status_code == 200
        response.close()
        return ok
    except requests.RequestException:
        return False


def upload_file(s: requests.Session, local_path: Path, storage_path: str, mime_type: Optional[str]) -> str:
    encoded_path = '/'.join(quote(part) for part in storage_path.split('/'))
    url = f'{SUPABASE_URL}/storage/v1/object/{STORAGE_BUCKET}/{encoded_path}'
    data = local_path.read_bytes()
    headers = {
        'Content-Type': mime_type or 'application/octet-stream',
        'Cache-Control': 'public, max-age=31536000, immutable',
        'x-upsert': 'true',
    }
    last_error = None
    for attempt in range(5):
        try:
            response = s.post(url, data=data, headers=headers, timeout=600)
            response.raise_for_status()
            return public_url_for(storage_path)
        except requests.RequestException as error:
            last_error = error
            time.sleep(1 + attempt)
    raise RuntimeError(f'Не удалось загрузить {storage_path}: {last_error}')


def patch_media(s: requests.Session, listing_id: int, media_role: str, sort_order: int, public_url: str, file_size: int):
    response = s.patch(
        f'{SUPABASE_URL}/rest/v1/listing_media',
        params={
            'listing_id': f'eq.{listing_id}',
            'media_role': f'eq.{media_role}',
            'sort_order': f'eq.{sort_order}',
        },
        headers={'Content-Type': 'application/json'},
        json={'public_url': public_url, 'details': {'file_size': file_size}},
        timeout=120,
    )
    response.raise_for_status()


def main() -> None:
    require_env()
    payload = json.loads(SEED_FILE.read_text(encoding='utf-8'))
    s = session()
    listing_map = fetch_listing_map(s)
    uploaded = 0
    reused = 0
    missing_local = 0
    for item in payload['media']:
        local_path = Path(item['local_path'])
        if not local_path.exists():
            missing_local += 1
            continue
        storage_path = item.get('storage_path') or item['source_url'].lstrip('/media/')
        mime_type = item.get('mime_type') or mimetypes.guess_type(local_path.name)[0]
        public_url = public_url_for(storage_path)
        if object_exists(public_url):
            reused += 1
        else:
            public_url = upload_file(s, local_path, storage_path, mime_type)
            uploaded += 1
        listing_id = listing_map.get((item['source_kind'], item['source_channel'], item['source_message_id']))
        if listing_id:
            patch_media(s, listing_id, item['media_role'], item['sort_order'], public_url, local_path.stat().st_size)
        if (uploaded + reused) % 50 == 0:
            print(f'Обработано: {uploaded + reused} | загружено: {uploaded} | переиспользовано: {reused}')
    print(f'Готово. Загружено: {uploaded}, переиспользовано: {reused}, отсутствует локально: {missing_local}')


if __name__ == '__main__':
    main()
