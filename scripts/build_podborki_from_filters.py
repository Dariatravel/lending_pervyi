#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from listing_visibility import load_hidden_slugs  # noqa: E402
from media_urls import yandex_photo_url  # noqa: E402
PODBORKI_DIR = ROOT / "podborki"
META_PATH = ROOT / "podbori_txt" / "_collection_meta.json"
INDEX_PATH = ROOT / "index.html"
KVARTIRA_INDEX_PATH = ROOT / "kvartira" / "index.html"
SITEMAP_PATH = ROOT / "sitemap.xml"
REPORT_PATH = ROOT / "output" / "podborki_from_filters_report.txt"
ASSET_VERSION_PATH = ROOT / "data" / "asset-version.txt"
SNAPSHOT_PATH = ROOT / "data" / "catalog-snapshot.json"
CANONICAL_ORIGIN = "https://абхазберег.рф"
CDN_MEDIA_BASE = "https://media.xn--80aacbklan7f0b.xn--p1ai/media"
OG_FALLBACK_IMAGE = f"{CDN_MEDIA_BASE}/branding/og-banner.png"

CITY_LABELS = {
    "ldzaa": "ЛДЗАА",
    "pitsunda": "ПИЦУНДА",
    "gagra": "ГАГРА",
    "alakhadzy": "АЛАХАДЗЫ",
    "gudauta": "ГУДАУТА",
    "new-afon": "НОВЫЙ АФОН",
    "sukhum": "СУХУМ",
    "tsandripsh": "ЦАНДРИПШ",
}
CITY_ORDER = list(CITY_LABELS)

MANUAL_SELECTION_SLUGS: dict[str, list[str]] = {
    "gory-oteli-v-gorah": [
        "bungalo-glemping-3623",
        "grass-otel-kottedzhi-v-gorah-abhazii-s-basseynom-2928",
        "dyshi-glubzhe-domiki-v-gorah-3459",
        "radonovyy-istochnik-otel-v-gorah-3064",
    ],
}
MOUNTAIN_OTHER_SLUGS = set(MANUAL_SELECTION_SLUGS["gory-oteli-v-gorah"])


@dataclass(frozen=True)
class Card:
    href: str
    title: str
    summary: str
    image: str
    alt: str
    filters: dict[str, set[str]]
    price_html: str = ""  # готовая строка «Цена от …» из карточки каталога


@dataclass(frozen=True)
class Selection:
    slug: str
    title: str
    predicate: Callable[[Card], bool]
    group_by_city: bool = True


def asset_version() -> str:
    return ASSET_VERSION_PATH.read_text(encoding="utf-8").strip()


def page_path_from_url(value: str) -> str:
    match = re.search(r"https?://[^/]+(/[^?#]*)", value or "")
    return match.group(1) if match else (value or "")


def load_manual_selection_hrefs() -> dict[str, list[str]]:
    payload = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    active_by_slug = {
        str(row.get("slug") or ""): row
        for row in payload.get("listings") or []
        if row.get("is_active", True)
    }
    out: dict[str, list[str]] = {}
    for selection_slug, slugs in MANUAL_SELECTION_SLUGS.items():
        hrefs: list[str] = []
        for slug in slugs:
            row = active_by_slug.get(slug)
            if not row:
                raise RuntimeError(f"{selection_slug}: активный объект со slug {slug!r} не найден в catalog-snapshot.json")
            kind = str(row.get("source_kind") or "")
            expected_prefix = "/hotels/" if kind == "hotel" else "/kvartira/" if kind == "kvartira" else ""
            if not expected_prefix:
                raise RuntimeError(f"{selection_slug}: у {slug!r} неизвестный source_kind={kind!r}")
            expected_href = f"{expected_prefix}{slug}/"
            page_url = str(row.get("page_url") or "")
            actual_href = page_path_from_url(page_url)
            if actual_href != expected_href:
                raise RuntimeError(
                    f"{selection_slug}: page_url для {slug!r} = {actual_href!r}, ожидалось {expected_href!r}"
                )
            hrefs.append(expected_href)
        out[selection_slug] = hrefs
    return out


def strip_tags(value: str) -> str:
    return re.sub(r"<[^>]+>", "", value)


