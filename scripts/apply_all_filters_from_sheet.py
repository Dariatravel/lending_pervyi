from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import requests
from google.oauth2 import service_account
from googleapiclient.discovery import build

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / '.env.supabase.local'
REPORT_PATH = ROOT / 'output' / 'all_filters_sync_report.txt'
EMPTY_FILTERS: dict[str, list[str]] = {g: [] for g in ('distance', 'food', 'price', 'city', 'beach', 'room', 'stay')}

SPREADSHEET_ID = '135fxeZX5OE30rH3Sg5KWpTR4VuhBntCzGrTk0WcdTBY'
SHEET_NAME = 'СОЦСЕТИ'
RANGE = f'{SHEET_NAME}!A2:BK'

# 0-based индексы колонок
COL = {
    'title': 0,          # A
    'n_text': 13,         # N
    'tg_link': 8,         # I
    'ab_text': 27,        # AB
    'ac_capacity': 28,    # AC

    # Пляж
    'beach_ad': 29,       # AD
    'beach_ae': 30,       # AE
    'beach_af': 31,       # AF

    # Расстояние
    'dist_beachfront': 33,  # AH
    'dist_up5': 34,         # AI
    'dist_up10': 35,        # AJ
    'dist_over10': 36,      # AK

    # Особенности номера
    'room_beachfront': 37,  # AL
    'room_two_plus': 38,    # AM
    'room_five_plus': 39,   # AN
    'room_kitchen': 40,     # AO
    'room_sea_view': 41,    # AP
    'room_pool': 45,        # AT
    'room_balcony': 61,     # BJ
    'room_terrace': 62,     # BK

    # Особенности размещения
    'stay_cottages': 42,    # AQ
    'stay_apartments': 43,  # AR
    'stay_turnkey': 44,     # AS
    'stay_pets': 48,        # AW

    # Питание
    'food_filter': 47,      # AV

    # Город
    'city_ldzaa': 50,       # AY
    'city_pitsunda': 51,    # AZ
    'city_gagra': 52,       # BA
    'city_alakhadzy': 53,   # BB
    'city_gudauta': 54,     # BC
    'city_new_afon': 55,    # BD
    'city_sukhum': 56,      # BE
    'city_tsandripsh': 57,  # BF

    # Цена
    'price_economy': 58,    # BG
    'price_midrange': 59,   # BH
    'price_premium': 60,    # BI
}

GROUPS = ('distance', 'food', 'price', 'city', 'beach', 'room', 'stay')


def load_env(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.exists():
        return data
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, v = line.split('=', 1)
        data[k.strip()] = v.strip()
    return data


def pick_google_credentials_path() -> Path:
    candidates = [
        os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON', '').strip(),
        str(ROOT / 'google-service-account.json'),
        '/Users/darya_botova/Downloads/sonorous-bounty-488706-q9-32a19387de8d.json',
        '/Users/darya_botova/Documents/ПОДБОРКИ/telegram_export/credentials.json',
    ]
    for value in candidates:
        if not value:
            continue
        path = Path(value)
        if path.exists():
            return path
    raise FileNotFoundError('Не найден JSON service account для Google Sheets.')


def fetch_sheet_rows(credentials_path: Path) -> list[list[str]]:
    scopes = ['https://www.googleapis.com/auth/spreadsheets.readonly']
    creds = service_account.Credentials.from_service_account_file(str(credentials_path), scopes=scopes)
    service = build('sheets', 'v4', credentials=creds, cache_discovery=False)
    response = service.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range=RANGE).execute()
    return response.get('values', [])


def get_cell(row: list[str], key: str) -> str:
    idx = COL[key]
    if idx < len(row):
        return str(row[idx] or '').strip()
    return ''


def has_value(value: str) -> bool:
    return bool(str(value or '').strip())


