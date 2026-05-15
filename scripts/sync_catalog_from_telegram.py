from __future__ import annotations

import asyncio
import html
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import time
import hashlib
import importlib.util
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote

import requests
from telethon import TelegramClient
from telethon.errors.rpcerrorlist import FileReferenceExpiredError
from telethon.tl.functions import messages as message_functions

ROOT = Path.cwd()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / 'scripts') not in sys.path:
    sys.path.insert(0, str(ROOT / 'scripts'))

from sync_abhazbooking_2026 import (  # noqa: E402
    build_slug,
    city_label,
    clean_line,
    format_human_date,
    parse_post,
    render_paragraph_lines_html,
    render_reviews,
    should_drop_line,
    summary_text,
)
from apply_all_filters_from_sheet import EMPTY_FILTERS  # noqa: E402

ROOT_INDEX = ROOT / 'index.html'
HOTELS_DIR = ROOT / 'hotels'
KVARTIRA_DIR = ROOT / 'kvartira'
HOTEL_MEDIA_DIR = ROOT / 'media' / 'hotels'
KV_MEDIA_DIR = ROOT / 'media' / 'kvartira'
CARD_DIR = ROOT / 'media' / 'cards'
KV_CARD_DIR = ROOT / 'media' / 'kvartira-cards'
VIDEOS_DIR = ROOT / 'media' / 'videos'
OUTPUT_DIR = ROOT / 'output'
CURRENT_PAGES_FILE = OUTPUT_DIR / 'current_pages.json'
POSTS_FILE = OUTPUT_DIR / 'abhazbooking_2026_posts.json'
TOPICS_FILE = ROOT / 'topics.json'
KV_CARDS_FILE = ROOT / 'kvartira_cards.json'
ENV_FILE = ROOT / '.env.supabase.local'
STORAGE_BUCKET = 'site-media'
CUTOFF_DATE = '2026-01-01'
API_ID = 32916166
API_HASH = 'eefdec49605521b061de4bdf62ef784e'
SESSION = os.getenv('TG_SESSION', str(ROOT / 'tg_session'))
MAX_VIDEO_UPLOAD_MB = 48
VIDEO_BITRATES = ('1800k', '1200k', '900k', '700k', '500k', '350k')
MAX_LOCAL_SOURCE_KEEP_MB = 95
VIDEO_MAX_WIDTH = 960
FORCE_MEDIA_REFRESH = os.getenv('FORCE_MEDIA_REFRESH', '').strip().lower() in {'1', 'true', 'yes', 'on'}
# По умолчанию фото (как и видео) уходят в Supabase Storage, чтобы прод работал без /media из git.
SKIP_IMAGE_UPLOAD_TO_SUPABASE = os.getenv('SKIP_IMAGE_UPLOAD_TO_SUPABASE', '').strip().lower() in {
    '1',
    'true',
    'yes',
    'on',
}
def _parse_int_set(raw: str) -> set[int]:
    result: set[int] = set()
    for part in (raw or '').split(','):
        token = part.strip()
        if not token:
            continue
        try:
            result.add(int(token))
        except ValueError:
            continue
    return result


TARGET_HOTEL_SOURCE_IDS = _parse_int_set(os.getenv('TARGET_HOTEL_SOURCE_IDS', ''))
TARGET_KV_TOPIC_IDS = _parse_int_set(os.getenv('TARGET_KV_TOPIC_IDS', ''))
TARGET_SYNC_MODE = bool(TARGET_HOTEL_SOURCE_IDS or TARGET_KV_TOPIC_IDS)
CONTACT_BLOCK = '''      <section class="section cta-block hotel-contact-section hotel-site-concept__detail-section" id="contacts">
        <h2>Контакты</h2>
        <p>Задать вопросы либо проверить наличие номеров можно: <strong>+7 940 900-33-40</strong> (WhatsApp, Telegram, MAX).</p>
        <p class="note">(только сообщение, звонок не пройдёт)</p>
        <div class="contact-buttons">
          <a class="btn-book" href="https://max.ru/u/f9LHodD0cOLVw3RTEObQAuqGut5qrEnsCdmW7cdV4PgfGrp9ldI_eY2boY8" target="_blank" rel="noopener noreferrer">НАПИСАТЬ В MAX</a>
          <a class="btn-book" href="http://vk.cc/cQQnBn" target="_blank" rel="noopener noreferrer">НАПИСАТЬ В ВК</a>
          <a class="btn-book" href="https://t.me/abhazbooking_online" target="_blank" rel="noopener noreferrer">НАПИСАТЬ В TELEGRAM</a>
          <a class="btn-book" href="https://wa.me/79409003340" target="_blank" rel="noopener noreferrer">НАПИСАТЬ В WHATSAPP</a>
        </div>
      </section>'''
FAQ_BLOCK = '''      <section class="section hotel-faq-section hotel-site-concept__detail-section">
        <article class="card faq-card">
          <h2>Частые вопросы</h2>
          <div class="faq-list">
            <details>
              <summary>Где уточнить актуальное наличие?</summary>
              <p>Актуальное наличие уточняется напрямую у менеджера через Telegram, MAX, VK или WhatsApp.</p>
            </details>
            <details>
              <summary>Цены на странице актуальны?</summary>
              <p>Цены приведены по публикации поста. Перед оплатой всегда подтверждайте стоимость и даты у менеджера.</p>
            </details>
            <details>
              <summary>Можно ли задать дополнительные вопросы по объекту?</summary>
              <p>Да. Если важны нюансы по детям, парковке, питанию, кухне, животным или дороге к морю, лучше уточнить их заранее.</p>
            </details>
          </div>
        </article>
      </section>'''

_APPLY_DESIGN_MOD: Any = None


def _apply_design_mod():
    global _APPLY_DESIGN_MOD
    if _APPLY_DESIGN_MOD is None:
        spec = importlib.util.spec_from_file_location(
            'apply_new_site_design',
            ROOT / 'tools' / 'apply_new_site_design.py',
        )
        _APPLY_DESIGN_MOD = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(_APPLY_DESIGN_MOD)
    return _APPLY_DESIGN_MOD


def _reviews_panel_for_slug(mod: Any, slug: str) -> str:
    seed = sum(ord(ch) for ch in slug)
    wrapped = f'<section>{render_reviews(seed)}</section>'
    cards = mod.extract_reviews(wrapped)
    if not cards:
        return ''
    reviews_html = ''.join(
        f"""              <article class="review-card">
                <div class="review-card__top">
                  <strong>{html.escape(author)}</strong>
                  <span>{html.escape(kind)}</span>
                </div>
                <p>{html.escape(body)}</p>
              </article>"""
        for author, kind, body in cards[:2]
    )
    return (
        '<section class="reviews-panel">'
        '<div class="reviews-panel__head">'
        '<div class="reviews-summary"><span>Отзывы гостей</span>'
        '</div></div>'
        f'<div class="reviews-grid">{reviews_html}</div>'
        '</section>'
    )