def parse_attrs(raw: str) -> dict[str, str]:
    return {m.group(1): html.unescape(m.group(2)) for m in re.finditer(r'([\w:-]+)="([^"]*)"', raw)}


def filter_values(attrs: dict[str, str], group: str) -> set[str]:
    raw = attrs.get(f"data-filter-{group}", "")
    return {part.strip() for part in raw.split("|") if part.strip()}


def normalize_image(src: str) -> str:
    src = html.unescape(src or "").strip()
    if not src:
        return ""
    converted = yandex_photo_url(src)
    if converted.startswith("http://") or converted.startswith("https://"):
        return converted
    if src.startswith("/"):
        return "../.." + src
    if src.startswith("../"):
        return src
    return "../../" + src.lstrip("./")


def normalize_index_image(src: str) -> str:
    src = html.unescape(src or "").strip()
    if not src:
        return ""
    converted = yandex_photo_url(src)
    if converted.startswith("http://") or converted.startswith("https://"):
        return converted
    if src.startswith("/"):
        return src
    if src.startswith("../"):
        return src.lstrip("../")
    return src.lstrip("./")


def parse_catalog_cards(path: Path, prefix: str) -> list[Card]:
    text = path.read_text(encoding="utf-8")
    cards: list[Card] = []
    rx = re.compile(r'<a\s+class="catalog-card"(?P<attrs>[^>]*)>(?P<body>.*?)</a>', re.I | re.S)
    for match in rx.finditer(text):
        attrs = parse_attrs(match.group("attrs"))
        href = attrs.get("href", "")
        if not href.startswith(prefix):
            continue
        body = match.group("body")
        h3m = re.search(r"<h3>(.*?)</h3>", body, re.I | re.S)
        # Блок фактов (📍/🏖/👥) переносим как есть, вместе с <br />;
        # <p class="catalog-card__price"> сюда не попадает.
        pm = re.search(r'<p(?:\s+class="catalog-card__facts")?>(.*?)</p>', body, re.I | re.S)
        im = re.search(r"<img\b([^>]*)>", body, re.I | re.S)
        img_attrs = parse_attrs(im.group(1)) if im else {}
        title = html.unescape(strip_tags(h3m.group(1))).strip() if h3m else ""
        # summary хранит готовый inner-HTML из нашей же карточки (уже экранирован)
        summary = pm.group(1).strip() if pm else ""
        price_m = re.search(r'<p class="catalog-card__price">.*?</p>', body, re.I | re.S)
        price_html = price_m.group(0) if price_m else ""
        image = normalize_image(img_attrs.get("src", ""))
        alt = img_attrs.get("alt", "").strip() or title
        cards.append(
            Card(
                href=href,
                title=title,
                summary=summary,
                image=image,
                alt=alt or title,
                price_html=price_html,
                filters={
                    group: filter_values(attrs, group)
                    for group in ("distance", "food", "price", "city", "beach", "room", "stay")
                },
            )
        )
    return cards


def href_slug(href: str) -> str:
    match = re.match(r"^/(?:hotels|kvartira)/([^/]+)/?", href.strip())
    return match.group(1) if match else ""


def load_cards() -> list[Card]:
    """Карточки подборок строим из catalog-snapshot.json (все активные
    объекты). Раньше читали index.html, но после облегчения главной там
    только первые 24 карточки — подборки деградировали. Вёрстку берём из
    rebuild_from_supabase, чтобы совпадала с каталогом (title/факты/цена)."""
    import rebuild_from_supabase as rb

    hidden = load_hidden_slugs()
    featured = {slug: index for index, slug in enumerate(rb.load_featured_order())}
    snap = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    rows = [row for row in (snap.get("listings") or []) if row.get("is_active", True)]
    # тот же порядок, что и в каталоге: featured первыми, остальные как были
    if featured:
        rows.sort(key=lambda row: featured.get(str(row.get("slug")), len(featured)))

    kvartira_excluded = {"general-1409"}
    facts_wrapper = re.compile(r"^<p[^>]*>|</p>\s*$")
    deduped: dict[str, Card] = {}
    for row in rows:
        kind = str(row.get("source_kind") or "")
        if kind not in ("hotel", "kvartira"):
            continue
        slug = str(row.get("slug") or "")
        if not slug or slug in hidden or slug in kvartira_excluded:
            continue
        base = "hotels" if kind == "hotel" else "kvartira"
        href = f"/{base}/{slug}/"
        title = rb.clean_card_title(row.get("title") or "").strip()
        fallback = row.get("summary") or row.get("excerpt") or ((row.get("details") or {}).get("excerpt") or "")
        facts_html = rb.render_card_facts_html(row, fallback).strip()
        summary = facts_wrapper.sub("", facts_html).strip()
        image = normalize_image(rb.image_src_for_html(rb.pick_cover_url(row)))
        price_html = rb.render_card_price_html(slug)
        filters_raw = (row.get("details") or {}).get("filters") or {}
        filters = {
            group: set(filters_raw.get(group) or [])
            for group in ("distance", "food", "price", "city", "beach", "room", "stay")
        }
        deduped[href] = Card(
            href=href,
            title=title,
            summary=summary,
            image=image,
            alt=title,
            price_html=price_html,
            filters=filters,
        )
    return list(deduped.values())