def has_yes(value: str) -> bool:
    v = str(value or '').strip().lower()
    if not v:
        return False
    if re.fullmatch(r'(нет|no|false|0|n/?a|—|-|не\s*требуется|не\s*предусмотрено)', v):
        return False
    if v.startswith('нет '):
        return False
    return True


def parse_telegram_link(link: str) -> tuple[str, int] | None:
    if not has_value(link):
        return None
    link = link.strip()
    # Поддержка:
    # t.me/channel/1234
    # t.me/channel/topic_id/1234 — для abhkvartira ключ = topic_id (как в Supabase)
    forum_match = re.search(
        r'(?:https?://)?t\.me/(?:s/)?([A-Za-z0-9_]+)/(\d+)/(\d+)',
        link,
    )
    if forum_match:
        channel = forum_match.group(1).lower()
        topic_id = int(forum_match.group(2))
        message_id = int(forum_match.group(3))
        if channel == 'abhkvartira':
            return channel, topic_id
        return channel, message_id
    match = re.search(r'(?:https?://)?t\.me/(?:s/)?([A-Za-z0-9_]+)/(\d+)', link)
    if not match:
        return None
    return match.group(1).lower(), int(match.group(2))


def dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for v in values:
        if not v or v in seen:
            continue
        seen.add(v)
        out.append(v)
    return out


def normalize_text(value: str) -> str:
    text = str(value or '').lower().replace('ё', 'е')
    text = re.sub(r'[\"“”«»]', ' ', text)
    text = re.sub(r'[^a-zа-я0-9\\s-]', ' ', text)
    text = re.sub(r'\\s+', ' ', text).strip()
    return text


def extract_core_name(value: str) -> str:
    text = str(value or '')
    quoted = re.search(r'[\"«](.+?)[\"»]', text)
    if quoted:
        return normalize_text(quoted.group(1))
    # fallback: первые 2-4 слова как "ядро" названия
    words = [w for w in normalize_text(text).split(' ') if w]
    return ' '.join(words[:4]).strip()


def infer_distance(row: list[str]) -> list[str]:
    values: list[str] = []
    if has_yes(get_cell(row, 'dist_beachfront')):
        values.append('beachfront')
    if has_yes(get_cell(row, 'dist_up5')):
        values.append('up-to-5')
    if has_yes(get_cell(row, 'dist_up10')):
        values.append('up-to-10')
    if has_yes(get_cell(row, 'dist_over10')):
        values.append('over-10')
    return dedupe(values)


def infer_food(row: list[str]) -> list[str]:
    text = get_cell(row, 'food_filter').lower()
    values: list[str] = []

    if not text:
        return ['no-food']

    if 'без питан' in text:
        values.append('no-food')
    if 'полупансион' in text:
        values.append('half-board')
    if 'завтрак' in text and ('обед' in text or 'ужин' in text or 'трехраз' in text or 'трёхраз' in text):
        values.append('full-board')
    if 'завтрак' in text and 'full-board' not in values:
        values.append('breakfast')
    if 'кафе' in text or 'столов' in text:
        values.append('cafe')

    # Если текст есть, но не разобран — считаем как без питания
    if not values:
        values.append('no-food')

    return dedupe(values)


def infer_price(row: list[str]) -> list[str]:
    values: list[str] = []
    if has_yes(get_cell(row, 'price_economy')):
        values.append('economy')
    if has_yes(get_cell(row, 'price_midrange')):
        values.append('midrange')
    if has_yes(get_cell(row, 'price_premium')):
        values.append('premium')
    return dedupe(values)


def infer_city(row: list[str]) -> list[str]:
    values: list[str] = []
    if has_yes(get_cell(row, 'city_sukhum')):
        values.append('sukhum')
    if has_yes(get_cell(row, 'city_new_afon')):
        values.append('new-afon')
    if has_yes(get_cell(row, 'city_gudauta')):
        values.append('gudauta')
    if has_yes(get_cell(row, 'city_ldzaa')):
        values.append('ldzaa')
    if has_yes(get_cell(row, 'city_pitsunda')):
        values.append('pitsunda')
    if has_yes(get_cell(row, 'city_alakhadzy')):
        values.append('alakhadzy')
    if has_yes(get_cell(row, 'city_gagra')):
        values.append('gagra')
    if has_yes(get_cell(row, 'city_tsandripsh')):
        values.append('tsandripsh')
    return dedupe(values)


