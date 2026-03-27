from __future__ import annotations

import asyncio
import html
import json
import mimetypes
import os
import re
import shutil
import sys
import time
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
    render_reviews,
    should_drop_line,
    summary_text,
)
from rebuild_from_supabase import infer_filters  # noqa: E402

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
SESSION = str(ROOT / 'tg_session')
CONTACT_BLOCK = '''      <section class="section cta-block hotel-contact-section hotel-site-concept__detail-section">
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
        response = requests.post(url, headers=headers, data=data, timeout=600)
        response.raise_for_status()
        return self.public_url(storage_path)

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


def first_meaningful_line(lines: Iterable[str]) -> str:
    for line in lines:
        cleaned = clean_line(line)
        if cleaned and not should_drop_line(cleaned):
            return cleaned
    return ''


def build_excerpt(parsed: dict[str, Any]) -> str:
    for section in parsed.get('sections', []):
        line = first_meaningful_line(section.get('lines', []))
        if line:
            return line
    return summary_text(parsed.get('location', ''), parsed.get('beach', ''), parsed.get('capacity', ''))


def local_to_public_path(local_path: Path) -> str:
    rel = local_path.relative_to(ROOT).as_posix()
    return f'/{rel}'


def render_paragraph_block(lines: list[str]) -> str:
    visible = [line for line in lines if line and not should_drop_line(line)]
    return '\n'.join(f'            <p>{html.escape(line)}</p>' for line in visible)


def render_sections_html(sections: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for section in sections:
        block = render_paragraph_block(section.get('lines', []))
        if not block:
            continue
        parts.append(
            f'''      <section class="section hotel-site-concept__detail-section">\n        <article class="card">\n          <h2>{html.escape(section.get("label", "Обзор").title())}</h2>\n          <div class="paragraph-blocks">\n{block}\n          </div>\n        </article>\n      </section>'''
        )
    return ''.join(parts)


def render_prices_html(prices: list[str]) -> str:
    visible = [line for line in prices if line and not should_drop_line(line)]
    if not visible:
        return ''
    items = '\n'.join(f'            <li><strong>{html.escape(line)}</strong></li>' for line in visible)
    return f'''      <section class="section hotel-price-section hotel-site-concept__detail-section">\n        <article class="card price-card">\n          <h2>Цены</h2>\n          <ul>\n{items}\n          </ul>\n        </article>\n      </section>'''


def render_reviews_html(seed: int) -> str:
    return render_reviews(seed)


def human_lead(parsed: dict[str, Any]) -> str:
    lead = summary_text(parsed.get('location', ''), parsed.get('beach', ''), parsed.get('capacity', ''))
    excerpt = build_excerpt(parsed)
    if excerpt and excerpt != lead:
        return f'{lead} {excerpt}'
    return lead


def render_media_items(media_items: list[dict[str, Any]], title: str) -> str:
    parts: list[str] = []
    image_index = 1
    video_index = 1
    for item in media_items:
        if item['kind'] == 'photo':
            parts.append(f'            <img src="{html.escape(item["source_url"])}" alt="{html.escape(title)} фото {image_index}" loading="lazy" />')
            image_index += 1
        else:
            parts.append(
                f'''            <div class="video-embed video-embed--telegram">\n              <script async src="https://telegram.org/js/telegram-widget.js?22" data-telegram-post="{html.escape(item["telegram_post"])}" data-width="100%" data-userpic="false" data-single="1"></script>\n              <a class="video-link" href="{html.escape(item["telegram_url"])}?single" target="_blank" rel="noopener noreferrer">Открыть видео в Telegram</a>\n            </div>'''
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
    return f'''          <div class="hotel-card__gallery">\n            <div class="hotel-card__main-photo">\n              <img src="{html.escape(main["source_url"])}" alt="{html.escape(title)} фото 1" loading="eager" />\n              <div class="hotel-card__floating">\n                <span class="pill pill--accent">Проверенный объект</span>\n                <span class="pill">Abhazbereg choice</span>\n              </div>\n            </div>\n            <div class="hotel-card__thumbs">\n              {thumbs}\n            </div>\n          </div>'''


def render_detail_page(source_kind: str, slug: str, telegram_url: str, date_text: str, parsed: dict[str, Any], media_items: list[dict[str, Any]], page_href: str) -> str:
    title = normalize_title(parsed.get('title', '')).upper()
    city = html.escape(city_label(parsed.get('location', '')))
    lead = human_lead(parsed)
    description = build_excerpt(parsed)
    sections = parsed.get('sections', [])
    prices = parsed.get('prices', [])
    top_gallery = render_top_gallery(media_items, title)
    media_html = render_media_items(media_items, title)
    feature_values = [section.get('label', '').title() for section in sections[:3] if section.get('label')]
    if parsed.get('beach'):
        feature_values.append(parsed['beach'])
    feature_html = ''.join(f'<span>{html.escape(item)}</span>' for item in feature_values[:4])
    why_lines = sections[0]['lines'][:3] if sections else []
    important_lines = sections[1]['lines'][:3] if len(sections) > 1 else []
    why_html = ''.join(f'<li>{html.escape(line)}</li>' for line in why_lines if not should_drop_line(line))
    important_html = ''.join(f'<li>{html.escape(line)}</li>' for line in important_lines if not should_drop_line(line))
    breadcrumb = '/kvartira/' if source_kind == 'kvartira' else '/'
    breadcrumb_label = 'Каталог квартир' if source_kind == 'kvartira' else 'Каталог Abhazbereg'
    card_cta = 'К каталогу квартир' if source_kind == 'kvartira' else 'К каталогу'
    page_title_suffix = 'обзор, фото, видео и цены'
    return f'''<!doctype html>\n<html lang="ru">\n  <head>\n    <meta charset="UTF-8" />\n    <meta name="viewport" content="width=device-width, initial-scale=1.0" />\n    <title>{html.escape(title)} — {page_title_suffix}</title>\n    <meta name="description" content="{html.escape(summary_text(parsed.get('location', ''), parsed.get('beach', ''), parsed.get('capacity', '')))}" />\n    <meta name="robots" content="index, follow, max-image-preview:large" />\n    <link rel="canonical" href="https://абхазберег.рф{page_href}" />\n    <meta property="og:type" content="article" />\n    <meta property="og:title" content="{html.escape(title)} — обзор и цены" />\n    <meta property="og:description" content="{html.escape(summary_text(parsed.get('location', ''), parsed.get('beach', ''), parsed.get('capacity', '')))}" />\n    <meta property="og:url" content="https://абхазберег.рф{page_href}" />\n    <meta property="og:image" content="https://абхазберег.рф{html.escape(media_items[0]['source_url']) if media_items else ''}" />\n    <link rel="preconnect" href="https://fonts.googleapis.com" />\n    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />\n    <link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;700;800&family=Prata&display=swap" rel="stylesheet" />\n    <link rel="stylesheet" href="../../styles.css" />\n  </head>\n  <body>\n    <div class="grain" aria-hidden="true"></div>\n    <main class="hotel-site-concept">\n      <div class="card-preview-page__halo card-preview-page__halo--mint" aria-hidden="true"></div>\n      <div class="card-preview-page__halo card-preview-page__halo--sand" aria-hidden="true"></div>\n\n      <section class="hotel-site-concept__intro">\n        <p class="eyebrow"><a href="{breadcrumb}">{breadcrumb_label}</a></p>\n        <h1>{html.escape(title)}</h1>\n        <p>{html.escape(lead)}</p>\n        <p class="updated">Обновлено: <time datetime="{date_text}">{format_human_date(date_text)}</time></p>\n      </section>\n\n      <article class="hotel-card hotel-site-concept__card">\n{top_gallery}\n        <div class="hotel-card__content">\n          <div class="hotel-card__topline">\n            <div class="hotel-card__rating">\n              <strong>{city}</strong>\n              <span>Локация объекта</span>\n            </div>\n            <a class="save-button" href="{breadcrumb}">{card_cta}</a>\n          </div>\n\n          <div class="hotel-card__header">\n            <div>\n              <h2>{html.escape(title)}</h2>\n              <p class="location">{html.escape(lead)}</p>\n            </div>\n            <div class="partner-badge">\n              <span>Abhazbereg</span>\n              <strong>Проверено</strong>\n            </div>\n          </div>\n\n          <p class="hotel-card__description">{html.escape(description)}</p>\n\n          <div class="feature-row">{feature_html}</div>\n\n          <div class="benefit-grid">\n            <article>\n              <strong>Почему выбирают</strong>\n              <ul>{why_html}</ul>\n            </article>\n            <article>\n              <strong>Важно для гостя</strong>\n              <ul>{important_html}</ul>\n            </article>\n          </div>\n\n          <div class="hotel-card__footer">\n            <div class="price-box">\n              <span class="price-box__label">от</span>\n              <strong>{html.escape(prices[0]) if prices else 'по запросу'}</strong>\n              <span class="price-box__note">цены и сезонность смотрите ниже</span>\n            </div>\n\n            <div class="hotel-card__actions">\n              <a class="button button--ghost" href="#details">Смотреть детали</a>\n              <a class="button button--accent" href="https://max.ru/u/f9LHodD0cOLVw3RTEObQAuqGut5qrEnsCdmW7cdV4PgfGrp9ldI_eY2boY8" target="_blank" rel="noopener noreferrer">НАПИСАТЬ В MAX</a>\n            </div>\n          </div>\n        </div>\n      </article>\n\n      <div class="hotel-site-concept__detail-grid" id="details">\n        <div class="hotel-site-concept__detail-main">\n          <section class="section hotel-media-section hotel-site-concept__detail-section">\n            <article class="card">\n              <h2>Фото и видео из поста</h2>\n              <p class="media-note">Источник: <a href="{html.escape(telegram_url)}" target="_blank" rel="noopener noreferrer">{html.escape(telegram_url.replace('https://t.me/', '@'))}</a>.</p>\n              <div class="media-grid">\n{media_html}\n              </div>\n            </article>\n          </section>\n{render_sections_html(sections)}\n        </div>\n        <aside class="hotel-site-concept__detail-aside">\n{render_prices_html(prices)}\n{FAQ_BLOCK}\n{CONTACT_BLOCK}\n        </aside>\n      </div>\n\n      <section class="section hotel-site-concept__detail-section">\n        <article class="card">\n          <h2>Отзывы</h2>\n          <div class="reviews-scroller" aria-label="Лента отзывов">\n{render_reviews_html(sum(ord(ch) for ch in slug))}\n          </div>\n        </article>\n      </section>\n    </main>\n    <script src="../../scripts.js" defer></script>\n  </body>\n</html>'''


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
    payload['details']['filters'] = infer_filters(payload)
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
    if destination.exists() and destination.stat().st_size > 0:
        return destination
    try:
        result = await client.download_media(message, file=str(destination))
    except FileReferenceExpiredError:
        chat = await message.get_input_chat()
        refreshed = await client.get_messages(chat, ids=message.id)
        if not refreshed:
            return None
        result = await client.download_media(refreshed, file=str(destination))
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