def has(group: str, *values: str) -> Callable[[Card], bool]:
    expected = set(values)
    return lambda card: bool(card.filters.get(group, set()) & expected)


def any_of(*predicates: Callable[[Card], bool]) -> Callable[[Card], bool]:
    return lambda card: any(predicate(card) for predicate in predicates)


def selections() -> list[Selection]:
    return [
        Selection("doma-pod-klyuch-vse-varianty", "ДОМА ПОД КЛЮЧ", has("stay", "turnkey-house")),
        Selection("gagra-vse-varianty", "ГАГРА - варианты размещения", has("city", "gagra"), False),
        Selection("gudauta-vse-varianty", "ГУДАУТА - варианты размещения", has("city", "gudauta"), False),
        Selection("novyy-afon-vse-varianty", "НОВЫЙ АФОН - варианты размещения", has("city", "new-afon"), False),
        Selection("pitsunda-vse-varianty", "ПИЦУНДА - варианты размещения", has("city", "pitsunda"), False),
        Selection("suhum-vse-varianty", "СУХУМ - варианты размещения", has("city", "sukhum"), False),
        Selection("alahadzy-vse-varianty", "АЛАХАДЗЫ - варианты размещения", has("city", "alakhadzy"), False),
        Selection("varianty-do-5-tr-ekonom", "Варианты размещения до 5 тыс.руб в сезон", has("price", "economy")),
        Selection("varianty-5-12-tr-srednyak", "Варианты размещения от 5 до 12 тыс.руб в сезон", has("price", "midrange")),
        Selection("balkony", "С БАЛКОНОМ - варианты размещения", has("room", "balcony")),
        Selection("veranda", "С ВЕРАНДОЙ - варианты размещения", has("room", "terrace")),
        Selection("televizor-v-nomere", "С ТЕЛЕВИЗОРОМ - варианты размещения", has("room", "tv")),
        Selection("dvuhkomnatnye-i-bolee", "ДВЕ-ТРИ КОМНАТЫ - варианты размещения", has("room", "two-room-plus")),
        Selection("sobaki-varianty", "С ЖИВОТНЫМИ - варианты размещения", has("stay", "pets")),
        Selection("svoya-kuhnya-v-nomere", "СВОЯ КУХНЯ - варианты размещения", has("room", "kitchen")),
        Selection("domiki-vse-varianty", "ДОМИКИ - варианты размещения", has("stay", "cottages")),
        Selection("kvartiry-vse-varianty", "ЧАСТНЫЕ КВАРТИРЫ", has("stay", "apartments")),
        # Кнопка «Квартиры и дома под ключ» в быстрых подборках главной
        # (просьба Дарьи 27.08.2026: квартиры терялись в общем каталоге).
        Selection(
            "kvartiry-i-doma-pod-klyuch",
            "Квартиры и дома под ключ",
            any_of(has("stay", "apartments"), has("stay", "turnkey-house")),
        ),
        Selection(
            "gory-oteli-v-gorah",
            "ГОРЫ - отели в горах",
            lambda card: href_slug(card.href) in MOUNTAIN_OTHER_SLUGS,
        ),
        Selection("ldzaa-vse-varianty", "ЛДЗАА - варианты размещения", has("city", "ldzaa"), False),
        Selection("sosnovyy-plyazh", "СОСНОВЫЙ БЕРЕГ - варианты размещения", has("beach", "pine-pebble-ldzaa-pitsunda")),
        Selection("vid-na-more-pryamoy-bokovoy", "ВИД НА МОРЕ (прямой или боковой)", has("room", "sea-view")),
        Selection("basseyn-vse-varianty", "С БАССЕЙНОМ - варианты размещения", has("room", "pool")),
        Selection("pitanie-v-otele-ili-svoe-kafe", "Отели с питанием / собственным кафе", has("food", "cafe", "breakfast", "half-board", "full-board")),
        Selection("bereg-morya-oteli-na-beregu", "ЖИТЬ НА БЕРЕГУ - отели, которые расположены на пляжной линии", any_of(has("distance", "beachfront"), has("room", "beachfront-room"))),
        Selection("peschanyy-plyazh-suhum", "ПЕСЧАНЫЕ ПЛЯЖИ в Сухуме (Мокко, Марнеро, Келасур)", has("beach", "sand-sukhum")),
        Selection("peschanyy-ldzaa", "ЛДЗАА - только песчаный пляж", has("beach", "sand-ldzaa")),
        Selection("varianty-dorozhe-12-tr-premium", "ПРЕМИУМ-варианты размещения в Абхазии", has("price", "premium")),
        Selection("pyatero-gostey-i-bolee", "ПЯТЬ И БОЛЕЕ ГОСТЕЙ - варианты размещения", has("room", "five-plus")),
    ]