@dataclass
class SupabaseClient:
    url: str
    service_key: str

    @property
    def headers(self) -> dict[str, str]:
        return {
            'apikey': self.service_key,
            'Authorization': f'Bearer {self.service_key}',
        }

    def request(self, method: str, path: str, *, params: dict[str, Any] | None = None, payload: Any | None = None, extra_headers: dict[str, str] | None = None) -> Any:
        url = f'{self.url}{path}'
        headers = dict(self.headers)
        if extra_headers:
            headers.update(extra_headers)
        last_error = None
        for attempt in range(6):
            try:
                response = requests.request(method, url, headers=headers, params=params, json=payload, timeout=180)
                response.raise_for_status()
                if not response.text:
                    return None
                return response.json()
            except Exception as error:  # noqa: BLE001
                last_error = error
                time.sleep(1 + attempt)
        raise last_error

    def fetch_listings(self, source_kind: str | None = None) -> list[dict[str, Any]]:
        params = {'select': '*', 'limit': '5000', 'order': 'id.asc'}
        if source_kind:
            params['source_kind'] = f'eq.{source_kind}'
        return self.request('GET', '/rest/v1/listings', params=params) or []

    def fetch_media(self) -> list[dict[str, Any]]:
        return self.request('GET', '/rest/v1/listing_media', params={'select': '*', 'limit': '10000', 'order': 'listing_id.asc,sort_order.asc'}) or []

    def insert_listing(self, payload: dict[str, Any]) -> dict[str, Any]:
        rows = self.request(
            'POST',
            '/rest/v1/listings',
            payload=[payload],
            extra_headers={'Prefer': 'return=representation'},
        )
        return rows[0]

    def patch_listing(self, listing_id: int, payload: dict[str, Any]) -> None:
        self.request(
            'PATCH',
            '/rest/v1/listings',
            params={'id': f'eq.{listing_id}'},
            payload=payload,
            extra_headers={'Prefer': 'return=minimal'},
        )

    def delete_listing(self, listing_id: int) -> None:
        self.request('DELETE', '/rest/v1/listing_media', params={'listing_id': f'eq.{listing_id}'}, extra_headers={'Prefer': 'return=minimal'})
        self.request('DELETE', '/rest/v1/listings', params={'id': f'eq.{listing_id}'}, extra_headers={'Prefer': 'return=minimal'})

    def replace_media(self, listing_id: int, media_rows: list[dict[str, Any]]) -> None:
        self.request('DELETE', '/rest/v1/listing_media', params={'listing_id': f'eq.{listing_id}'}, extra_headers={'Prefer': 'return=minimal'})
        if not media_rows:
            return
        self.request(
            'POST',
            '/rest/v1/listing_media',
            payload=media_rows,
            extra_headers={'Prefer': 'return=minimal'},
        )

    def upload_file(self, local_path: Path, storage_path: str, mime_type: str | None) -> str:
        encoded = '/'.join(quote(part) for part in storage_path.split('/'))
        url = f'{self.url}/storage/v1/object/{STORAGE_BUCKET}/{encoded}'
        headers = dict(self.headers)
        headers['Content-Type'] = mime_type or 'application/octet-stream'
        headers['x-upsert'] = 'true'
        data = local_path.read_bytes()
        last_error: Exception | None = None
        for attempt in range(6):
            try:
                response = requests.post(url, headers=headers, data=data, timeout=600)
                response.raise_for_status()
                return self.public_url(storage_path)
            except Exception as error:  # noqa: BLE001
                last_error = error
                time.sleep(1 + attempt)
        if last_error:
            raise last_error
        raise RuntimeError(f'Не удалось загрузить файл в Storage: {storage_path}')

    def public_url(self, storage_path: str) -> str:
        encoded = '/'.join(quote(part) for part in storage_path.split('/'))
        return f'{self.url}/storage/v1/object/public/{STORAGE_BUCKET}/{encoded}'


