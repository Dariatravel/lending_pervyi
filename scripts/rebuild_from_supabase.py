from __future__ import annotations

import html
import json
import re
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse
import xml.etree.ElementTree as ET

import requests

from media_urls import media_src_for_html, yandex_photo_url  # noqa: E402
from supplemental_store import apply_to_page_html as supplemental_apply_to_page  # noqa: E402
from responsive_images import responsive_img_html  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env.supabase.local"
INDEX_PATH = ROOT / "index.html"
KVARTIRA_DIR = ROOT / "kvartira"
KVARTIRA_PATH = ROOT / "kvartira" / "index.html"
SITEMAP_PATH = ROOT / "sitemap.xml"
CANON_ORIGIN = "https://абхазберег.рф"
PUNY_ORIGIN_LEGACY = "https://xn--80aacbklan7f0b.xn--p1ai"
BLOG_ROOT = ROOT / "blog"
PODBORKI_ROOT_SITE = ROOT / "podborki"
HOTEL_POSTS_PATH = ROOT / "output" / "abhazbooking_2026_posts.json"


FILTER_GROUPS = ("distance", "food", "price", "city", "beach", "room", "stay")

# «Цена от …» в карточках каталога: файл фиксируется ежедневно в 03:00 МСК
# workflow'ом price-refresh (tools/build_min_prices.py), пересборки в течение
# дня используют зафиксированные значения.
MIN_PRICES_PATH = ROOT / "data" / "min-prices-today.json"


def _load_min_prices() -> tuple[dict[str, int], str]:
    try:
        payload = json.loads(MIN_PRICES_PATH.read_text(encoding="utf-8"))
        return dict(payload.get("prices") or {}), str(payload.get("month_label") or "")
    except Exception:  # noqa: BLE001 — нет файла = карточки без строки цены
        return {}, ""


MIN_PRICES, MIN_PRICES_MONTH_LABEL = _load_min_prices()


def render_card_price_html(slug: str) -> str:
    value = MIN_PRICES.get(str(slug))
    if not value or not MIN_PRICES_MONTH_LABEL:
        return ""
    pretty = f"{value:,}".replace(",", " ")
    return (
        f'<p class="catalog-card__price">Цена от <strong>{pretty} ₽</strong>/сутки '
        f"{MIN_PRICES_MONTH_LABEL}</p>"
    )


# Хвосты вида «🩵скидка 20% до 20 июля🩵» в мини-карточке не показываем —
# название должно оставаться чистым (решение Дарьи 18.07.2026).
_PROMO_TAIL_RX = re.compile(r"скидк|акци", re.IGNORECASE)
_TAIL_TRIM_RX = re.compile(
    "[\\s\\-–—:,·|" "\U0001f000-\U0001faff☀-➿⬀-⯿️]+$"
)
_CAPACITY_RX = re.compile(r"размещ\w*[^.,;!]*?до\s*\d+\s*чел\w*", re.IGNORECASE)


def clean_card_title(title: str) -> str:
    text = str(title or "")
    match = _PROMO_TAIL_RX.search(text)
    if not match:
        return text
    cleaned = _TAIL_TRIM_RX.sub("", text[: match.start()]).strip()
    return cleaned or text


def extract_capacity_text(row: dict[str, Any]) -> str:
    details = row.get("details") or {}
    for source in (row.get("summary"), row.get("excerpt"), details.get("lead")):
        match = _CAPACITY_RX.search(str(source or ""))
        if match:
            return match.group(0).strip()
    return ""


def render_card_facts_html(row: dict[str, Any], fallback_summary: str) -> str:
    """Три строки фактов из шапки телеграм-поста: 📍адрес, 🏖пляж, 👥вместимость."""
    lines: list[str] = []
    location_text = str(row.get("location_text") or "").strip().lstrip("️ ").strip()
    beach_text = str(row.get("beach_text") or "").strip().lstrip("️ ").strip()
    if location_text:
        lines.append(location_text if location_text.startswith("📍") else f"📍{location_text}")
    if beach_text:
        lines.append(beach_text if beach_text.startswith("🏖") else f"🏖 {beach_text}")
    capacity_text = extract_capacity_text(row)
    if capacity_text:
        lines.append(f"👥 {capacity_text}")
    if lines:
        inner = "<br />".join(html.escape(line) for line in lines)
        return f'<p class="catalog-card__facts">{inner}</p>'
    return f"<p>{html.escape(fallback_summary)}</p>"
CITY_MAP = {
    "sukhum": ("сухум",),
    "new-afon": ("новый афон", "приморское"),
    "gudauta": ("гудаута", "хыпста", "бамбора"),
    "ldzaa": ("лдзаа",),
    "pitsunda": ("пицунда", "птицефабрика"),
    "alakhadzy": ("алахадзы", "алахадзе"),
    "gagra": ("гагра", "старая гагра", "новая гагра", "багрипш"),
    "tsandripsh": ("цандрипш",),
}