def city_key(card: Card) -> str:
    if href_slug(card.href) in MOUNTAIN_OTHER_SLUGS:
        return "other"
    for city in CITY_ORDER:
        if city in card.filters.get("city", set()):
            return city
    return "other"


def city_label(key: str) -> str:
    if key == "other":
        return "ДРУГИЕ ЛОКАЦИИ"
    return CITY_LABELS.get(key, "ДРУГИЕ ЛОКАЦИИ")


def accommodation_priority(card: Card) -> int:
    """Отели выше; квартиры и дома под ключ — ниже внутри того же города."""
    if card.href.startswith("/kvartira/"):
        return 2
    if "turnkey-house" in card.filters.get("stay", set()):
        return 1
    return 0


def card_sort_key(card: Card) -> tuple[int, int, str]:
    city_rank = CITY_ORDER.index(city_key(card)) if city_key(card) in CITY_ORDER else 99
    return (city_rank, accommodation_priority(card), card.title.lower())


def within_city_sort_key(card: Card) -> tuple[int, str]:
    """Порядок внутри одного города: отели → дома под ключ → квартиры, по алфавиту."""
    return (accommodation_priority(card), card.title.lower())


def cover_image_key(src: str) -> str:
    return normalize_index_image(src) or normalize_image(src) or src.strip()


def responsive_srcset(src: str) -> str:
    if not src.startswith(CDN_MEDIA_BASE):
        return ""
    if "/media/branding/" in src:
        return ""
    if not re.search(r"\.(?:jpe?g|png)$", src, flags=re.I):
        return ""
    stem = re.sub(r"\.(?:jpe?g|png)$", "", src, flags=re.I)
    return f"{stem}-480.webp 480w"


def pick_cover_card(selected: list[Card], used_images: set[str]) -> Card | None:
    """Обложка индекса подборок: первое фото объекта из подборки, ещё не занятое на странице."""
    if not selected:
        return None
    for card in selected:
        key = cover_image_key(card.image)
        if not key or key in used_images:
            continue
        used_images.add(key)
        return card
    for card in selected:
        if card.image:
            return card
    return selected[0]


def render_card(card: Card, rank: int) -> str:
    if card.image:
        srcset = responsive_srcset(card.image)
        srcset_attr = f' srcset="{html.escape(srcset)}" sizes="(max-width: 720px) 92vw, (max-width: 1180px) 45vw, 320px"' if srcset else ""
        media_inner = f'<img src="{html.escape(card.image)}"{srcset_attr} alt="{html.escape(card.alt)}" loading="lazy" decoding="async" />'
    else:
        media_inner = '<div class="catalog-card__media-fallback" role="img" aria-hidden="true">Фото</div>'
    return (
        f'          <a class="catalog-card podborki-catalog-card" href="{html.escape(card.href)}">'
        f'<div class="catalog-card__media-wrap">'
        f'<span class="catalog-card__badge catalog-card__badge--rank" aria-label="Место в подборке — {rank}">{rank}</span>'
        f"{media_inner}</div><h3>{html.escape(card.title)}</h3>"
        f'<p class="catalog-card__facts">{card.summary or " "}</p>{card.price_html}</a>'
    )