def infer_beach(row: list[str]) -> list[str]:
    ad = get_cell(row, 'beach_ad')
    ae = get_cell(row, 'beach_ae')
    af = get_cell(row, 'beach_af')

    values: list[str] = []

    if has_yes(ad):
        values.append('pine-pebble-ldzaa-pitsunda')

    ae_low = ae.lower()
    if has_yes(ae):
        if 'песок/мелкая галька' in ae_low or 'мелкая галька/песок' in ae_low:
            values.append('pitsunda-bay-mixed')
        elif '(песок)' in ae_low:
            values.append('sand-ldzaa')
        elif 'песок' in ae_low and 'мелк' not in ae_low:
            values.append('sand-ldzaa')

    if has_yes(af):
        values.append('sand-sukhum')

    if not any([has_yes(ad), has_yes(ae), has_yes(af)]):
        values.append('pebble')

    return dedupe(values)


def infer_room(row: list[str]) -> list[str]:
    values: list[str] = []
    if has_yes(get_cell(row, 'room_sea_view')):
        values.append('sea-view')
    if has_yes(get_cell(row, 'room_pool')):
        values.append('pool')
    if has_yes(get_cell(row, 'room_balcony')):
        values.append('balcony')
    if has_yes(get_cell(row, 'room_terrace')):
        values.append('terrace')
    if has_yes(get_cell(row, 'room_kitchen')):
        values.append('kitchen')
    if has_yes(get_cell(row, 'room_five_plus')):
        values.append('five-plus')
    if has_yes(get_cell(row, 'room_two_plus')):
        values.append('two-room-plus')
    if has_yes(get_cell(row, 'room_beachfront')):
        values.append('beachfront-room')
    return dedupe(values)


def infer_stay(row: list[str]) -> list[str]:
    values: list[str] = []
    if has_yes(get_cell(row, 'stay_cottages')):
        values.append('cottages')
    if has_yes(get_cell(row, 'stay_apartments')):
        values.append('apartments')
    if has_yes(get_cell(row, 'stay_turnkey')):
        values.append('turnkey-house')
    if has_yes(get_cell(row, 'stay_pets')):
        values.append('pets')

    # По заданию: "Без маленьких детей" ставим только на объект "Апса-парк".
    title_blob = get_cell(row, 'title').lower().replace('ё', 'е')
    if 'апса' in title_blob and 'парк' in title_blob:
        values.append('no-small-kids')

    return dedupe(values)


def infer_all_filters(row: list[str]) -> dict[str, list[str]]:
    return {
        'distance': infer_distance(row),
        'food': infer_food(row),
        'price': infer_price(row),
        'city': infer_city(row),
        'beach': infer_beach(row),
        'room': infer_room(row),
        'stay': infer_stay(row),
    }


def listing_exists_on_site(listing: dict[str, Any], repo_root: Path | None = None) -> bool:
    """Объект считается на сайте, если есть HTML-страница hotels/… или kvartira/…."""
    base = repo_root or ROOT
    details = listing.get('details') or {}
    page_path = str(details.get('page_path') or '').strip()
    if page_path:
        path = Path(page_path)
        if path.is_file():
            return True
        alt = Path(page_path.replace('/New project/', f'/GitHub/lending_pervyi/'))
        if alt.is_file():
            return True
    slug = str(listing.get('slug') or '').strip()
    kind = str(listing.get('source_kind') or '').strip()
    if slug and kind in {'hotel', 'kvartira'}:
        folder = 'hotels' if kind == 'hotel' else 'kvartira'
        if (base / folder / slug / 'index.html').is_file():
            return True
    page_url = str(listing.get('page_url') or '')
    match = re.search(r'/(hotels|kvartira)/([^/?#]+)', page_url)
    if match:
        return (base / match.group(1) / match.group(2) / 'index.html').is_file()
    return False