def build_hotel_clusters(messages: list[Any]) -> list[dict[str, Any]]:
    candidates = [msg for msg in messages if is_hotel_object_message(msg.message or '')]
    ids = [msg.id for msg in candidates]
    by_id = {msg.id: msg for msg in messages}
    clusters = []
    for index, msg in enumerate(candidates):
        prev_id = ids[index - 1] if index > 0 else min(by_id) - 1
        next_id = ids[index + 1] if index + 1 < len(ids) else max(by_id) + 1
        region = [item for item in messages if prev_id < item.id < next_id]
        clusters.append({'canonical': msg, 'region': region})
    return clusters


async def build_hotel_objects(client: TelegramClient) -> list[dict[str, Any]]:
    messages = await collect_hotel_messages(client)
    clusters = build_hotel_clusters(messages)
    result = []
    for cluster in clusters:
        canonical = cluster['canonical']
        region = cluster['region']
        media_messages = [msg for msg in region if msg.media]
        result.append({
            'source_kind': 'hotel',
            'canonical': canonical,
            'media_messages': sorted(media_messages, key=lambda item: item.id),
            'region_ids': [msg.id for msg in region],
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
    offset_date = None
    offset_id = 0
    offset_topic = 0
    topics = []
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
        thread_messages = await fetch_topic_messages(client, entity, topic.id)
        text_candidates = [msg for msg in thread_messages if is_kvartira_object_message(msg.message or '')]
        if not text_candidates:
            text_candidates = [msg for msg in thread_messages if msg.message and not is_service_text(msg.message)]
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
            photo_paths.append(photo_path)
            storage_path, public_url = local_media_entry(source_kind, photo_path)
            local_media_items.append({'kind': 'photo', 'source_url': local_to_public_path(photo_path), 'public_url': public_url, 'telegram_url': object_data['telegram_url']})
            media_payload.append(media_row(existing_listing['id'] if existing_listing else 0, 'gallery', media_sort, 'image/jpeg', local_to_public_path(photo_path), storage_path, public_url))
        elif msg.video or (msg.file and str(getattr(msg.file, 'mime_type', '')).startswith('video/')):
            video_count += 1
            media_sort += 1
            telegram_url = f'https://t.me/{"abhkvartira" if source_kind == "kvartira" else "abhazbooking"}/{msg.id}'
            telegram_post = telegram_url.replace('https://t.me/', '')
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
            cover_storage, cover_public = local_media_entry(source_kind, cover_path)
            cover_local = local_to_public_path(cover_path)
            media_payload.insert(0, media_row(existing_listing['id'] if existing_listing else 0, 'card', 0, 'image/jpeg', cover_local, cover_storage, cover_public))

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

    client = TelegramClient(SESSION, API_ID, API_HASH)
    await client.connect()

    hotel_objects = await build_hotel_objects(client)
    kvartira_objects, topic_dump = await build_kvartira_objects(client)
    print(f'Найдено объектов: hotels={len(hotel_objects)}, kvartira={len(kvartira_objects)}', flush=True)

    existing_hotels = supa.fetch_listings('hotel')
    existing_kvartira = supa.fetch_listings('kvartira')

    kvartira_by_topic = {row.get('source_topic_id'): row for row in existing_kvartira}

    active_hotel_ids = set()
    processed_hotel_rows = set()
    current_pages = []
    slug_pool = {row['slug'] for row in existing_hotels + existing_kvartira}

    hotel_exact_by_source = {row['source_message_id']: row for row in existing_hotels}
    hotel_canonical_ids = {obj['canonical'].id for obj in hotel_objects}
    hotel_region_fallback_rows = [
        row for row in existing_hotels
        if row['source_message_id'] not in hotel_canonical_ids
    ]

    for index, obj in enumerate(hotel_objects, start=1):
        matched_row = hotel_exact_by_source.get(obj['canonical'].id)
        if matched_row is None:
            region_ids = set(obj['region_ids'])
            for row in hotel_region_fallback_rows:
                if row['id'] in processed_hotel_rows:
                    continue
                if row['source_message_id'] in region_ids:
                    matched_row = row
                    break
        if matched_row is not None:
            processed_hotel_rows.add(matched_row['id'])
        result = await materialize_object(client, supa, matched_row, obj, slug_pool)
        current_pages.append({'slug': result['slug'], 'source_id': result['source_id'], 'title': result['title']})
        active_hotel_ids.add(result['id'])
        if index % 10 == 0 or index == len(hotel_objects):
            print(f'Обновлены отели: {index}/{len(hotel_objects)}', flush=True)

    for row in existing_hotels:
        if row['id'] not in processed_hotel_rows:
            cleanup_removed_listing('hotel', row, supa)

    kvartira_cards = []
    processed_kv_rows = set()
    for index, obj in enumerate(kvartira_objects, start=1):
        matched_row = kvartira_by_topic.get(obj['topic_id'])
        if matched_row:
            processed_kv_rows.add(matched_row['id'])
        result = await materialize_object(client, supa, matched_row, obj, slug_pool)
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

    for row in existing_kvartira:
        if row['id'] not in processed_kv_rows:
            cleanup_removed_listing('kvartira', row, supa)

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
        'deleted_hotels': len(existing_hotels) - len(processed_hotel_rows),
        'deleted_kvartira': len(existing_kvartira) - len(processed_kv_rows),
    }, ensure_ascii=False))


if __name__ == '__main__':
    asyncio.run(main())