def render_page(selection: Selection, cards: list[Card], meta: dict[str, dict[str, str]], version: str) -> str:
    page_meta = meta.get(selection.slug, {})
    h1 = page_meta.get("h1") or selection.title
    page_title = page_meta.get("page_title") or f"{h1} — подборка | АБХАЗБЕРЕГ"
    description = page_meta.get("meta_description") or f"{h1}: подборка проверенных вариантов размещения в Абхазии."
    parts: list[str] = []
    rank = 0
    if selection.group_by_city:
        grouped: dict[str, list[Card]] = {}
        for card in cards:
            grouped.setdefault(city_key(card), []).append(card)
        for key in [*CITY_ORDER, "other"]:
            group_cards = sorted(grouped.get(key, []), key=within_city_sort_key)
            if not group_cards:
                continue
            parts.append(f'        <h2 class="podborki-region">{city_label(key)}</h2>')
            parts.append('        <div class="catalog-grid podborki-catalog-grid">')
            for card in group_cards:
                rank += 1
                parts.append(render_card(card, rank))
            parts.append("        </div>")
    else:
        parts.append('        <div class="catalog-grid podborki-catalog-grid">')
        for card in cards:
            rank += 1
            parts.append(render_card(card, rank))
        parts.append("        </div>")
    body_html = "\n".join(parts)
    # Картинка для превью в поиске и мессенджерах: фото первого объекта
    # подборки, а если карточек нет — брендовый баннер.
    og_image = next((card.image for card in cards if card.image), "") or OG_FALLBACK_IMAGE
    return f"""<!DOCTYPE html>
<html lang="ru" id="top">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{html.escape(page_title)}</title>
  <meta name="description" content="{html.escape(description)}" />
  <meta name="robots" content="index, follow" />
  <link rel="canonical" href="{CANONICAL_ORIGIN}/podborki/{selection.slug}/" />
  <meta property="og:type" content="website" />
  <meta property="og:title" content="{html.escape(h1)}" />
  <meta property="og:description" content="{html.escape(description)}" />
  <meta property="og:url" content="{CANONICAL_ORIGIN}/podborki/{selection.slug}/" />
  <meta property="og:image" content="{html.escape(og_image)}" />
  <link rel="preconnect" href="https://media.xn--80aacbklan7f0b.xn--p1ai" crossorigin />
  <link rel="icon" type="image/png" href="{CDN_MEDIA_BASE}/branding/favicon-48.png" />
  <link rel="stylesheet" href="../../styles.min.css?v={version}" />
</head>
<body>
  <div class="grain" aria-hidden="true"></div>
  <main class="page-shell site-concept podborki-page">
    <div class="bg-blur bg-blur--mint" aria-hidden="true"></div>
    <div class="bg-blur bg-blur--sand" aria-hidden="true"></div>

    <header class="site-concept__topbar" role="banner">
      <a class="site-concept__brand" href="/">
        <img class="site-concept__brand-mark" src="{CDN_MEDIA_BASE}/branding/logo-emblem-160.png" width="80" height="80" alt="АБХАЗБЕРЕГ — на главную" decoding="async" />
        <span class="site-concept__brand-copy">
          <strong>АБХАЗБЕРЕГ - жилье напрямую</strong>
        </span>
      </a>
      <nav class="site-concept__topnav" aria-label="Основная навигация">
        <a href="/">Главная</a>
        <a href="/podborki/">Подборки</a>
        <a href="/blog/">Полезно узнать</a>
        <a href="/#contacts">Контакты</a>
      </nav>
    </header>

    <section class="site-concept__hero-card podborki-hero">
      <p class="site-concept__eyebrow"><a href="/podborki/">Подборки</a></p>
      <h1>{html.escape(h1)}</h1>
    </section>

    <section class="site-concept__section-block podborki-body" aria-label="Список объектов">
{body_html}
    </section>
  </main>
  <script src="../../scripts.min.js?v={version}" defer></script>
  <a class="back-to-top" href="#top" aria-label="Наверх"><span class="back-to-top__icon" aria-hidden="true">↑</span></a>
</body>
</html>
"""