def fetch_listings(supabase_url: str, service_role: str) -> list[dict[str, Any]]:
    headers = {'apikey': service_role, 'Authorization': f'Bearer {service_role}'}
    params = {
        'select': 'id,slug,source_kind,title,source_channel,source_message_id,page_url,details,is_active',
        'is_active': 'eq.true',
        'limit': '5000',
    }
    response = requests.get(f'{supabase_url}/rest/v1/listings', headers=headers, params=params, timeout=120)
    response.raise_for_status()
    return response.json()


def patch_listing_details(supabase_url: str, service_role: str, listing_id: int, details: dict[str, Any]) -> None:
    headers = {
        'apikey': service_role,
        'Authorization': f'Bearer {service_role}',
        'Content-Type': 'application/json',
        'Prefer': 'return=minimal',
    }
    params = {'id': f'eq.{listing_id}'}
    response = requests.patch(
        f'{supabase_url}/rest/v1/listings',
        headers=headers,
        params=params,
        data=json.dumps({'details': details}, ensure_ascii=False).encode('utf-8'),
        timeout=120,
    )
    response.raise_for_status()


def normalize_filter_values(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(v).strip() for v in raw if str(v).strip()]
    if isinstance(raw, str):
        return [v.strip() for v in raw.split('|') if v.strip()]
    return []