def load_env(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        data[key.strip()] = value.strip()
    return data


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def normalize_title(raw: str) -> str:
    return clean_line(raw).strip()


def is_service_text(text: str) -> bool:
    sample = clean_line(text).lower()
    markers = (
        'кто я и почему выгодно бронировать',
        'отзывы гостей',
        'друзья, в этой группе собраны варианты',
        'здесь вы найдёте квартиры',
        'здесь вы найдете квартиры',
        'общение в группе',
    )
    return any(marker in sample for marker in markers)


def is_hotel_object_message(text: str) -> bool:
    if not text:
        return False
    cleaned = clean_line(text)
    if is_service_text(cleaned):
        return False
    if '📍' not in cleaned or '👥' not in cleaned:
        return False
    head = ' '.join(clean_line(line) for line in cleaned.splitlines()[:18])
    if any(marker in head for marker in ('✔', '✔️', 'цены', 'стоимость', '🏖', '🏝')):
        return True
    return False


def is_kvartira_object_message(text: str) -> bool:
    if not text:
        return False
    cleaned = clean_line(text)
    if is_service_text(cleaned):
        return False
    if '📍' not in cleaned:
        return False
    if any(marker in cleaned for marker in ('👥', '🏖', '🏝', '✔', '✔️', 'цены', 'стоимость')):
        return True
    return False


def topic_message_score(text: str) -> float:
    if not text:
        return -1.0
    cleaned = clean_line(text)
    if is_service_text(cleaned):
        return -100.0
    score = 0.0
    if '📍' in cleaned:
        score += 3
    if '🏖' in cleaned or '🏝' in cleaned:
        score += 3
    if '👥' in cleaned:
        score += 2
    if '✔' in cleaned:
        score += 2
    if 'ЦЕН' in cleaned.upper() or 'СТОИМОСТ' in cleaned.upper():
        score += 1
    score += min(len(cleaned) / 120.0, 8)
    return score


def title_key(value: str) -> str:
    return clean_line(value).strip().lower()


def file_sha1(path: Path) -> str:
    hasher = hashlib.sha1()
    with path.open('rb') as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def first_meaningful_line(lines: Iterable[str]) -> str:
    for line in lines:
        cleaned = clean_line(line)
        if cleaned and not should_drop_line(cleaned):
            return cleaned
    return ''


_EXCERPT_GPS_RE = re.compile(
    r"\s*[.;]?\s*Координаты\s*:?\s*\d[\d.\s]*\s*,\s*\d[\d.\s]*",
    re.I,
)


def _strip_excerpt_gps_clause(text: str) -> str:
    """Убирает «Координаты: …» из первой строки описания (не дублировать в лиде карточки)."""
    if not text:
        return text
    t = _EXCERPT_GPS_RE.sub("", text)
    return re.sub(r"\s{2,}", " ", t).strip(" ,.;")


def build_excerpt(parsed: dict[str, Any]) -> str:
    for section in parsed.get('sections', []):
        line = first_meaningful_line(section.get('lines', []))
        if line:
            return _strip_excerpt_gps_clause(line)
    return summary_text(parsed.get('location', ''), parsed.get('beach', ''), parsed.get('capacity', ''))


def local_to_public_path(local_path: Path) -> str:
    rel = local_path.relative_to(ROOT).as_posix()
    return f'/{rel}'


def upload_local_image_public_url(supa: SupabaseClient, local_path: Path, storage_path: str) -> str:
    """
    Загрузка JPEG/WebP PNG в bucket; при ошибке или SKIP_IMAGE_UPLOAD_TO_SUPABASE — URL как /media/... в репо.
    """
    if SKIP_IMAGE_UPLOAD_TO_SUPABASE:
        return local_to_public_path(local_path)
    mime = mimetypes.guess_type(local_path.name)[0] or 'image/jpeg'
    try:
        return supa.upload_file(local_path, storage_path, mime)
    except Exception as error:  # noqa: BLE001
        print(
            f'[warn] Не удалось загрузить фото в Storage ({storage_path}): {error} — используем локальный путь.',
            flush=True,
        )
        return local_to_public_path(local_path)


def resolve_ffmpeg_binary() -> str | None:
    path = shutil.which('ffmpeg')
    if path:
        return path
    try:
        import imageio_ffmpeg  # type: ignore
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001
        return None


FFMPEG_BIN = resolve_ffmpeg_binary()


def transcode_video(source: Path, target: Path, bitrate: str) -> bool:
    if not FFMPEG_BIN:
        return False
    ensure_dir(target.parent)
    cmd = [
        FFMPEG_BIN,
        '-y',
        '-i',
        str(source),
        '-vf',
        f"scale='min({VIDEO_MAX_WIDTH},iw)':-2",
        '-c:v',
        'libx264',
        '-preset',
        'veryfast',
        '-b:v',
        bitrate,
        '-maxrate',
        bitrate,
        '-bufsize',
        f'{int(bitrate[:-1]) * 2}k',
        '-pix_fmt',
        'yuv420p',
        '-movflags',
        '+faststart',
        '-c:a',
        'aac',
        '-b:a',
        '96k',
        str(target),
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return target.exists() and target.stat().st_size > 0
    except Exception:  # noqa: BLE001
        return False


def cleanup_large_source_file(source_file: Path, chosen_file: Path) -> None:
    """Удаляем тяжёлый source.mp4 после успешной загрузки web-варианта.

    Это защищает репозиторий от случайного попадания файлов >100MB в коммит.
    """
    try:
        if source_file == chosen_file:
            return
        if not source_file.exists():
            return
        limit_bytes = MAX_LOCAL_SOURCE_KEEP_MB * 1024 * 1024
        if source_file.stat().st_size > limit_bytes:
            source_file.unlink()
    except Exception:
        return


def render_paragraph_block(lines: list[str]) -> str:
    return render_paragraph_lines_html(lines)


def _section_heading_markup(label: str) -> str:
    t = (label or '').strip()
    if not t or t.casefold() == 'обзор':
        return ''
    return f'          <h2>{html.escape(t)}</h2>\n'


def render_sections_html(sections: list[dict[str, Any]], parsed: dict[str, Any] | None = None) -> str:
    parts: list[str] = []
    for section in sections:
        lines = list(section.get('lines', []))
        block = render_paragraph_block(lines)
        if not block:
            continue
        heading = _section_heading_markup(str(section.get('label', '')))
        parts.append(
            f'''      <section class="section hotel-site-concept__detail-section">\n        <article class="card">\n{heading}          <div class="paragraph-blocks">\n{block}\n          </div>\n        </article>\n      </section>'''
        )
    return ''.join(parts)


def _normalize_prices_payload(prices: Any) -> list[dict[str, str]]:
    """Приводит цены из поста/БД к единому списку {kind, text} (строки в БД — legacy)."""
    out: list[dict[str, str]] = []
    raw_list = prices if isinstance(prices, list) else []
    for item in raw_list:
        if isinstance(item, str):
            t = item.strip()
            if not t or should_drop_line(t):
                continue
            kind = 'note' if t.startswith(('(', '（')) else 'price'
            out.append({'kind': kind, 'text': item})
            continue
        if isinstance(item, dict):
            kind = str(item.get('kind') or 'price')
            text_raw = item.get('text') if item.get('text') is not None else item.get('label')
            text = str(text_raw or '').strip()
            if not text or should_drop_line(text):
                continue
            if kind == 'heading':
                out.append({'kind': 'heading', 'text': text})
            elif kind == 'note':
                out.append({'kind': 'note', 'text': str(item.get('text') or text)})
            else:
                out.append({'kind': 'price', 'text': text})
    return out


def render_prices_html(prices: Any) -> str:
    norm = _normalize_prices_payload(prices)
    if not norm:
        return ''

    has_heading = any(e['kind'] == 'heading' for e in norm)

    mod = _apply_design_mod()
    fmt = mod.format_price_line_to_html

    def seasons_ul(lines: list[str]) -> str:
        lis = '\n'.join(f'            <li>{fmt(line)}</li>' for line in lines)
        return f'          <ul class="price-card__seasons">\n{lis}\n          </ul>'

    def notes_ul(note_lines: list[str]) -> str:
        if not note_lines:
            return ''
        nitems = '\n'.join(f'            <li>{fmt(n)}</li>' for n in note_lines)
        return (
            f'\n          <ul class="price-card__notes" aria-label="Особые условия">\n{nitems}\n          </ul>'
        )

    if not has_heading:
        price_lines = [e['text'] for e in norm if e['kind'] == 'price']
        note_lines = [e['text'] for e in norm if e['kind'] == 'note']
        if not price_lines:
            return ''
        notes_part = notes_ul(note_lines)
        return (
            f'''      <section class="section hotel-price-section hotel-site-concept__detail-section">\n'''
            f'''        <article class="card price-card">\n'''
            f'''          <h2 class="price-card__heading">ЦЕНЫ:</h2>\n'''
            f'''{seasons_ul(price_lines)}{notes_part}\n'''
            f'''        </article>\n'''
            f'''      </section>'''
        )

    groups: list[tuple[str, list[str]]] = []
    notes: list[str] = []
    bucket: list[str] = []
    current_label: str | None = None

    def flush_bucket() -> None:
        nonlocal current_label, bucket
        if not bucket:
            return
        groups.append((current_label or '', bucket[:]))
        bucket = []

    for entry in norm:
        kind, text = entry['kind'], entry['text']
        if kind == 'heading':
            flush_bucket()
            current_label = text
            continue
        if kind == 'note':
            notes.append(text)
            continue
        bucket.append(text)
    flush_bucket()

    body_chunks: list[str] = ['          <h2 class="price-card__heading">ЦЕНЫ:</h2>']
    for label, lines in groups:
        if not lines:
            continue
        ul = seasons_ul(lines)
        if label:
            body_chunks.append(
                f'          <div class="price-card__tariff-group">\n'
                f'            <h3 class="price-card__group">{html.escape(label)}</h3>\n'
                f'{ul}\n          </div>'
            )
        else:
            body_chunks.append(ul)

    inner = '\n'.join(body_chunks) + notes_ul(notes)
    return (
        f'''      <section class="section hotel-price-section hotel-site-concept__detail-section">\n'''
        f'''        <article class="card price-card">\n{inner}\n        </article>\n'''
        f'''      </section>'''
    )


def render_reviews_html(seed: int) -> str:
    return render_reviews(seed)


def human_lead(parsed: dict[str, Any]) -> str:
    lead = summary_text(parsed.get('location', ''), parsed.get('beach', ''), parsed.get('capacity', ''))
    excerpt = build_excerpt(parsed)
    if excerpt and excerpt != lead:
        return f'{lead} {excerpt}'
    return lead


def build_top_meta_lines(parsed: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    location = str(parsed.get('location') or '').strip()
    beach = str(parsed.get('beach') or '').strip()
    capacity = str(parsed.get('capacity') or '').strip()
    if location:
        lines.append(f'📍 {location}')
    if beach:
        lines.append(f'🏖️ {beach}')
    if capacity:
        lines.append(f'👥 {capacity}')
    return lines


def render_media_items(media_items: list[dict[str, Any]], title: str) -> str:
    parts: list[str] = []
    image_index = 1
    video_index = 1
    for item in media_items:
        if item['kind'] == 'photo':
            parts.append(f'            <img src="{html.escape(item["source_url"])}" alt="{html.escape(title)} фото {image_index}" loading="lazy" />')
            image_index += 1
        else:
            source_url = str(item.get('source_url') or '').strip()
            telegram_post = str(item.get('telegram_post') or '').strip()
            if source_url and source_url.startswith('http') and not telegram_post:
                parts.append(
                    f'''            <video class="local-video" controls preload="metadata" playsinline>\n              <source src="{html.escape(source_url)}" type="video/mp4" />\n            </video>'''
                )
            elif telegram_post:
                parts.append(
                    f'''            <div class="video-embed video-embed--telegram">\n              <script async src="https://telegram.org/js/telegram-widget.js?22" data-telegram-post="{html.escape(telegram_post)}" data-width="100%" data-userpic="false" data-single="1"></script>\n            </div>'''
                )
            video_index += 1
    return '\n'.join(parts)


def render_top_gallery(media_items: list[dict[str, Any]], title: str) -> str:
    photos = [item for item in media_items if item['kind'] == 'photo']
    if not photos:
        return ''
    main = photos[0]
    thumbs = ''.join(
        f'<img src="{html.escape(item["source_url"])}" alt="{html.escape(title)} фото {index + 2}" loading="lazy" />'
        for index, item in enumerate(photos[1:4])
    )
    return f'''          <div class="hotel-card__gallery">\n            <div class="hotel-card__main-photo">\n              <img src="{html.escape(main["source_url"])}" alt="{html.escape(title)} фото 1" loading="eager" />\n              <div class="hotel-card__floating">\n                <span class="pill pill--accent">Проверенный объект</span>\n              </div>\n            </div>\n            <div class="hotel-card__thumbs">\n              {thumbs}\n            </div>\n          </div>'''


def render_detail_page(source_kind: str, slug: str, telegram_url: str, date_text: str, parsed: dict[str, Any], media_items: list[dict[str, Any]], page_href: str) -> str:
    _ = date_text
    title = normalize_title(parsed.get('title', '')).upper()
    lead = human_lead(parsed)
    description = build_excerpt(parsed)
    sections = parsed.get('sections', [])
    prices = parsed.get('prices', [])
    mod = _apply_design_mod()
    lead_text = mod.format_lead_text(lead)
    lead_lines = [mod.clean_text(part) for part in re.split(r'[•\n]', lead_text) if mod.clean_text(part)]
    city_badge = mod.short_location_badge(lead_lines, title)
    top_meta_lines = build_top_meta_lines(parsed)
    if top_meta_lines:
        top_meta_html = '<br>'.join(html.escape(line) for line in top_meta_lines[:3])
        location_html = f'<p class="location">{top_meta_html}</p>'
    else:
        location_html = (
            f'<p class="location">{html.escape(lead_text)}</p>'
            if mod.should_show_location_under_title(lead_text, description)
            else ''
        )
    reviews_panel = _reviews_panel_for_slug(mod, slug)
    top_gallery = render_top_gallery(media_items, title)
    media_html = render_media_items(media_items, title)
    why_lines = sections[0]['lines'][:3] if sections else []
    important_lines = sections[1]['lines'][:3] if len(sections) > 1 else []
    why_html = ''.join(f'<li>{html.escape(line)}</li>' for line in why_lines if not should_drop_line(line))
    important_html = ''.join(f'<li>{html.escape(line)}</li>' for line in important_lines if not should_drop_line(line))
    if source_kind == 'kvartira':
        eyebrow_link = '<a href="/kvartira/"><strong>Каталог квартир</strong></a>'
        save_href = '/kvartira/'
        save_label = 'К каталогу квартир'
    else:
        eyebrow_link = '<a href="/"><strong>Каталог Абхазберег</strong></a>'
        save_href = '/'
        save_label = 'К каталогу'
    page_title_suffix = 'обзор, фото, видео и цены'
    summary = summary_text(parsed.get('location', ''), parsed.get('beach', ''), parsed.get('capacity', ''))
    def absolute_site_url(raw: str) -> str:
        value = (raw or '').strip()
        if not value:
            return ''
        if value.startswith('http://') or value.startswith('https://'):
            return value
        if value.startswith('/'):
            return f'https://абхазберег.рф{value}'
        return f'https://абхазберег.рф/{value}'

    first_photo_url = next(
        (
            str(item.get('source_url') or '').strip()
            for item in media_items
            if item.get('kind') == 'photo' and str(item.get('source_url') or '').strip()
        ),
        '',
    )
    og_image = absolute_site_url(first_photo_url or '/media/branding/site-cover.jpg')
    return f'''<!doctype html>
<html lang="ru">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{html.escape(title)} — {page_title_suffix}</title>
    <meta name="description" content="{html.escape(summary)}" />
    <meta name="robots" content="index, follow, max-image-preview:large" />
    <link rel="canonical" href="https://абхазберег.рф{page_href}" />
    <meta property="og:type" content="article" />
    <meta property="og:title" content="{html.escape(title)} — обзор и цены" />
    <meta property="og:description" content="{html.escape(summary)}" />
    <meta property="og:url" content="https://абхазберег.рф{page_href}" />
    <meta property="og:image" content="{og_image}" />
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;700;800&family=Prata&display=swap" rel="stylesheet" />
    <link rel="stylesheet" href="../../styles.css" />
  </head>
  <body>
    <div class="grain" aria-hidden="true"></div>
    <main class="hotel-site-concept">
      <div class="card-preview-page__halo card-preview-page__halo--mint" aria-hidden="true"></div>
      <div class="card-preview-page__halo card-preview-page__halo--sand" aria-hidden="true"></div>

      <section class="hotel-site-concept__intro">
        <div class="hotel-site-concept__intro-brand">
          <p class="eyebrow">{eyebrow_link}</p>
          <p class="hotel-site-concept__intro-subline">онлайн-бронирование без накруток</p>
        </div>
      </section>

      <article class="hotel-card hotel-site-concept__card">
{top_gallery}
        <div class="hotel-card__content">
          <div class="hotel-card__topline">
            <div class="hotel-card__rating">
              <span class="hotel-card__rating-label">Локация объекта</span>
              <strong class="hotel-card__rating-summary">{html.escape(city_badge)}</strong>
            </div>
            <a class="save-button" href="{html.escape(save_href)}">{html.escape(save_label)}</a>
          </div>

          <div class="hotel-card__header">
            <div class="hotel-card__header-main">
              <h2>{html.escape(title)}</h2>
              {location_html}
            </div>
            <div class="partner-badge">
              <span>Abhazbereg</span>
              <strong>Проверено</strong>
            </div>
          </div>

          <div class="benefit-grid">
            <article>
              <strong>Почему выбирают</strong>
              <ul>{why_html}</ul>
            </article>
            <article>
              <strong>Важно для гостя</strong>
              <ul>{important_html}</ul>
            </article>
          </div>

          <div class="hotel-card__footer">
            <div class="hotel-card__actions">
              <a class="button button--ghost" href="#contacts">Что-то нужно уточнить?</a>
              <a class="button button--accent" href="#contacts">Написать мне</a>
            </div>
          </div>

          {reviews_panel}
        </div>
      </article>

      <div class="hotel-site-concept__detail-grid" id="details">
        <div class="hotel-site-concept__detail-main">
          <section class="section hotel-media-section hotel-site-concept__detail-section">
            <article class="card">
              <h2>Фото и видео</h2>
              <div class="media-grid">
{media_html}
              </div>
            </article>
          </section>
{render_sections_html(sections, parsed)}
        </div>
        <aside class="hotel-site-concept__detail-aside">
{render_prices_html(prices)}
{FAQ_BLOCK}
{CONTACT_BLOCK}
        </aside>
      </div>
    </main>
    <script src="../../scripts.js" defer></script>
  </body>
</html>'''


def parse_city_value(location: str) -> str:
    city = city_label(location)
    return city if city != 'Абхазия' else ''


def storage_kind_prefix(source_kind: str) -> str:
    return 'hotels' if source_kind == 'hotel' else 'kvartira'


def copy_cover(first_photo: Path, source_kind: str, slug: str) -> Path:
    if source_kind == 'hotel':
        cover_path = CARD_DIR / f'{slug}.jpg'
    else:
        cover_path = KV_CARD_DIR / f'{slug}-cover.jpg'
    ensure_dir(cover_path.parent)
    shutil.copyfile(first_photo, cover_path)
    return cover_path


def listing_payload(source_kind: str, row_id: int | None, slug: str, source_message_id: int, source_topic_id: int | None, title: str, summary: str, excerpt: str, parsed: dict[str, Any], page_url: str, telegram_url: str, published_at: str, has_video: bool, cover_url: str, page_path: Path) -> dict[str, Any]:
    payload = {
        'source_kind': source_kind,
        'source_channel': 'abhkvartira' if source_kind == 'kvartira' else 'abhazbooking',
        'source_message_id': source_message_id,
        'source_topic_id': source_topic_id,
        'slug': slug,
        'title': title,
        'summary': summary,
        'excerpt': excerpt,
        'city': parse_city_value(parsed.get('location', '')),
        'location_text': parsed.get('location', ''),
        'distance_text': parsed.get('beach', ''),
        'beach_text': parsed.get('beach', ''),
        'capacity_text': parsed.get('capacity', ''),
        'page_url': page_url,
        'telegram_url': telegram_url,
        'published_at': published_at,
        'has_video': has_video,
        'cover_url': cover_url,
        'is_active': True,
        'details': {
            'lead': summary,
            'sections': parsed.get('sections', []),
            'prices': parsed.get('prices', []),
            'page_path': str(page_path),
        },
    }
    # Фильтры задаются только из Google Sheets «СОЦСЕТИ» (apply_all_filters_from_sheet.py).
    payload['details']['filters'] = {k: list(v) for k, v in EMPTY_FILTERS.items()}
    if row_id is not None:
        payload['id'] = row_id
    return payload


def media_row(listing_id: int, media_role: str, sort_order: int, mime_type: str, source_url: str, storage_path: str, public_url: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        'listing_id': listing_id,
        'media_role': media_role,
        'sort_order': sort_order,
        'mime_type': mime_type,
        'source_url': source_url,
        'storage_bucket': STORAGE_BUCKET,
        'storage_path': storage_path,
        'public_url': public_url,
        'details': details or {},
    }


async def download_message_media(client: TelegramClient, message, destination: Path) -> Path | None:
    ensure_dir(destination.parent)
    if destination.exists() and destination.stat().st_size > 0 and not FORCE_MEDIA_REFRESH:
        try:
            head = destination.read_bytes()[:80]
            is_lfs_pointer = head.startswith(b'version https://git-lfs.github.com/spec/v1')
        except OSError:
            is_lfs_pointer = False
        if not is_lfs_pointer:
            return destination
        try:
            destination.unlink()
        except OSError:
            pass
    try:
        result = await client.download_media(message, file=str(destination))
    except FileReferenceExpiredError:
        chat = await message.get_input_chat()
        refreshed = await client.get_messages(chat, ids=message.id)
        if not refreshed:
            return None
        try:
            result = await client.download_media(refreshed, file=str(destination))
        except Exception as error:  # noqa: BLE001
            print(
                f'[warn] Не удалось скачать media msg={message.id} -> {destination.name}: {error}',
                flush=True,
            )
            return None
    except Exception as error:  # noqa: BLE001
        print(
            f'[warn] Не удалось скачать media msg={message.id} -> {destination.name}: {error}',
            flush=True,
        )
        return None
    if not result:
        return None
    return Path(result)


def local_media_entry(source_kind: str, local_path: Path) -> tuple[str, str]:
    public_url = local_to_public_path(local_path)
    if source_kind == 'hotel':
        storage_path = f'hotels/{local_path.parent.name}/{local_path.name}' if local_path.parent.name != 'cards' else f'cards/{local_path.name}'
    else:
        if 'kvartira-cards' in local_path.parts:
            storage_path = f'kvartira-cards/{local_path.name}'
        else:
            storage_path = f'kvartira/{local_path.parent.name}/{local_path.name}'
    return storage_path, public_url


async def collect_hotel_messages(client: TelegramClient) -> list[Any]:
    entity = await client.get_entity('abhazbooking')
    result = []
    async for msg in client.iter_messages(entity, reverse=True):
        if not msg.date:
            continue
        if msg.date.date().isoformat() < CUTOFF_DATE:
            continue
        result.append(msg)
    return result


async def _hotel_album_media_messages(
    client: TelegramClient,
    entity: Any,
    canonical: Any,
    *,
    channel_messages: list[Any] | None,
) -> list[Any]:
    """Собирает сообщения одного альбома: из полного списка канала или узким окном по id."""
    if not getattr(canonical, 'grouped_id', None) or not canonical.grouped_id:
        return [canonical] if canonical.media else []
    gid = canonical.grouped_id
    if channel_messages is not None:
        media_messages = [msg for msg in channel_messages if msg.grouped_id == gid and msg.media]
        return sorted(media_messages, key=lambda item: item.id)
    window = 80
    min_id = max(1, canonical.id - window)
    max_id = canonical.id + window
    found: list[Any] = []
    async for m in client.iter_messages(entity, min_id=min_id, max_id=max_id):
        if m.grouped_id == gid and m.media:
            found.append(m)
    if not found and canonical.media:
        return [canonical]
    return sorted(found, key=lambda item: item.id)


async def build_hotel_objects(client: TelegramClient) -> list[dict[str, Any]]:
    entity = await client.get_entity('abhazbooking')
    if TARGET_HOTEL_SOURCE_IDS:
        ids_sorted = sorted(TARGET_HOTEL_SOURCE_IDS)
        print(
            f'[info] Точечный режим отелей: get_messages по id ({len(ids_sorted)} шт.), без полного скана канала.',
            flush=True,
        )
        raw_list = await client.get_messages(entity, ids=ids_sorted)
        result: list[dict[str, Any]] = []
        for req_id, canonical in zip(ids_sorted, raw_list):
            if canonical is None:
                print(f'[warn] Сообщение отеля id={req_id} не найдено в канале.', flush=True)
                continue
            if canonical.date and canonical.date.date().isoformat() < CUTOFF_DATE:
                if req_id not in TARGET_HOTEL_SOURCE_IDS:
                    print(
                        f'[warn] Сообщение отеля id={req_id} старше CUTOFF_DATE={CUTOFF_DATE}, пропуск.',
                        flush=True,
                    )
                    continue
                print(
                    f'[info] Сообщение отеля id={req_id} старше CUTOFF_DATE={CUTOFF_DATE}, но включено по TARGET_HOTEL_SOURCE_IDS.',
                    flush=True,
                )
            text = canonical.message or ''
            if not is_hotel_object_message(text) and req_id not in TARGET_HOTEL_SOURCE_IDS:
                continue
            if not is_hotel_object_message(text) and req_id in TARGET_HOTEL_SOURCE_IDS:
                print(
                    f'[info] Сообщение id={req_id} принято по TARGET (не проходит типичные маркеры отеля).',
                    flush=True,
                )
            media_messages = await _hotel_album_media_messages(
                client, entity, canonical, channel_messages=None
            )
            result.append({
                'source_kind': 'hotel',
                'canonical': canonical,
                'media_messages': media_messages,
                'published_at': canonical.date.date().isoformat(),
                'telegram_url': f'https://t.me/abhazbooking/{canonical.id}',
                'parsed': parse_post(text),
            })
        return result

    messages = await collect_hotel_messages(client)
    candidates = [msg for msg in messages if is_hotel_object_message(msg.message or '')]
    result = []
    for canonical in candidates:
        if canonical.grouped_id:
            media_messages = [msg for msg in messages if msg.grouped_id == canonical.grouped_id and msg.media]
        else:
            media_messages = [canonical] if canonical.media else []
        result.append({
            'source_kind': 'hotel',
            'canonical': canonical,
            'media_messages': sorted(media_messages, key=lambda item: item.id),
            'published_at': canonical.date.date().isoformat(),
            'telegram_url': f'https://t.me/abhazbooking/{canonical.id}',
            'parsed': parse_post(canonical.message or ''),
        })
    return result


async def fetch_topic_messages(client: TelegramClient, entity, topic_id: int) -> list[Any]:
    result = []
    async for msg in client.iter_messages(entity, reply_to=topic_id):
        result.append(msg)
    result.sort(key=lambda item: item.id)
    return result


async def build_kvartira_objects(client: TelegramClient) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    entity = await client.get_entity('abhkvartira')
    topics: list[Any] = []
    if TARGET_KV_TOPIC_IDS:
        ids_sorted = sorted(TARGET_KV_TOPIC_IDS)
        peer = await client.get_input_entity(entity)
        print(
            f'[info] Точечный режим квартир: GetForumTopicsByID ({len(ids_sorted)} тем), без полного списка форума.',
            flush=True,
        )
        response = await client(
            message_functions.GetForumTopicsByIDRequest(peer=peer, topics=ids_sorted)
        )
        topics = list(response.topics)
        found_ids = {t.id for t in topics}
        for tid in ids_sorted:
            if tid not in found_ids:
                print(
                    f'[warn] Тема форума id={tid} не вернулась из GetForumTopicsByID (нет доступа или неверный id).',
                    flush=True,
                )
    else:
        offset_date = None
        offset_id = 0
        offset_topic = 0
        while True:
            response = await client(message_functions.GetForumTopicsRequest(peer=entity, offset_date=offset_date, offset_id=offset_id, offset_topic=offset_topic, limit=100, q=None))
            if not response.topics:
                break
            topics.extend(response.topics)
            if len(response.topics) < 100:
                break
            last = response.topics[-1]
            offset_date = last.date
            offset_id = last.id
            offset_topic = last.id

    objects = []
    topic_dump = []
    for topic in topics:
        topic_dump.append({'topic_id': topic.id, 'title': topic.title, 'top_message_id': topic.top_message})
        if topic.id == 1 or clean_line(topic.title).lower() == 'general':
            continue
        if TARGET_KV_TOPIC_IDS and topic.id not in TARGET_KV_TOPIC_IDS:
            continue
        thread_messages = await fetch_topic_messages(client, entity, topic.id)
        text_candidates = [msg for msg in thread_messages if is_kvartira_object_message(msg.message or '')]
        if not text_candidates:
            text_candidates = [msg for msg in thread_messages if msg.message and not is_service_text(msg.message)]
        if (
            not text_candidates
            and TARGET_KV_TOPIC_IDS
            and topic.id in TARGET_KV_TOPIC_IDS
        ):
            text_candidates = [msg for msg in thread_messages if msg.message]
        if not text_candidates:
            continue
        canonical = max(text_candidates, key=lambda item: (topic_message_score(item.message or ''), item.id))
        if canonical.grouped_id:
            media_messages = [msg for msg in thread_messages if msg.grouped_id == canonical.grouped_id and msg.media]
        else:
            media_messages = [canonical] if canonical.media else []
        objects.append({
            'source_kind': 'kvartira',
            'topic_id': topic.id,
            'topic_title': topic.title,
            'canonical': canonical,
            'media_messages': sorted(media_messages, key=lambda item: item.id),
            'published_at': canonical.date.date().isoformat(),
            'telegram_url': f'https://t.me/abhkvartira/{canonical.id}',
            'parsed': parse_post(canonical.message or ''),
        })
    return objects, topic_dump


def cleanup_removed_listing(source_kind: str, listing: dict[str, Any], supa: SupabaseClient) -> None:
    page_url = listing.get('page_url') or ''
    local_path = None
    if page_url:
        try:
            path = page_url.split('https://абхазберег.рф', 1)[-1].strip('/')
            if path:
                local_path = ROOT / path / 'index.html'
        except Exception:
            local_path = None
    if local_path and local_path.exists():
        shutil.rmtree(local_path.parent, ignore_errors=True)
    if source_kind == 'hotel':
        shutil.rmtree(HOTEL_MEDIA_DIR / listing['slug'], ignore_errors=True)
        cover = CARD_DIR / f"{listing['slug']}.jpg"
        if cover.exists():
            cover.unlink()
    else:
        shutil.rmtree(KV_MEDIA_DIR / listing['slug'], ignore_errors=True)
        cover = KV_CARD_DIR / f"{listing['slug']}-cover.jpg"
        if cover.exists():
            cover.unlink()
    supa.delete_listing(listing['id'])


async def materialize_object(client: TelegramClient, supa: SupabaseClient, existing_listing: dict[str, Any] | None, object_data: dict[str, Any], slug_pool: set[str]) -> dict[str, Any]:
    source_kind = object_data['source_kind']
    canonical = object_data['canonical']
    parsed = object_data['parsed']
    media_messages = object_data['media_messages']
    title = normalize_title(parsed.get('title') or object_data.get('topic_title') or '')
    if existing_listing:
        slug = existing_listing['slug']
    else:
        slug = build_slug(title, canonical.id, slug_pool)
        slug_pool.add(slug)

    gallery_dir = HOTEL_MEDIA_DIR / slug if source_kind == 'hotel' else KV_MEDIA_DIR / slug
    ensure_dir(gallery_dir)
    ensure_dir(VIDEOS_DIR)

    media_payload: list[dict[str, Any]] = []
    local_media_items: list[dict[str, Any]] = []
    photo_paths: list[Path] = []
    photo_hashes: set[str] = set()
    video_hashes: set[str] = set()
    photo_count = 0
    video_count = 0
    media_sort = 0
    for msg in media_messages:
        if msg.photo or (msg.file and str(getattr(msg.file, 'mime_type', '')).startswith('image/')):
            photo_count += 1
            media_sort += 1
            photo_path = gallery_dir / f'photo-{photo_count:02d}.jpg'
            downloaded = await download_message_media(client, msg, photo_path)
            if not downloaded:
                photo_count -= 1
                continue
            if downloaded != photo_path:
                shutil.move(str(downloaded), photo_path)
            photo_hash = file_sha1(photo_path)
            if photo_hash in photo_hashes:
                try:
                    photo_path.unlink()
                except Exception:
                    pass
                photo_count -= 1
                continue
            photo_hashes.add(photo_hash)
            photo_paths.append(photo_path)
            storage_path, _legacy_public = local_media_entry(source_kind, photo_path)
            public_url = upload_local_image_public_url(supa, photo_path, storage_path)
            local_media_items.append({'kind': 'photo', 'source_url': public_url, 'public_url': public_url, 'telegram_url': object_data['telegram_url']})
            media_payload.append(media_row(existing_listing['id'] if existing_listing else 0, 'gallery', media_sort, 'image/jpeg', public_url, storage_path, public_url))
        elif msg.video or (msg.file and str(getattr(msg.file, 'mime_type', '')).startswith('video/')):
            video_count += 1
            media_sort += 1
            telegram_url = f'https://t.me/{"abhkvartira" if source_kind == "kvartira" else "abhazbooking"}/{msg.id}'
            telegram_post = telegram_url.replace('https://t.me/', '')
            video_dir = VIDEOS_DIR / storage_kind_prefix(source_kind) / slug
            ensure_dir(video_dir)
            source_file = video_dir / f'video-{video_count:02d}-source.mp4'
            downloaded = await download_message_media(client, msg, source_file)
            if not downloaded:
                continue
            if downloaded != source_file:
                shutil.move(str(downloaded), source_file)
            video_hash = file_sha1(source_file)
            if video_hash in video_hashes:
                try:
                    source_file.unlink()
                except Exception:
                    pass
                continue
            video_hashes.add(video_hash)

            uploaded_public_url = ''
            uploaded_storage_path = ''
            chosen_file = source_file
            chosen_details = {'telegram_post': telegram_post, 'telegram_url': telegram_url}
            max_bytes = MAX_VIDEO_UPLOAD_MB * 1024 * 1024

            def try_upload(candidate: Path) -> bool:
                nonlocal uploaded_public_url, uploaded_storage_path, chosen_file
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
                chosen_file = candidate
                return True

            # 1) Пытаемся загрузить исходник как есть (самый быстрый путь).
            _ = try_upload(source_file)

            # 2) Если не вышло (обычно из-за размера), понижаем битрейт и пробуем снова.
            if not uploaded_public_url and FFMPEG_BIN:
                for bitrate in VIDEO_BITRATES:
                    candidate = video_dir / f'video-{video_count:02d}-{bitrate}.mp4'
                    if not candidate.exists() or candidate.stat().st_size == 0:
                        ok = transcode_video(source_file, candidate, bitrate)
                        if not ok:
                            continue
                    if try_upload(candidate):
                        break

            if uploaded_public_url:
                cleanup_large_source_file(source_file, chosen_file)
                local_media_items.append(
                    {
                        'kind': 'video',
                        'source_url': uploaded_public_url,
                        'public_url': uploaded_public_url,
                        'telegram_url': telegram_url,
                    }
                )
                media_payload.append(
                    media_row(
                        existing_listing['id'] if existing_listing else 0,
                        'gallery',
                        media_sort,
                        'video/mp4',
                        uploaded_public_url,
                        uploaded_storage_path,
                        uploaded_public_url,
                        chosen_details,
                    )
                )
            else:
                print(
                    f'[warn] Не удалось загрузить видео в Storage для {slug} (msg={msg.id}), оставляю Telegram-embed',
                    flush=True,
                )
                local_media_items.append({'kind': 'video', 'source_url': telegram_url, 'public_url': '', 'telegram_url': telegram_url, 'telegram_post': telegram_post})
                media_payload.append(
                    media_row(
                        existing_listing['id'] if existing_listing else 0,
                        'gallery',
                        media_sort,
                        'application/x-telegram-embed',
                        telegram_url,
                        '',
                        '',
                        {'telegram_post': telegram_post},
                    )
                )

    if not photo_paths and existing_listing and existing_listing.get('cover_url'):
        cover_public = existing_listing['cover_url']
        cover_local = ''
    else:
        first_photo = photo_paths[0] if photo_paths else None
        cover_public = existing_listing.get('cover_url', '') if existing_listing else ''
        cover_local = ''
        if first_photo:
            cover_path = copy_cover(first_photo, source_kind, slug)
            cover_storage, _legacy_cover = local_media_entry(source_kind, cover_path)
            cover_public = upload_local_image_public_url(supa, cover_path, cover_storage)
            cover_local = cover_public
            media_payload.insert(
                0,
                media_row(existing_listing['id'] if existing_listing else 0, 'card', 0, 'image/jpeg', cover_public, cover_storage, cover_public),
            )

    if source_kind == 'hotel':
        page_dir = HOTELS_DIR / slug
        page_href = f'/hotels/{slug}/'
    else:
        page_dir = KVARTIRA_DIR / slug
        page_href = f'/kvartira/{slug}/'
    ensure_dir(page_dir)
    page_path = page_dir / 'index.html'

    summary = summary_text(parsed.get('location', ''), parsed.get('beach', ''), parsed.get('capacity', ''))
    excerpt = build_excerpt(parsed)
    html_page = render_detail_page(source_kind, slug, object_data['telegram_url'], object_data['published_at'], parsed, local_media_items, page_href)
    page_path.write_text(html_page, encoding='utf-8')

    payload = listing_payload(
        source_kind=source_kind,
        row_id=existing_listing['id'] if existing_listing else None,
        slug=slug,
        source_message_id=canonical.id,
        source_topic_id=object_data.get('topic_id'),
        title=title,
        summary=summary,
        excerpt=excerpt,
        parsed=parsed,
        page_url=f'https://абхазберег.рф{page_href}',
        telegram_url=object_data['telegram_url'],
        published_at=object_data['published_at'],
        has_video=any(item['kind'] == 'video' for item in local_media_items),
        cover_url=cover_public,
        page_path=page_path,
    )

    if existing_listing:
        prev_details = existing_listing.get('details') if isinstance(existing_listing.get('details'), dict) else {}
        prev_filters = prev_details.get('filters')
        if isinstance(prev_filters, dict) and prev_filters:
            details = payload.get('details')
            if isinstance(details, dict):
                details['filters'] = {gk: list(gv) if isinstance(gv, list) else gv for gk, gv in prev_filters.items()}

    if existing_listing:
        supa.patch_listing(existing_listing['id'], {k: v for k, v in payload.items() if k != 'id'})
        listing_id = existing_listing['id']
    else:
        listing_id = supa.insert_listing({k: v for k, v in payload.items() if k != 'id'})['id']

    for row in media_payload:
        row['listing_id'] = listing_id
    supa.replace_media(listing_id, media_payload)

    return {
        'id': listing_id,
        'slug': slug,
        'title': title,
        'source_id': canonical.id,
        'topic_id': object_data.get('topic_id'),
        'page_url': f'https://абхазберег.рф{page_href}',
        'telegram_url': object_data['telegram_url'],
        'has_video': any(item['kind'] == 'video' for item in local_media_items),
        'cover_local': cover_local,
        'summary': summary,
        'excerpt': excerpt,
    }


async def main() -> None:
    env = load_env(ENV_FILE)
    supa = SupabaseClient(url=env['SUPABASE_URL'].rstrip('/'), service_key=env['SUPABASE_SERVICE_ROLE_KEY'])
    ensure_dir(OUTPUT_DIR)
    ensure_dir(KV_CARD_DIR)
    ensure_dir(CARD_DIR)

    client = TelegramClient(SESSION, API_ID, API_HASH, receive_updates=False)
    await client.connect()

    run_hotels = True
    run_kvartira = True
    if TARGET_HOTEL_SOURCE_IDS and not TARGET_KV_TOPIC_IDS:
        run_kvartira = False
    elif TARGET_KV_TOPIC_IDS and not TARGET_HOTEL_SOURCE_IDS:
        run_hotels = False

    hotel_objects: list[dict[str, Any]] = []
    kvartira_objects: list[dict[str, Any]] = []
    topic_dump: list[dict[str, Any]] = []
    if run_hotels:
        hotel_objects = await build_hotel_objects(client)
    if run_kvartira:
        kvartira_objects, topic_dump = await build_kvartira_objects(client)
    print(f'Найдено объектов: hotels={len(hotel_objects)}, kvartira={len(kvartira_objects)}', flush=True)
    if TARGET_SYNC_MODE:
        print('[info] Включен точечный режим синка: удаление неактивных объектов отключено.', flush=True)

    existing_hotels = supa.fetch_listings('hotel') if run_hotels else []
    existing_kvartira = supa.fetch_listings('kvartira') if run_kvartira else []

    kvartira_by_topic = {row.get('source_topic_id'): row for row in existing_kvartira}

    active_hotel_ids = set()
    processed_hotel_rows = set()
    failed_hotel_existing_rows = set()
    failed_hotel_objects: list[dict[str, Any]] = []
    current_pages = []
    slug_pool = {row['slug'] for row in existing_hotels + existing_kvartira}

    hotel_exact_by_source = {row['source_message_id']: row for row in existing_hotels}
    hotel_by_title: dict[str, list[dict[str, Any]]] = {}
    for row in existing_hotels:
        hotel_by_title.setdefault(title_key(row.get('title') or ''), []).append(row)
    hotel_canonical_ids = {obj['canonical'].id for obj in hotel_objects}
    unused_rows = {row['id']: row for row in existing_hotels if row['source_message_id'] not in hotel_canonical_ids}

    for index, obj in enumerate(hotel_objects, start=1):
        matched_row = hotel_exact_by_source.get(obj['canonical'].id)
        if matched_row is None:
            key = title_key(obj['parsed'].get('title') or '')
            for row in hotel_by_title.get(key, []):
                if row['id'] in processed_hotel_rows:
                    continue
                if row['id'] in unused_rows:
                    matched_row = row
                    break
        try:
            result = await materialize_object(client, supa, matched_row, obj, slug_pool)
        except Exception as error:  # noqa: BLE001
            if matched_row is not None:
                failed_hotel_existing_rows.add(matched_row['id'])
            failed_hotel_objects.append(
                {
                    'source_id': obj['canonical'].id,
                    'title': obj['parsed'].get('title') or '',
                    'error': str(error),
                }
            )
            print(
                f'[error] hotel materialize failed id={obj["canonical"].id} title="{obj["parsed"].get("title") or ""}": {error}',
                flush=True,
            )
            continue
        if matched_row is not None:
            processed_hotel_rows.add(matched_row['id'])
        current_pages.append({'slug': result['slug'], 'source_id': result['source_id'], 'title': result['title']})
        active_hotel_ids.add(result['id'])
        if index % 10 == 0 or index == len(hotel_objects):
            print(f'Обновлены отели: {index}/{len(hotel_objects)}', flush=True)

    deleted_hotels_count = 0
    if run_hotels and not TARGET_SYNC_MODE:
        for row in existing_hotels:
            if row['id'] not in processed_hotel_rows and row['id'] not in failed_hotel_existing_rows:
                cleanup_removed_listing('hotel', row, supa)
                deleted_hotels_count += 1

    kvartira_cards = []
    processed_kv_rows = set()
    failed_kv_existing_rows = set()
    failed_kv_objects: list[dict[str, Any]] = []
    for index, obj in enumerate(kvartira_objects, start=1):
        matched_row = kvartira_by_topic.get(obj['topic_id'])
        try:
            result = await materialize_object(client, supa, matched_row, obj, slug_pool)
        except Exception as error:  # noqa: BLE001
            if matched_row:
                failed_kv_existing_rows.add(matched_row['id'])
            failed_kv_objects.append(
                {
                    'topic_id': obj['topic_id'],
                    'title': obj.get('topic_title') or obj['parsed'].get('title') or '',
                    'error': str(error),
                }
            )
            print(
                f'[error] kvartira materialize failed topic={obj["topic_id"]} title="{obj.get("topic_title") or obj["parsed"].get("title") or ""}": {error}',
                flush=True,
            )
            continue
        if matched_row:
            processed_kv_rows.add(matched_row['id'])
        kvartira_cards.append({
            'title': result['title'],
            'slug': result['slug'],
            'topic_id': obj['topic_id'],
            'message_id': result['source_id'],
            'url': result['page_url'],
            'telegram_url': result['telegram_url'],
            'image': result['cover_local'],
            'has_video': result['has_video'],
            'excerpt': result['excerpt'],
        })
        if index % 10 == 0 or index == len(kvartira_objects):
            print(f'Обновлены квартиры: {index}/{len(kvartira_objects)}', flush=True)

    deleted_kvartira_count = 0
    if run_kvartira and not TARGET_SYNC_MODE:
        for row in existing_kvartira:
            if row['id'] not in processed_kv_rows and row['id'] not in failed_kv_existing_rows:
                cleanup_removed_listing('kvartira', row, supa)
                deleted_kvartira_count += 1

    if not TARGET_SYNC_MODE:
        CURRENT_PAGES_FILE.write_text(json.dumps(sorted(current_pages, key=lambda item: item['source_id']), ensure_ascii=False, indent=2), encoding='utf-8')
        POSTS_FILE.write_text(json.dumps([
            {
                'id': obj['canonical'].id,
                'date': obj['published_at'],
                'text': obj['canonical'].message or '',
                'html': '',
            }
            for obj in hotel_objects
        ], ensure_ascii=False, indent=2), encoding='utf-8')
        TOPICS_FILE.write_text(json.dumps(topic_dump, ensure_ascii=False, indent=2), encoding='utf-8')
        KV_CARDS_FILE.write_text(json.dumps(sorted(kvartira_cards, key=lambda item: item['message_id'], reverse=True), ensure_ascii=False, indent=2), encoding='utf-8')

    await client.disconnect()
    print(json.dumps({
        'hotels': len(hotel_objects),
        'kvartira': len(kvartira_objects),
        'failed_hotels': len(failed_hotel_objects),
        'failed_kvartira': len(failed_kv_objects),
        'deleted_hotels': deleted_hotels_count,
        'deleted_kvartira': deleted_kvartira_count,
    }, ensure_ascii=False))
    if failed_hotel_objects:
        print('[warn] Не обновились отели:', json.dumps(failed_hotel_objects[:20], ensure_ascii=False), flush=True)
    if failed_kv_objects:
        print('[warn] Не обновились квартиры:', json.dumps(failed_kv_objects[:20], ensure_ascii=False), flush=True)


if __name__ == '__main__':
    asyncio.run(main())