PODBORKI_INDEX_VISUALS: dict[str, tuple[str, str]] = {
    "doma-pod-klyuch-vse-varianty": ("homes", "дом"),
    "gagra-vse-varianty": ("gagra", "Гагра"),
    "gudauta-vse-varianty": ("gudauta", "Гудаута"),
    "novyy-afon-vse-varianty": ("afon", "Новый Афон"),
    "pitsunda-vse-varianty": ("pitsunda", "Пицунда"),
    "suhum-vse-varianty": ("suhum", "Сухум"),
    "alahadzy-vse-varianty": ("alahadzy", "Алахадзы"),
    "varianty-do-5-tr-ekonom": ("economy", "до 5 тыс."),
    "varianty-5-12-tr-srednyak": ("midrange", "5-12 тыс."),
    "balkony": ("balcony", "балкон"),
    "veranda": ("veranda", "веранда"),
    "televizor-v-nomere": ("tv", "ТВ"),
    "dvuhkomnatnye-i-bolee": ("rooms", "2-3 комнаты"),
    "sobaki-varianty": ("pets", "pet friendly"),
    "svoya-kuhnya-v-nomere": ("kitchen", "кухня"),
    "domiki-vse-varianty": ("cottages", "домики"),
    "kvartiry-vse-varianty": ("apartments", "квартира"),
    "kvartiry-i-doma-pod-klyuch": ("apartments", "квартиры и дома"),
    "gory-oteli-v-gorah": ("mountains", "горы"),
    "ldzaa-vse-varianty": ("ldzaa", "Лдзаа"),
    "sosnovyy-plyazh": ("pines", "сосны"),
    "vid-na-more-pryamoy-bokovoy": ("sea-view", "вид на море"),
    "basseyn-vse-varianty": ("pool", "бассейн"),
    "pitanie-v-otele-ili-svoe-kafe": ("cafe", "кафе"),
    "bereg-morya-oteli-na-beregu": ("beachfront", "у берега"),
    "peschanyy-plyazh-suhum": ("sand-sukhum", "песок"),
    "peschanyy-ldzaa": ("sand-ldzaa", "Лдзаа песок"),
    "varianty-dorozhe-12-tr-premium": ("premium", "premium"),
    "pyatero-gostey-i-bolee": ("guests", "5+ гостей"),
}

# Ручная обложка на индексе подборок (если авто-выбор неудачен)
PODBORKI_INDEX_COVER_OVERRIDES: dict[str, tuple[str, str]] = {
    # Домики должны выглядеть домиками: фасады снаружи, а не кровати
    # (просьба Дарьи 27.08.2026).
    "domiki-vse-varianty": (
        f"{CDN_MEDIA_BASE}/cards/sanni-houm-domiki-s-basseynom-4731.jpg",
        '"САННИ ХОУМ" домики с бассейном',
    ),
    "gudauta-vse-varianty": (
        f"{CDN_MEDIA_BASE}/cards/full-haus-domiki-s-basseynom-4092.jpg",
        '"ФУЛЛ ХАУС" домики с бассейном',
    ),
    "gory-oteli-v-gorah": (
        f"{CDN_MEDIA_BASE}/cards/bungalo-glemping-3623.jpg",
        '"БУНГАЛО" глэмпинг',
    ),
}


def render_index_link(slug: str, title: str, cover_image: str = "", cover_alt: str = "") -> str:
    visual, label = PODBORKI_INDEX_VISUALS.get(slug, ("default", "Абхазия"))
    photo_html = ""
    visual_mod = ""
    if cover_image:
        img_src = normalize_index_image(cover_image)
        if img_src:
            photo_html = (
                f'<img class="podborki-index__photo" src="{html.escape(img_src, quote=True)}" '
                f'alt="{html.escape(cover_alt or title)}" loading="lazy" decoding="async" />'
            )
            visual_mod = " podborki-index__visual--photo"
    return (
        f'        <li><a class="podborki-index__link podborki-index__link--{html.escape(visual)}" '
        f'href="/podborki/{html.escape(slug)}/">'
        f'<span class="podborki-index__visual{visual_mod}" aria-hidden="true">{photo_html}'
        f"<span>{html.escape(label)}</span></span>"
        f'<span class="podborki-index__title">{html.escape(title)}</span></a></li>'
    )