def main() -> None:
    parser = argparse.ArgumentParser(description='Перенос фильтров из Google Sheets «СОЦСЕТИ» в Supabase.')
    parser.add_argument(
        '--all-listings',
        action='store_true',
        help='Обновить все активные объекты в Supabase (по умолчанию — только с HTML-страницей на сайте).',
    )
    args = parser.parse_args()
    site_only = not args.all_listings

    env = load_env(ENV_PATH)
    supabase_url = env.get('SUPABASE_URL', '').rstrip('/')
    service_role = env.get('SUPABASE_SERVICE_ROLE_KEY', '')
    if not supabase_url or not service_role:
        raise RuntimeError('В .env.supabase.local должны быть SUPABASE_URL и SUPABASE_SERVICE_ROLE_KEY.')

    credentials_path = pick_google_credentials_path()
    sheet_rows = fetch_sheet_rows(credentials_path)

    rows_without_link = 0
    rows_unparsed_link = 0
    sheet_filters: dict[tuple[str, int], dict[str, list[str]]] = {}
    tg_source_by_key: dict[tuple[str, int], str] = {}
    sheet_title_by_key: dict[tuple[str, int], str] = {}

    sheet_group_value_counts: dict[str, Counter[str]] = {g: Counter() for g in GROUPS}

    for row in sheet_rows:
        tg_link = get_cell(row, 'tg_link')
        if not has_value(tg_link):
            rows_without_link += 1
            continue
        key = parse_telegram_link(tg_link)
        if not key:
            rows_unparsed_link += 1
            continue

        filters = infer_all_filters(row)
        sheet_filters[key] = filters
        tg_source_by_key[key] = tg_link
        sheet_title_by_key[key] = get_cell(row, 'title')

        for group in GROUPS:
            for value in filters[group]:
                sheet_group_value_counts[group][value] += 1

    listings = fetch_listings(supabase_url, service_role)
    listing_map: dict[tuple[str, int], dict[str, Any]] = {}
    listings_by_kind: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in listings:
        channel = str(row.get('source_channel') or '').lower().strip()
        message_id = int(row.get('source_message_id') or 0)
        topic_id = int(row.get('source_topic_id') or 0)
        if channel and message_id:
            listing_map[(channel, message_id)] = row
        if channel == 'abhkvartira' and topic_id:
            listing_map[(channel, topic_id)] = row
        source_kind = str(row.get('source_kind') or '').strip()
        if source_kind:
            listings_by_kind[source_kind].append(row)

    updated = 0
    unchanged = 0
    not_found = 0
    skipped_not_on_site = 0
    on_site_total = 0

    group_changed: Counter[str] = Counter()
    group_assigned: Counter[str] = Counter()
    not_found_links: list[str] = []

    for key, new_filters in sheet_filters.items():
        listing = listing_map.get(key)
        if not listing:
            channel, _message_id = key
            source_kind = 'kvartira' if channel == 'abhkvartira' else 'hotel'
            core = extract_core_name(sheet_title_by_key.get(key, ''))
            if core:
                candidates = [
                    row for row in listings_by_kind.get(source_kind, [])
                    if core in normalize_text(str(row.get('title') or ''))
                    and abs(int(row.get('source_message_id') or 0) - int(_message_id)) <= 30
                ]
                if len(candidates) == 1:
                    listing = candidates[0]
        if not listing:
            not_found += 1
            not_found_links.append(tg_source_by_key[key])
            continue

        if site_only and not listing_exists_on_site(listing):
            skipped_not_on_site += 1
            continue
        on_site_total += 1

        details = listing.get('details') or {}
        if not isinstance(details, dict):
            details = {}

        existing_filters = details.get('filters') or {}
        if not isinstance(existing_filters, dict):
            existing_filters = {}

        changed_any = False

        for group in GROUPS:
            old_values = normalize_filter_values(existing_filters.get(group))
            new_values = list(new_filters[group])

            if old_values != new_values:
                changed_any = True
                group_changed[group] += 1

            existing_filters[group] = new_values
            if new_values:
                group_assigned[group] += 1

        if not changed_any:
            unchanged += 1
            continue

        details['filters'] = existing_filters
        patch_listing_details(supabase_url, service_role, int(listing['id']), details)
        updated += 1

    lines: list[str] = []
    lines.append('Готово. Массовый перенос фильтров из СОЦСЕТИ в Supabase выполнен.')
    lines.append('')
    lines.append(f'Режим: {"только объекты с HTML на сайте" if site_only else "все активные listings"}')
    lines.append(f'Строк в СОЦСЕТИ: {len(sheet_rows)}')
    lines.append(f'Разобрано ссылок Telegram: {len(sheet_filters)}')
    lines.append(f'Без ссылки Telegram: {rows_without_link}')
    lines.append(f'Ссылка не распознана: {rows_unparsed_link}')
    lines.append(f'Обработано объектов на сайте (есть строка в таблице): {on_site_total}')
    lines.append(f'Обновлено объектов в Supabase: {updated}')
    lines.append(f'Без изменений: {unchanged}')
    lines.append(f'Пропущено (нет HTML-страницы на сайте): {skipped_not_on_site}')
    lines.append(f'Не найдено в Supabase по channel+message_id: {not_found}')
    lines.append('')
    lines.append('Отчёт по группам фильтров:')
    for group in GROUPS:
        lines.append(f'- {group}: заполнено по таблице (непустые) у {group_assigned[group]} объектов, изменено у {group_changed[group]} объектов')
        values_repr = ', '.join(f'{k}:{v}' for k, v in sheet_group_value_counts[group].most_common()) or 'нет значений'
        lines.append(f'  значения: {values_repr}')

    if rows_unparsed_link:
        lines.append('')
        lines.append('Нераспознанные ссылки Telegram (из таблицы):')
        for row in sheet_rows:
            tg_link = get_cell(row, 'tg_link')
            if has_value(tg_link) and parse_telegram_link(tg_link) is None:
                lines.append(f'- {tg_link}')

    if not_found_links:
        lines.append('')
        lines.append('Ссылки, не найденные в Supabase:')
        for link in not_found_links:
            lines.append(f'- {link}')

    report = '\n'.join(lines)
    print(report)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding='utf-8')


if __name__ == '__main__':
    main()