def load_env(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip()
    return data


def resolve_site_page_path(row: dict[str, Any]) -> Path | None:
    """Путь к index.html объекта в текущем репозитории (приоритет — lending_pervyi)."""
    details = row.get("details") or {}
    candidates: list[Path] = []
    slug = str(row.get("slug") or "").strip()
    kind = str(row.get("source_kind") or "").strip()
    if slug and kind in {"hotel", "kvartira"}:
        folder = "hotels" if kind == "hotel" else "kvartira"
        candidates.append(ROOT / folder / slug / "index.html")
    page_url = str(row.get("page_url") or "")
    match = re.search(r"/(hotels|kvartira)/([^/?#]+)", page_url)
    if match:
        candidates.append(ROOT / match.group(1) / match.group(2) / "index.html")
    page_path = str(details.get("page_path") or "").strip()
    if page_path:
        candidates.append(Path(page_path.replace("/New project/", "/GitHub/lending_pervyi/")))
    for path in candidates:
        if path.is_file():
            try:
                with path.open("r", encoding="utf-8") as handle:
                    handle.read(1)
            except OSError:
                continue
            return path
    return None


def pick_cover_url(row: dict[str, Any]) -> str:
    media = sorted(row.get("listing_media") or [], key=lambda item: item.get("sort_order") or 0)
    for item in media:
        if item.get("media_role") == "card" and item.get("public_url"):
            return item["public_url"]
    for item in media:
        if item.get("public_url") and str(item.get("mime_type") or "").startswith("image/"):
            return item["public_url"]
    return row.get("cover_url") or ""


def image_src_for_html(url: str) -> str:
    return yandex_photo_url(url)


def page_path_from_url(url: str | None, fallback: str) -> str:
    if not url:
        return fallback
    parsed = urlparse(url)
    return parsed.path or fallback


def human_date(value: str | None) -> str:
    if not value:
        return ""
    year, month, day = value.split("-")
    months = {
        "01": "января",
        "02": "февраля",
        "03": "марта",
        "04": "апреля",
        "05": "мая",
        "06": "июня",
        "07": "июля",
        "08": "августа",
        "09": "сентября",
        "10": "октября",
        "11": "ноября",
        "12": "декабря",
    }
    return f"{int(day)} {months[month]} {year}"


def extract_emoji_line(lines: list[str], prefixes: tuple[str, ...]) -> str:
    for line in lines:
        trimmed = line.strip()
        if any(trimmed.startswith(prefix) for prefix in prefixes):
            return trimmed
    return ""


def load_hotel_card_meta() -> dict[int, dict[str, str]]:
    if not HOTEL_POSTS_PATH.exists():
        return {}
    try:
        posts = json.loads(HOTEL_POSTS_PATH.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}
    result: dict[int, dict[str, str]] = {}
    for item in posts:
        try:
            message_id = int(item.get("id"))
        except Exception:  # noqa: BLE001
            continue
        text = str(item.get("text") or "")
        lines = [line for line in text.splitlines() if line.strip()]
        location_line = extract_emoji_line(lines, ("📍",))
        beach_line = extract_emoji_line(lines, ("🏖", "🏝"))
        if location_line or beach_line:
            result[message_id] = {
                "location_line": location_line,
                "beach_line": beach_line,
            }
    return result


CITY_MAP_LABELS = {
    "ldzaa": "Лдзаа",
    "pitsunda": "Пицунда",
    "gagra": "Гагра",
    "alakhadzy": "Алахадзы",
    "gudauta": "Гудаута",
    "new-afon": "Н. Афон",
    "sukhum": "Сухум",
    "tsandripsh": "Цандрипш",
}


def normalize_city_lookup_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", value or "").lower().replace("ё", "е")
    return re.sub(r"[^a-zа-я0-9]+", " ", text).strip()


def city_key_from_text(value: str) -> str:
    normalized = normalize_city_lookup_text(value)
    if not normalized:
        return ""
    for key, label in CITY_MAP_LABELS.items():
        if normalize_city_lookup_text(label) == normalized:
            return key
    for key, markers in CITY_MAP.items():
        for marker in markers:
            marker_normalized = normalize_city_lookup_text(marker)
            if marker_normalized and re.search(rf"(^|\s){re.escape(marker_normalized)}(\s|$)", normalized):
                return key
    return ""


def listing_city_key(row: dict[str, Any]) -> str:
    for value in (row.get("city"), row.get("location_text")):
        key = city_key_from_text(str(value or ""))
        if key:
            return key
    return ""


def filter_city_values(filters: dict[str, Any]) -> list[str]:
    cities = filters.get("city") or []
    if isinstance(cities, str):
        cities = [part.strip() for part in cities.split("|") if part.strip()]
    return [str(city).strip() for city in cities if str(city).strip()]


def primary_city_key(filters: dict[str, Any], row: dict[str, Any] | None = None) -> str:
    listing_key = listing_city_key(row or {})
    if listing_key:
        return listing_key
    cities = filter_city_values(filters)
    return cities[0] if cities else ""


def render_map_plaque_html(city_key: str) -> str:
    if not city_key:
        return ""
    label = CITY_MAP_LABELS.get(city_key, "Абхазия")
    city_attr = html.escape(city_key, quote=True)
    label_text = html.escape(label)
    return (
        f'<span class="catalog-card__map-plaque catalog-card__map-plaque--{city_attr}" '
        f'data-map-city="{city_attr}" role="link" tabindex="0">'
        f'<span class="catalog-card__map-plaque-pin" aria-hidden="true"></span>'
        f'<span class="catalog-card__map-plaque-city">{label_text}</span>'
        f'<span class="catalog-card__map-plaque-map" aria-hidden="true">карта</span>'
        f"</span>"
    )


def render_hotel_card(row: dict[str, Any], post_meta: dict[int, dict[str, str]]) -> str:
    filters = (row.get("details") or {}).get("filters") or {}
    attrs = " ".join(
        f'data-filter-{group}="{html.escape("|".join(filters.get(group) or []), quote=True)}"'
        for group in FILTER_GROUPS
    )
    href = page_path_from_url(row.get("page_url"), f"/hotels/{row['slug']}/")
    image = image_src_for_html(pick_cover_url(row))
    title = html.escape(clean_card_title(row.get("title") or ""))
    summary_fallback = row.get("summary") or row.get("excerpt") or ""
    facts_row = row
    if not str(row.get("location_text") or "").strip() and not str(row.get("beach_text") or "").strip():
        source_message_id = resolve_source_message_id(row)
        if source_message_id is not None:
            meta = post_meta.get(source_message_id) or {}
            if meta.get("location_line") or meta.get("beach_line"):
                facts_row = dict(row)
                facts_row["location_text"] = meta.get("location_line") or ""
                facts_row["beach_text"] = meta.get("beach_line") or ""
    facts_html = render_card_facts_html(facts_row, summary_fallback)
    city_key = primary_city_key(filters, row)
    map_plaque = render_map_plaque_html(city_key)
    video_attr = ' data-has-video="1"' if row.get("has_video") else ""
    image_html = responsive_img_html(
        image,
        html.unescape(title),
        loading="lazy",
        sizes="(max-width: 720px) 92vw, (max-width: 1180px) 45vw, 320px",
    )
    return (
        f'<a class="catalog-card" data-listing-kind="hotel"{video_attr} {attrs} href="{html.escape(href, quote=True)}">'
        f'<div class="catalog-card__media-wrap">{image_html}'
        f"{map_plaque}</div>"
        f"<h3>{title}</h3>"
        f"{facts_html}"
        f"{render_card_price_html(row.get('slug') or '')}"
        f"</a>"
    )


def resolve_source_message_id(row: dict[str, Any]) -> int | None:
    direct = row.get("source_message_id")
    if isinstance(direct, int) and direct > 0:
        return direct
    if isinstance(direct, str) and direct.isdigit():
        return int(direct)

    # Часть объектов в базе живет без source_message_id, но с id в slug/telegram_url.
    candidates = [
        str(row.get("telegram_url") or "").strip(),
        str(row.get("slug") or "").strip(),
        str(row.get("page_url") or "").strip(),
    ]
    for value in candidates:
        if not value:
            continue
        matches = re.findall(r"(\d{3,6})", value)
        if not matches:
            continue
        try:
            return int(matches[-1])
        except ValueError:
            continue
    return None


def render_kvartira_card(row: dict[str, Any]) -> str:
    filters = (row.get("details") or {}).get("filters") or {}
    attrs = " ".join(
        f'data-filter-{group}="{html.escape("|".join(filters.get(group) or []), quote=True)}"'
        for group in FILTER_GROUPS
    )
    href = page_path_from_url(row.get("page_url"), row.get("telegram_url") or "/kvartira/")
    title = html.escape(clean_card_title(row.get("title") or ""))
    summary_fallback = row.get("summary") or row.get("excerpt") or ((row.get("details") or {}).get("excerpt") or "")
    facts_html = render_card_facts_html(row, summary_fallback)
    image = image_src_for_html(pick_cover_url(row))
    badge = '<span class="catalog-card__badge">Видео</span>' if row.get("has_video") else ""
    map_plaque = render_map_plaque_html(primary_city_key(filters, row))
    image_html = responsive_img_html(
        image,
        html.unescape(title),
        loading="lazy",
        sizes="(max-width: 720px) 92vw, (max-width: 1180px) 45vw, 320px",
    )
    return (
        f'<a class="catalog-card" data-listing-kind="kvartira" {attrs} href="{html.escape(href, quote=True)}">'
        f'<div class="catalog-card__media-wrap">{badge}{image_html}'
        f"{map_plaque}</div>"
        f"<h3>{title}</h3>"
        f"{facts_html}"
        f"{render_card_price_html(row.get('slug') or '')}"
        f"</a>"
    )


KVARTIRA_CATALOG_PAGE_SUFFIX = """
      <section class="site-concept__section-block" id="guide">
        <div class="site-concept__section-head">
          <div>
            <p class="site-concept__eyebrow">Как бронировать</p>
            <h2>Выбирай жилье в Абхазии без утомительного поиска и без переплаты</h2>
          </div>
        </div>

        <div class="site-concept__guide-grid">
          <article class="site-concept__guide-card">
            <span>01</span>
            <strong>Говорите, что вам нужно</strong>
            <p>Курорт, даты, сколько человек, какой бюджет и что важно именно вам.</p>
          </article>
          <article class="site-concept__guide-card site-concept__guide-card--accent">
            <span>02</span>
            <strong>Я подбираю подходящие варианты</strong>
            <p>Не всё подряд, а только то, что правда стоит смотреть под ваш запрос.</p>
          </article>
          <article class="site-concept__guide-card site-concept__guide-card--accent">
            <span>03</span>
            <strong>Обсуждаем в удобном формате</strong>
            <p>Можно в мессенджере — спокойно задать вопросы и быстро сузить выбор.</p>
          </article>
          <article class="site-concept__guide-card">
            <span>04</span>
            <strong>Фиксируем бронь</strong>
            <p>Когда вариант подходит, помогаю оформить бронирование и всё подтвердить.</p>
          </article>
        </div>

        <div class="site-concept__guide-footer">
          <p class="site-concept__guide-pitch">Самостоятельный поиск жилья — это десятки сайтов и переписок, где теряется время.</p>
          <p class="site-concept__guide-pitch">Напишите, что вам нужно — я предложу подходящие варианты; если не подойдёт, продолжите искать сами.</p>
          <div class="site-concept__guide-cta">
            <div class="site-concept__guide-messenger-grid" role="group" aria-label="Написать в мессенджер">
              <a class="btn-book site-concept__guide-messenger-btn" href="https://max.ru/abhazbereg" rel="noopener noreferrer" target="_blank">НАПИСАТЬ В МАКС</a>
              <a class="btn-book site-concept__guide-messenger-btn" href="http://vk.cc/cQQnBn" rel="noopener noreferrer" target="_blank">НАПИСАТЬ В ВК-ЧАТ</a>
              <a class="btn-book site-concept__guide-messenger-btn" href="https://t.me/abhazbooking_online" rel="noopener noreferrer" target="_blank">НАПИСАТЬ В ТЕЛЕГРАМ</a>
              <a class="btn-book site-concept__guide-messenger-btn" href="https://wa.me/79409003340" rel="noopener noreferrer" target="_blank">НАПИСАТЬ В ВАТСАП</a>
            </div>
          </div>
        </div>
      </section>

      <section class="section site-concept__reviews" id="reviews">
        <article class="card review-shell">
          <div class="section-heading section-heading--compact">
            <p class="eyebrow">Отзывы гостей</p>
          </div>
          <div aria-label="Лента отзывов" class="reviews-scroller" data-random-reviews="" data-review-count="6"></div>
        </article>
      </section>

      <section class="section site-concept__contacts" id="contacts">
        <article class="cta-block contact-shell">
          <div class="contact-shell__intro">
            <p class="eyebrow">Контакты и бронирование</p>
            <p>
              Проверить наличие номеров и задать вопросы можно по номеру<br />
              <strong class="contact-phone">+7 940 900-33-40</strong><br />
              <span class="contact-messengers">(max, whatsapp, telegram - только сообщения, обычный звонок не пройдёт)</span>
            </p>
            <p class="note">ВАЖНО: прежде чем написать в максе, добавьте номер в контакты телефона (иначе макс не даст ответить на входящее сообщение)</p>
          </div>
          <div class="contact-channel-panel">
<div class="contact-channel-grid">
<a class="contact-channel-card" href="https://vk.cc/cQQnBn" rel="noopener noreferrer" target="_blank">
<span aria-hidden="true" class="contact-channel-card__icon contact-channel-card__icon--vk"></span>
<span class="contact-channel-card__copy"><strong>ВКонтакте</strong><small>Самый быстрый ответ</small></span>
<span aria-hidden="true" class="contact-channel-card__arrow">→</span>
</a>
<a class="contact-channel-card" href="https://max.ru/abhazbereg" rel="noopener noreferrer" target="_blank">
<span aria-hidden="true" class="contact-channel-card__icon contact-channel-card__icon--max"></span>
<span class="contact-channel-card__copy"><strong>MAX</strong><small>Добавьте номер в книгу контактов, прежде чем написать</small></span>
<span aria-hidden="true" class="contact-channel-card__arrow">→</span>
</a>
<a class="contact-channel-card" href="https://t.me/abhazbooking_online" rel="noopener noreferrer" target="_blank">
<span aria-hidden="true" class="contact-channel-card__icon contact-channel-card__icon--tg"></span>
<span class="contact-channel-card__copy"><strong>Telegram</strong><small>Только сообщения</small></span>
<span aria-hidden="true" class="contact-channel-card__arrow">→</span>
</a>
<a class="contact-channel-card" href="https://wa.me/79409003340" rel="noopener noreferrer" target="_blank">
<span aria-hidden="true" class="contact-channel-card__icon contact-channel-card__icon--whatsapp">
<svg aria-hidden="true" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M12.04 2a9.84 9.84 0 0 0-8.47 14.83L2 22l5.3-1.53A9.96 9.96 0 0 0 12.04 22C17.53 22 22 17.52 22 12S17.53 2 12.04 2Zm0 18.32a8.2 8.2 0 0 1-4.18-1.14l-.3-.18-3.15.91.93-3.07-.2-.32a8.16 8.16 0 0 1-1.26-4.38 8.18 8.18 0 1 1 8.16 8.18Zm4.5-6.12c-.25-.12-1.46-.72-1.69-.8-.23-.09-.4-.13-.56.12-.17.25-.65.8-.8.97-.14.16-.29.18-.53.06-.25-.13-1.04-.39-1.99-1.23a7.45 7.45 0 0 1-1.38-1.72c-.14-.25-.01-.38.11-.5.11-.1.25-.29.37-.43.12-.15.16-.25.25-.42.08-.16.04-.31-.02-.43-.07-.13-.56-1.36-.77-1.86-.2-.49-.41-.42-.56-.43h-.48c-.17 0-.44.06-.67.31-.23.25-.88.86-.88 2.1 0 1.23.9 2.43 1.02 2.6.13.16 1.77 2.7 4.28 3.78.6.26 1.07.41 1.43.53.6.19 1.15.16 1.58.1.48-.08 1.46-.6 1.67-1.18.2-.57.2-1.06.14-1.17-.06-.1-.23-.16-.48-.29Z"/></svg>
</span>
<span class="contact-channel-card__copy"><strong>WhatsApp</strong><small>Только сообщения</small></span>
<span aria-hidden="true" class="contact-channel-card__arrow">→</span>
</a>
</div>
</div>
</div>
        </article>
      </section>
"""


def render_kvartira_catalog_page(_rows: list[dict[str, Any]]) -> str:
    """Legacy /kvartira/ URL: redirect to unified catalog on the homepage."""
    return """<!doctype html>
<html lang="ru">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Каталог жилья — Абхазберег</title>
    <meta name="robots" content="noindex, follow" />
    <link rel="canonical" href="https://абхазберег.рф/" />
    <meta http-equiv="refresh" content="0;url=/#catalog" />
    <script>location.replace("/#catalog");</script>
  </head>
  <body>
    <p><a href="/#catalog">Перейти в каталог</a></p>
  </body>
</html>
"""


def replace_catalog_block(file_path: Path, marker: str, html_block: str) -> None:
    text = file_path.read_text(encoding="utf-8")
    pattern = (
        r'<div class="catalog-grid" id="catalog-grid"[^>]*>'
        r'[\s\S]*?'
        r'</div>\s*(?:<div class="catalog-grid" id="catalog-grid"[^>]*>[\s\S]*?</div>\s*)?'
        r'(?=<div class="catalog-expand-wrap">|<button class="btn-filter catalog-expand-button")'
    )
    replacement = f'<div class="catalog-grid" id="catalog-grid">{html_block}</div>\n'
    updated, count = re.subn(pattern, replacement, text, count=1)
    if count != 1:
        raise RuntimeError(
            f"Не удалось заменить блок каталога в {file_path}: найдено совпадений {count}"
        )
    file_path.write_text(updated, encoding="utf-8")


def replace_once(text: str, pattern: str, replacement: str) -> str:
    return re.sub(pattern, replacement, text, count=1, flags=re.S)


def render_media_grid(row: dict[str, Any], title: str) -> str:
    media_items = sorted(row.get("listing_media") or [], key=lambda media: media.get("sort_order") or 0)
    parts: list[str] = []
    image_index = 1
    video_index = 1

    for item in media_items:
        if item.get("media_role") != "gallery":
            continue

        mime = str(item.get("mime_type") or "")
        source_url = str(item.get("source_url") or "").strip()
        public_url = str(item.get("public_url") or "").strip()
        preferred_url = source_url if source_url.startswith("/media/") else (public_url or source_url)

        if mime.startswith("image/") and preferred_url:
            preferred_url = image_src_for_html(preferred_url)
            parts.append(
                f"            {responsive_img_html(preferred_url, f'{title} фото {image_index}', loading='lazy', sizes='(max-width: 720px) 92vw, (max-width: 1180px) 45vw, 520px')}"
            )
            image_index += 1
            continue

        if mime.startswith("video/") and preferred_url:
            preferred_url = media_src_for_html(preferred_url, mime_type=mime)
            details = item.get("details") or {}
            poster_url = str(details.get("poster_url") or "").strip()
            poster_attr = (
                f' poster="{html.escape(poster_url, quote=True)}"' if poster_url.startswith("http") else ""
            )
            parts.append(
                f"""            <video class="local-video" controls preload="none" playsinline{poster_attr}>
              <source src="{html.escape(preferred_url, quote=True)}" type="{html.escape(mime or 'video/mp4', quote=True)}" />
            </video>"""
            )
            video_index += 1
            continue

        if mime == "application/x-telegram-embed":
            details = item.get("details") or {}
            telegram_post = str(details.get("telegram_post") or "").strip()
            if telegram_post:
                parts.append(
                    f"""            <div class="video-embed video-embed--telegram">
              <script async src="https://telegram.org/js/telegram-widget.js?22" data-telegram-post="{html.escape(telegram_post, quote=True)}" data-width="100%" data-userpic="false" data-single="1"></script>
            </div>"""
                )
                video_index += 1

    return "\n".join(parts)


def update_hotel_page(row: dict[str, Any]) -> None:
    path = resolve_site_page_path(row)
    if not path:
        return
    details = row.get("details") or {}

    title = row.get("title") or ""
    summary = row.get("summary") or row.get("excerpt") or ""
    lead = details.get("lead") or summary
    cover = pick_cover_url(row)
    page_url = row.get("page_url") or f"https://абхазберег.рф/hotels/{row['slug']}/"
    telegram = row.get("telegram_url") or ""
    published = row.get("published_at")
    published_human = human_date(published)
    media_label = telegram.replace("https://t.me/", "@") if telegram else ""

    lead_html = "<br />".join(html.escape(part.strip()) for part in lead.split("\n") if part.strip())
    text = path.read_text(encoding="utf-8")
    text = replace_once(text, r"<title>.*?</title>", f"<title>{html.escape(title)} — обзор, фото, видео и цены</title>")
    text = replace_once(text, r'<meta name="description" content=".*?" ?/?>', f'<meta name="description" content="{html.escape(summary, quote=True)}" />')
    text = replace_once(text, r'<link rel="canonical" href=".*?" ?/?>', f'<link rel="canonical" href="{html.escape(page_url, quote=True)}" />')
    text = replace_once(text, r'<meta property="og:title" content=".*?" ?/?>', f'<meta property="og:title" content="{html.escape(title, quote=True)} — обзор и цены" />')
    text = replace_once(text, r'<meta property="og:description" content=".*?" ?/?>', f'<meta property="og:description" content="{html.escape(summary, quote=True)}" />')
    text = replace_once(text, r'<meta property="og:url" content=".*?" ?/?>', f'<meta property="og:url" content="{html.escape(page_url, quote=True)}" />')
    if cover:
        text = replace_once(text, r'<meta property="og:image" content="https://storage.yandexcloud.net/abhazbereg-media/media/branding/og-banner.png" ?/?>', f'<meta property="og:image" content="https://storage.yandexcloud.net/abhazbereg-media/media/branding/og-banner.png" />')
    text = replace_once(text, r"<h1>.*?</h1>", f"<h1>{html.escape(title)}</h1>")
    if lead_html:
        text = replace_once(text, r'<p class="lead">.*?</p>', f'<p class="lead">{lead_html}</p>')
    if published and published_human:
        text = replace_once(
            text,
            r'<p class="updated">Обновлено: <time datetime=".*?">.*?</time></p>',
            f'<p class="updated">Обновлено: <time datetime="{html.escape(published, quote=True)}">{published_human}</time></p>',
        )
    if telegram and media_label:
        text = replace_once(
            text,
            r'<p class="media-note">Источник: <a href=".*?" target="_blank" rel="noopener noreferrer">.*?</a>\.</p>',
            f'<p class="media-note">Источник: <a href="{html.escape(telegram, quote=True)}" target="_blank" rel="noopener noreferrer">{html.escape(media_label)}</a>.</p>',
        )

    gallery_html = render_media_grid(row, title)
    if gallery_html:
        text = re.sub(
            r'(<div class="media-grid">)(.*?)(\s*</div>\s*</article>)',
            r"\1\n" + gallery_html + r"\3",
            text,
            count=1,
            flags=re.S,
        )

    cover_url = image_src_for_html(cover.strip()) if cover else ""
    ld_script = lodging_listing_json_ld_script(
        "Hotel",
        title,
        summary or title,
        page_url,
        cover_url if cover_url else None,
    )
    if 'data-schema="listing"' in text:
        text = re.sub(r"\s*<script type=\"application/ld\+json\" data-schema=\"listing\">[\s\S]*?</script>", "\n" + ld_script, text, count=1)
    else:
        text = re.sub(r"(\s*)</head>", rf"\1{ld_script}\n\1</head>", text, count=1)

    path.write_text(text, encoding="utf-8")


def rebuild_kvartira_pages(rows: list[dict[str, Any]]) -> None:
    from sync_catalog_from_telegram import render_detail_page  # noqa: PLC0415

    for row in rows:
        details = row.get("details") or {}
        page_url = row.get("page_url") or f"https://абхазберег.рф/kvartira/{row['slug']}/"
        path = resolve_site_page_path(row)
        if not path:
            rel = page_path_from_url(page_url, f"/kvartira/{row['slug']}/").strip("/")
            path = ROOT / rel / "index.html"
        path.parent.mkdir(parents=True, exist_ok=True)

        parsed = {
            "title": row.get("title") or "",
            "location": row.get("location_text") or row.get("city") or "",
            "beach": row.get("beach_text") or "",
            "capacity": row.get("capacity_text") or "",
            "sections": details.get("sections") or [],
            "prices": details.get("prices") or [],
        }

        media_items: list[dict[str, Any]] = []
        for item in sorted(row.get("listing_media") or [], key=lambda media: media.get("sort_order") or 0):
            if item.get("media_role") != "gallery":
                continue
            mime = str(item.get("mime_type") or "")
            source_url = item.get("source_url") or ""
            public_url = item.get("public_url") or ""
            preferred_url = source_url if str(source_url).startswith("/media/") else public_url or source_url
            if mime.startswith("image/") and preferred_url:
                media_items.append({"kind": "photo", "source_url": image_src_for_html(preferred_url)})
                continue
            if mime.startswith("video/") and preferred_url:
                poster_url = str((item.get("details") or {}).get("poster_url") or "").strip()
                media_items.append(
                    {
                        "kind": "video",
                        "source_url": media_src_for_html(preferred_url, mime_type=mime),
                        "poster": poster_url,
                    }
                )
                continue
            if mime == "application/x-telegram-embed":
                telegram_post = ((item.get("details") or {}).get("telegram_post") or "").strip()
                telegram_url = item.get("source_url") or row.get("telegram_url") or ""
                if telegram_post and telegram_url:
                    media_items.append(
                        {
                            "kind": "video",
                            "source_url": telegram_url,
                            "telegram_post": telegram_post,
                            "telegram_url": telegram_url,
                        }
                    )

        page_href = page_path_from_url(page_url, f"/kvartira/{row['slug']}/")
        html_page = render_detail_page("kvartira", row["slug"], row.get("telegram_url") or "", row.get("published_at") or "", parsed, media_items, page_href)
        # Возвращаем блок «Дополнительные обзоры» из манифеста (переживает пересборки).
        html_page = supplemental_apply_to_page(html_page, row["slug"])
        path.write_text(html_page, encoding="utf-8")


def lodging_listing_json_ld_script(schema_type: str, name: str, description: str, url: str, image_url: str | None) -> str:
    blob: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": schema_type,
        "name": name,
        "description": description,
        "url": url,
    }
    if image_url:
        blob["image"] = [image_url]
    dumped = json.dumps(blob, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    return f'    <script type="application/ld+json" data-schema="listing">\n      {dumped}\n    </script>'


def discover_static_sitemap_urls() -> list[str]:
    urls: list[str] = [
        f"{CANON_ORIGIN}/",
        f"{CANON_ORIGIN}/kvartira/",
        f"{CANON_ORIGIN}/blog/",
    ]
    if BLOG_ROOT.is_dir():
        for path_item in sorted(BLOG_ROOT.glob("*/index.html")):
            urls.append(f"{CANON_ORIGIN}/blog/{path_item.parent.name}/")
    if PODBORKI_ROOT_SITE.is_dir():
        urls.append(f"{CANON_ORIGIN}/podborki/")
        for path_item in sorted(PODBORKI_ROOT_SITE.glob("*/index.html")):
            urls.append(f"{CANON_ORIGIN}/podborki/{path_item.parent.name}/")
    return urls


def _normalize_sitemap_location(raw: str) -> str:
    u = (raw or "").strip()
    if not u:
        return ""
    return u.replace(PUNY_ORIGIN_LEGACY, CANON_ORIGIN)


def rebuild_sitemap(rows: list[dict[str, Any]]) -> None:
    ordered: list[str] = []
    seen: set[str] = set()

    def push(raw: str) -> None:
        u = _normalize_sitemap_location(raw)
        if not u or u in seen:
            return
        seen.add(u)
        ordered.append(u)

    for u in discover_static_sitemap_urls():
        push(u)
    for row in rows:
        if row.get("source_kind") not in {"hotel", "kvartira"}:
            continue
        page_u = row.get("page_url")
        if page_u:
            push(str(page_u))

    urlset = ET.Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
    today = datetime.now(timezone.utc).date().isoformat()
    for u in ordered:
        node = ET.SubElement(urlset, "url")
        loc_el = ET.SubElement(node, "loc")
        loc_el.text = u
        lastmod_el = ET.SubElement(node, "lastmod")
        lastmod_el.text = today
    tree = ET.ElementTree(urlset)
    try:
        ET.indent(tree.getroot(), space="  ")
    except (AttributeError, TypeError):
        pass
    tree.write(SITEMAP_PATH, encoding="utf-8", xml_declaration=True)


def normalize_catalog_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        if "listing_media" not in item and "media" in item:
            item["listing_media"] = item.get("media") or []
        normalized.append(item)
    return normalized


CATALOG_INITIAL_LIMIT = 20
# В статический HTML главной попадают только первые карточки — остальные
# дорендерит scripts.js из catalog-index.json после загрузки (Lighthouse:
# полный каталог в HTML давал TBT>1s на слабых CPU из-за парсинга/стилей).
CATALOG_STATIC_LIMIT = 24


def mark_catalog_cards_initial_hidden(cards_html: str, limit: int = CATALOG_INITIAL_LIMIT) -> str:
    """Pre-hide cards beyond the first-screen limit so the grid does not FOUC before JS."""
    parts = re.split(r'(?=<a class="catalog-card")', cards_html)
    prefix = parts[0]
    cards = [part for part in parts[1:] if part.startswith('<a class="catalog-card"')]
    marked: list[str] = []
    for index, card in enumerate(cards):
        if index >= limit and " hidden" not in card[:80]:
            card = card.replace('<a class="catalog-card"', '<a class="catalog-card" hidden', 1)
        marked.append(card)
    return prefix + "".join(marked)


def sync_catalog_grid_total_attr(total_cards: int) -> None:
    """data-catalog-total на гриде — сигнал клиенту дорендерить остальные карточки."""
    text = INDEX_PATH.read_text(encoding="utf-8")
    updated, count = re.subn(
        r'<div class="catalog-grid" id="catalog-grid"(?: data-catalog-total="\d+")?>',
        f'<div class="catalog-grid" id="catalog-grid" data-catalog-total="{total_cards}">',
        text,
        count=1,
    )
    if count:
        INDEX_PATH.write_text(updated, encoding="utf-8")


def sync_catalog_visible_count_markup(total_cards: int) -> None:
    """Keep SSR counter honest before deferred scripts run."""
    text = INDEX_PATH.read_text(encoding="utf-8")
    initial = min(total_cards, CATALOG_INITIAL_LIMIT)
    updated, count = re.subn(
        r'(<p class="filter-result">)[\s\S]*?(</p>)',
        (
            rf'\1Показано объектов: <strong id="visible-count">{initial}</strong>'
            rf' из <strong id="catalog-match-total">{total_cards}</strong>\2'
        ),
        text,
        count=1,
    )
    if count != 1:
        raise RuntimeError("Не удалось обновить счётчик каталога в index.html")
    INDEX_PATH.write_text(updated, encoding="utf-8")


def load_featured_order() -> list[str]:
    """Слаги, которые Дарья хочет видеть первыми на главной (data/featured-order.json)."""
    path = ROOT / "data" / "featured-order.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return [str(slug).strip() for slug in data if str(slug).strip()]
    except Exception:  # noqa: BLE001 — нет файла = прежний порядок
        return []


def rebuild_catalog(rows: list[dict[str, Any]]) -> None:
    rows = normalize_catalog_rows(rows)
    rows = [row for row in rows if row.get("is_active", True)]
    featured_rank = {slug: index for index, slug in enumerate(load_featured_order())}
    if featured_rank:
        # sort стабильный: приоритетные — в заданном порядке, остальные — как были.
        rows.sort(key=lambda row: featured_rank.get(str(row.get("slug")), len(featured_rank)))
    hotel_rows = [row for row in rows if row.get("source_kind") == "hotel"]
    kvartira_excluded = {"general-1409"}
    kvartira_rows = [
        row
        for row in rows
        if row.get("source_kind") == "kvartira" and row.get("slug") not in kvartira_excluded
    ]
    KVARTIRA_DIR.mkdir(parents=True, exist_ok=True)

    hotel_post_meta = load_hotel_card_meta()
    catalog_cards = [render_hotel_card(row, hotel_post_meta) for row in hotel_rows] + [
        render_kvartira_card(row) for row in kvartira_rows
    ]
    total_cards = len(catalog_cards)
    catalog_cards_html = mark_catalog_cards_initial_hidden(
        "".join(catalog_cards[:CATALOG_STATIC_LIMIT])
    )
    replace_catalog_block(
        INDEX_PATH,
        '<div class="catalog-grid" id="catalog-grid">',
        catalog_cards_html,
    )
    sync_catalog_grid_total_attr(total_cards)
    sync_catalog_visible_count_markup(total_cards)
    KVARTIRA_PATH.write_text(render_kvartira_catalog_page(kvartira_rows), encoding="utf-8")

    for row in hotel_rows:
        update_hotel_page(row)
    rebuild_kvartira_pages(kvartira_rows)

    rebuild_sitemap(rows)

    print(f"Пересобрано отелей: {len(hotel_rows)}")
    print(f"Пересобрано квартир: {len(kvartira_rows)}")


def fetch_listings_from_supabase() -> list[dict[str, Any]]:
    env = load_env(ENV_PATH)
    base = env["SUPABASE_URL"].rstrip("/")
    service_key = env["SUPABASE_SERVICE_ROLE_KEY"]
    headers = {"apikey": service_key, "Authorization": f"Bearer {service_key}"}

    response = requests.get(
        f"{base}/rest/v1/listings",
        headers=headers,
        params={
            "select": "id,slug,source_kind,source_message_id,title,summary,excerpt,city,location_text,beach_text,capacity_text,page_url,telegram_url,published_at,has_video,cover_url,details,is_active,listing_media(id,media_role,sort_order,public_url,storage_path,mime_type,source_url,details)",
            "is_active": "eq.true",
            "order": "published_at.desc",
            "limit": "2000",
        },
        timeout=120,
    )
    response.raise_for_status()
    return response.json()


def main() -> None:
    rebuild_catalog(fetch_listings_from_supabase())


if __name__ == "__main__":
    main()