# Порядок подборок на странице /podborki/ — задан Дарьей 27.08.2026.
# Не перечисленные здесь идут после, по алфавиту названий.
PODBORKI_DISPLAY_ORDER = [
    "sosnovyy-plyazh",
    "peschanyy-ldzaa",
    "basseyn-vse-varianty",
    "varianty-dorozhe-12-tr-premium",
    "bereg-morya-oteli-na-beregu",
    "gory-oteli-v-gorah",
    "vid-na-more-pryamoy-bokovoy",
    "ldzaa-vse-varianty",
    "pitanie-v-otele-ili-svoe-kafe",
    "pitsunda-vse-varianty",
    "peschanyy-plyazh-suhum",
    "balkony",
    "gagra-vse-varianty",
    "novyy-afon-vse-varianty",
    "svoya-kuhnya-v-nomere",
    "suhum-vse-varianty",
]


def render_index(items: list[tuple[str, str, str, str]], version: str) -> str:
    order = {slug: index for index, slug in enumerate(PODBORKI_DISPLAY_ORDER)}
    ordered = sorted(
        items,
        key=lambda row: (order.get(row[0], len(order)), row[1].lower()),
    )
    links = "\n".join(
        render_index_link(slug, title, cover_image, cover_alt)
        for slug, title, cover_image, cover_alt in ordered
    )
    return f"""<!DOCTYPE html>
<html lang="ru" id="top">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Подборки жилья в Абхазии — АБХАЗБЕРЕГ</title>
  <meta name="description" content="Тематические подборки отелей, домов и квартир в Абхазии: море, бюджет, удобства, локации." />
  <link rel="canonical" href="{CANONICAL_ORIGIN}/podborki/" />
  <meta property="og:type" content="website" />
  <meta property="og:title" content="Подборки жилья в Абхазии" />
  <meta property="og:description" content="Тематические подборки отелей, домов и квартир в Абхазии: море, бюджет, удобства, локации." />
  <meta property="og:url" content="{CANONICAL_ORIGIN}/podborki/" />
  <meta property="og:image" content="{OG_FALLBACK_IMAGE}" />
  <link rel="preconnect" href="https://media.xn--80aacbklan7f0b.xn--p1ai" crossorigin />
  <link rel="icon" type="image/png" href="{CDN_MEDIA_BASE}/branding/favicon-48.png" />
  <link rel="stylesheet" href="../styles.min.css?v={version}" />
</head>
<body>
  <div class="grain" aria-hidden="true"></div>
  <main class="page-shell site-concept podborki-page">
    <div class="bg-blur bg-blur--mint" aria-hidden="true"></div>
    <div class="bg-blur bg-blur--sand" aria-hidden="true"></div>
    <header class="site-concept__topbar" role="banner">
      <a class="site-concept__brand" href="/">
        <img class="site-concept__brand-mark" src="{CDN_MEDIA_BASE}/branding/logo-emblem-160.png" width="80" height="80" alt="АБХАЗБЕРЕГ — на главную" decoding="async" />
        <span class="site-concept__brand-copy"><strong>АБХАЗБЕРЕГ - жилье напрямую</strong></span>
      </a>
      <nav class="site-concept__topnav" aria-label="Основная навигация">
        <a href="/">Главная</a>
        <a href="/podborki/" aria-current="page">Подборки</a>
        <a href="/blog/">Полезно узнать</a>
        <a href="#contacts">Контакты</a>
      </nav>
    </header>
    <section class="site-concept__section-block podborki-index-panel">
      <div class="podborki-index-head">
        <h1>Подборки жилья</h1>
        <p class="podborki-index-head__lead">Выберите подборку под свой формат отдыха</p>
        <p>Собрали варианты по городам, бюджету, пляжам и удобствам, чтобы не листать весь каталог вручную.</p>
      </div>
      <ul class="podborki-index-list">
{links}
      </ul>
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
        </div>
        <div class="contact-channel-panel">
<div class="contact-channel-grid">
<a class="contact-channel-card" href="https://vk.cc/cQQnBn" rel="noopener noreferrer" target="_blank">
<span aria-hidden="true" class="contact-channel-card__icon contact-channel-card__icon--vk"></span>
<span class="contact-channel-card__copy"><strong>ВКонтакте</strong><small>Самый быстрый ответ</small></span>
<span aria-hidden="true" class="contact-channel-card__arrow">→</span>
</a>
<a class="contact-channel-card" href="https://max.ru/id741113115256_bot" rel="noopener noreferrer" target="_blank">
<span aria-hidden="true" class="contact-channel-card__icon contact-channel-card__icon--max"></span>
<span class="contact-channel-card__copy"><strong>MAX</strong><small>Только сообщения</small></span>
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
  </main>
  <script src="../scripts.min.js?v={version}" defer></script>
  <a class="back-to-top" href="#top" aria-label="Наверх"><span class="back-to-top__icon" aria-hidden="true">↑</span></a>
</body>
</html>
"""


def update_sitemap(slugs: list[str]) -> None:
    ET.register_namespace("", "http://www.sitemaps.org/schemas/sitemap/0.9")
    tree = ET.parse(SITEMAP_PATH)
    root = tree.getroot()
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    existing = {loc.text for loc in root.findall("sm:url/sm:loc", ns) if loc.text}
    urls = [f"{CANONICAL_ORIGIN}/podborki/"] + [f"{CANONICAL_ORIGIN}/podborki/{slug}/" for slug in slugs]
    for url in urls:
        if url in existing:
            continue
        node = ET.SubElement(root, "{http://www.sitemaps.org/schemas/sitemap/0.9}url")
        loc = ET.SubElement(node, "{http://www.sitemaps.org/schemas/sitemap/0.9}loc")
        loc.text = url
    tree.write(SITEMAP_PATH, encoding="utf-8", xml_declaration=True)


def main() -> int:
    version = asset_version()
    manual_selection_hrefs = load_manual_selection_hrefs()
    meta = json.loads(META_PATH.read_text(encoding="utf-8")) if META_PATH.is_file() else {}
    cards = load_cards()
    report = [
        "Подборки пересобраны по data-filter-* из каталога.",
        "Источник data-filter-* — Google Sheet СОЦСЕТИ через apply_all_filters_from_sheet.py.",
        "",
        f"Карточек в каталоге: {len(cards)}",
        "",
    ]
    index_items: list[tuple[str, str, str, str]] = []
    slugs: list[str] = []
    used_cover_images: set[str] = set()
    cards_by_href = {card.href: card for card in cards}
    for selection in selections():
        manual_hrefs = manual_selection_hrefs.get(selection.slug)
        if manual_hrefs:
            missing = [href for href in manual_hrefs if href not in cards_by_href]
            if missing:
                raise RuntimeError(f"{selection.slug}: карточки из ручного списка не найдены в index.html: {', '.join(missing)}")
            selected = [cards_by_href[href] for href in manual_hrefs]
            page_selection = Selection(selection.slug, selection.title, selection.predicate, group_by_city=False)
        else:
            selected = [card for card in cards if selection.predicate(card)]
            selected = sorted(selected, key=card_sort_key)
            page_selection = selection
        out_dir = PODBORKI_DIR / selection.slug
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "index.html").write_text(render_page(page_selection, selected, meta, version), encoding="utf-8")
        title = meta.get(selection.slug, {}).get("h1") or selection.title
        cover_card = pick_cover_card(selected, used_cover_images)
        override = PODBORKI_INDEX_COVER_OVERRIDES.get(selection.slug)
        if override:
            cover_image, cover_alt = override
            key = cover_image_key(cover_image)
            if key:
                used_cover_images.add(key)
        else:
            cover_image = cover_card.image if cover_card else ""
            cover_alt = cover_card.alt if cover_card else title
        index_items.append((selection.slug, title, cover_image, cover_alt))
        slugs.append(selection.slug)
        report.append(f"- {selection.slug}: {len(selected)}")
    PODBORKI_DIR.mkdir(parents=True, exist_ok=True)
    (PODBORKI_DIR / "index.html").write_text(render_index(index_items, version), encoding="utf-8")
    update_sitemap(slugs)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n".join(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
