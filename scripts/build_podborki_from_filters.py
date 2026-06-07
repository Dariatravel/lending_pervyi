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
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from listing_visibility import load_hidden_slugs  # noqa: E402
PODBORKI_DIR = ROOT / "podborki"
META_PATH = ROOT / "podbori_txt" / "_collection_meta.json"
INDEX_PATH = ROOT / "index.html"
KVARTIRA_INDEX_PATH = ROOT / "kvartira" / "index.html"
SITEMAP_PATH = ROOT / "sitemap.xml"
REPORT_PATH = ROOT / "output" / "podborki_from_filters_report.txt"
CSS_VERSION = "202605272305"
CANONICAL_ORIGIN = "https://абхазберег.рф"
STORAGE_PUBLIC_IMAGE_MARKER = "/storage/v1/object/public/site-media/"
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".gif")

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
# Горные объекты без привязки к побережью — только они попадают в «ДРУГИЕ ЛОКАЦИИ».
MOUNTAIN_OTHER_HREFS = {
    "/hotels/bungalo-glemping-3623/",
    "/hotels/grass-otel-kottedzhi-v-gorah-abhazii-s-basseynom-2928/",
    "/hotels/dyshi-glubzhe-domiki-v-gorah-3459/",
    "/hotels/radonovyy-istochnik-otel-v-gorah-3064/",
}


@dataclass(frozen=True)
class Card:
    href: str
    title: str
    summary: str
    image: str
    alt: str
    filters: dict[str, set[str]]


@dataclass(frozen=True)
class Selection:
    slug: str
    title: str
    predicate: Callable[[Card], bool]
    group_by_city: bool = True


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
    if STORAGE_PUBLIC_IMAGE_MARKER in src:
        relative = src.split(STORAGE_PUBLIC_IMAGE_MARKER, 1)[1].split("?", 1)[0]
        if relative.lower().endswith(IMAGE_EXTENSIONS):
            return "../../media/" + unquote(relative)
    if src.startswith("http://") or src.startswith("https://"):
        return src
    if src.startswith("/"):
        return "../.." + src
    if src.startswith("../"):
        return src
    return "../../" + src.lstrip("./")


def normalize_index_image(src: str) -> str:
    src = html.unescape(src or "").strip()
    if not src:
        return ""
    if STORAGE_PUBLIC_IMAGE_MARKER in src:
        relative = src.split(STORAGE_PUBLIC_IMAGE_MARKER, 1)[1].split("?", 1)[0]
        if relative.lower().endswith(IMAGE_EXTENSIONS):
            return "../media/" + unquote(relative)
    if src.startswith("http://") or src.startswith("https://"):
        return src
    if src.startswith("../../"):
        return ".." + src[5:]
    if src.startswith("../"):
        return src
    if src.startswith("/"):
        return ".." + src
    return "../" + src.lstrip("./")


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
        pm = re.search(r"<p>(.*?)</p>", body, re.I | re.S)
        im = re.search(r"<img\b([^>]*)>", body, re.I | re.S)
        img_attrs = parse_attrs(im.group(1)) if im else {}
        title = html.unescape(strip_tags(h3m.group(1))).strip() if h3m else ""
        summary = html.unescape(strip_tags(pm.group(1))).strip() if pm else ""
        image = normalize_image(img_attrs.get("src", ""))
        alt = img_attrs.get("alt", "").strip() or title
        cards.append(
            Card(
                href=href,
                title=title,
                summary=summary,
                image=image,
                alt=alt or title,
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
    hidden = load_hidden_slugs()
    cards = parse_catalog_cards(INDEX_PATH, "/hotels/")
    if KVARTIRA_INDEX_PATH.is_file():
        cards.extend(parse_catalog_cards(KVARTIRA_INDEX_PATH, "/kvartira/"))
    deduped: dict[str, Card] = {}
    for card in cards:
        if href_slug(card.href) in hidden:
            continue
        deduped[card.href] = card
    return list(deduped.values())


def has(group: str, *values: str) -> Callable[[Card], bool]:
    expected = set(values)
    return lambda card: bool(card.filters.get(group, set()) & expected)


def any_of(*predicates: Callable[[Card], bool]) -> Callable[[Card], bool]:
    return lambda card: any(predicate(card) for predicate in predicates)


def keyword(*needles: str) -> Callable[[Card], bool]:
    lowered = tuple(needle.lower() for needle in needles)
    return lambda card: any(needle in f"{card.title} {card.summary}".lower() for needle in lowered)


def selections() -> list[Selection]:
    return [
        Selection("doma-pod-klyuch-vse-varianty", "Варианты домов под ключ", has("stay", "turnkey-house")),
        Selection("gagra-vse-varianty", "Варианты размещения в г. Гагра", has("city", "gagra"), False),
        Selection("gudauta-vse-varianty", "Варианты размещения в г. Гудаута", has("city", "gudauta"), False),
        Selection("novyy-afon-vse-varianty", "Варианты размещения в г. Новый Афон", has("city", "new-afon"), False),
        Selection("pitsunda-vse-varianty", "Варианты размещения в г. Пицунда", has("city", "pitsunda"), False),
        Selection("suhum-vse-varianty", "Варианты размещения в г. Сухуме", has("city", "sukhum"), False),
        Selection("alahadzy-vse-varianty", "Варианты размещения в пос. Алахадзы", has("city", "alakhadzy"), False),
        Selection("varianty-do-5-tr-ekonom", "Варианты размещения до 5 тыс.руб в сезон", has("price", "economy")),
        Selection("varianty-5-12-tr-srednyak", "Варианты размещения от 5 до 12 тыс.руб в сезон", has("price", "midrange")),
        Selection("balkony", "Варианты размещения с балконом", has("room", "balcony")),
        Selection("veranda", "Варианты размещения с верандой", has("room", "terrace")),
        Selection("dvuhkomnatnye-i-bolee", "Варианты размещения с двумя/тремя комнатами", has("room", "two-room-plus")),
        Selection("sobaki-varianty", "Варианты размещения с животными", has("stay", "pets")),
        Selection("svoya-kuhnya-v-nomere", "Варианты размещения с собственной кухней", has("room", "kitchen")),
        Selection("domiki-vse-varianty", "Варианты с отдельными домиками", has("stay", "cottages")),
        Selection("kvartiry-vse-varianty", "Варианты частных квартир", has("stay", "apartments")),
        Selection(
            "gory-oteli-v-gorah",
            "Горы - отели в горах",
            any_of(keyword("гор", "ущель", "источник"), lambda card: card.href in MOUNTAIN_OTHER_HREFS),
        ),
        Selection("ldzaa-vse-varianty", "Именно в Лдзаа есть такие варианты", has("city", "ldzaa"), False),
        Selection("sosnovyy-plyazh", "На пляже с соснами у меня есть варианты", has("beach", "pine-pebble-ldzaa-pitsunda")),
        Selection("vid-na-more-pryamoy-bokovoy", "Объекты, номера в которых имеют вид на море (прямой или боковой)", has("room", "sea-view")),
        Selection("basseyn-vse-varianty", "Отели с бассейном", has("room", "pool")),
        Selection("pitanie-v-otele-ili-svoe-kafe", "Отели с питанием / собственным кафе", has("food", "cafe", "breakfast", "half-board", "full-board")),
        Selection("bereg-morya-oteli-na-beregu", "Отели, которые расположены прямо на пляже, у берега", any_of(has("distance", "beachfront"), has("room", "beachfront-room"))),
        Selection("peschanyy-plyazh-suhum", "Песчаные пляжи в Сухуме (Мокко, Марнеро, Келасур)", has("beach", "sand-sukhum")),
        Selection("peschanyy-ldzaa", "Песчаный пляж в Лдзаа", has("beach", "sand-ldzaa")),
        Selection("varianty-dorozhe-12-tr-premium", "Премиум-варианты размещения в Абхазии", has("price", "premium")),
        Selection("pyatero-gostey-i-bolee", "С размещением 5+ гостей варианты", has("room", "five-plus")),
    ]


def city_key(card: Card) -> str:
    if card.href in MOUNTAIN_OTHER_HREFS:
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
        media_inner = f'<img src="{html.escape(card.image)}" alt="{html.escape(card.alt)}" loading="lazy" decoding="async" />'
    else:
        media_inner = '<div class="catalog-card__media-fallback" role="img" aria-hidden="true">Фото</div>'
    return (
        f'          <a class="catalog-card podborki-catalog-card" href="{html.escape(card.href)}">'
        f'<div class="catalog-card__media-wrap">'
        f'<span class="catalog-card__badge catalog-card__badge--rank" aria-label="Место в подборке — {rank}">{rank}</span>'
        f"{media_inner}</div><h3>{html.escape(card.title)}</h3><p>{html.escape(card.summary) or ' '}</p></a>"
    )


def render_page(selection: Selection, cards: list[Card], meta: dict[str, dict[str, str]]) -> str:
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
        for card in sorted(cards, key=card_sort_key):
            rank += 1
            parts.append(render_card(card, rank))
        parts.append("        </div>")
    body_html = "\n".join(parts)
    return f"""<!DOCTYPE html>
<html lang="ru" id="top">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{html.escape(page_title)}</title>
  <meta name="description" content="{html.escape(description)}" />
  <meta name="robots" content="index, follow" />
  <link rel="canonical" href="{CANONICAL_ORIGIN}/podborki/{selection.slug}/" />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link rel="preconnect" href="https://chnyazvybzzryduhgopa.supabase.co" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;700;800&family=Prata&display=swap" rel="stylesheet" />
  <link rel="icon" type="image/png" href="../../media/branding/favicon-abhazbereg.png" />
  <link rel="stylesheet" href="../../styles.css?v={CSS_VERSION}" />
</head>
<body>
  <div class="grain" aria-hidden="true"></div>
  <main class="page-shell site-concept podborki-page">
    <div class="bg-blur bg-blur--mint" aria-hidden="true"></div>
    <div class="bg-blur bg-blur--sand" aria-hidden="true"></div>

    <header class="site-concept__topbar" role="banner">
      <a class="site-concept__brand" href="/">
        <img class="site-concept__brand-mark" src="../../media/branding/logo-emblem.png" width="80" height="80" alt="АБХАЗБЕРЕГ — на главную" decoding="async" />
        <span class="site-concept__brand-copy">
          <strong>АБХАЗБЕРЕГ - жилье напрямую</strong>
        </span>
      </a>
      <nav class="site-concept__topnav" aria-label="Основная навигация">
        <a href="/">Главная</a>
        <a href="/podborki/">Подборки</a>
        <a href="/kvartira/">Квартиры и дома</a>
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
  <script src="../../image-lite.js" defer></script>
  <script src="../../scripts.js" defer></script>
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
    "dvuhkomnatnye-i-bolee": ("rooms", "2-3 комнаты"),
    "sobaki-varianty": ("pets", "pet friendly"),
    "svoya-kuhnya-v-nomere": ("kitchen", "кухня"),
    "domiki-vse-varianty": ("cottages", "домики"),
    "kvartiry-vse-varianty": ("apartments", "квартира"),
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
    "gudauta-vse-varianty": (
        "/media/cards/full-haus-domiki-s-basseynom-4092.jpg",
        '"ФУЛЛ ХАУС" домики с бассейном',
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


def render_index(items: list[tuple[str, str, str, str]]) -> str:
    links = "\n".join(
        render_index_link(slug, title, cover_image, cover_alt)
        for slug, title, cover_image, cover_alt in sorted(items, key=lambda row: row[1].lower())
    )
    return f"""<!DOCTYPE html>
<html lang="ru" id="top">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Подборки жилья в Абхазии — АБХАЗБЕРЕГ</title>
  <meta name="description" content="Тематические подборки отелей, домов и квартир в Абхазии: море, бюджет, удобства, локации." />
  <link rel="canonical" href="{CANONICAL_ORIGIN}/podborki/" />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link rel="preconnect" href="https://chnyazvybzzryduhgopa.supabase.co" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;700;800&family=Prata&display=swap" rel="stylesheet" />
  <link rel="icon" type="image/png" href="../media/branding/favicon-abhazbereg.png" />
  <link rel="stylesheet" href="../styles.css?v={CSS_VERSION}" />
</head>
<body>
  <div class="grain" aria-hidden="true"></div>
  <main class="page-shell site-concept podborki-page">
    <div class="bg-blur bg-blur--mint" aria-hidden="true"></div>
    <div class="bg-blur bg-blur--sand" aria-hidden="true"></div>
    <header class="site-concept__topbar" role="banner">
      <a class="site-concept__brand" href="/">
        <img class="site-concept__brand-mark" src="../media/branding/logo-emblem.png" width="80" height="80" alt="АБХАЗБЕРЕГ — на главную" decoding="async" />
        <span class="site-concept__brand-copy"><strong>АБХАЗБЕРЕГ - жилье напрямую</strong></span>
      </a>
      <nav class="site-concept__topnav" aria-label="Основная навигация">
        <a href="/">Главная</a>
        <a href="/podborki/" aria-current="page">Подборки</a>
        <a href="/kvartira/">Квартиры и дома</a>
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
            <span class="contact-messengers">(WhatsApp, Telegram, MAX, VK)</span>
          </p>
          <p class="note">Только сообщения, обычный звонок не пройдёт.</p>
        </div>
        <div class="contact-buttons">
          <a class="btn-book" href="https://max.ru/abhazbereg" rel="noopener noreferrer" target="_blank">НАПИСАТЬ В MAX</a>
          <a class="btn-book" href="https://vk.cc/cQQnBn" rel="noopener noreferrer" target="_blank">НАПИСАТЬ В ВК</a>
          <a class="btn-book" href="https://t.me/abhazbooking_online" rel="noopener noreferrer" target="_blank">НАПИСАТЬ В TELEGRAM</a>
          <a class="btn-book" href="https://wa.me/79409003340" rel="noopener noreferrer" target="_blank">НАПИСАТЬ В WHATSAPP</a>
        </div>
      </article>
    </section>
  </main>
  <script src="../image-lite.js" defer></script>
  <script src="../scripts.js" defer></script>
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
    for selection in selections():
        selected = [card for card in cards if selection.predicate(card)]
        selected = sorted(selected, key=card_sort_key)
        out_dir = PODBORKI_DIR / selection.slug
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "index.html").write_text(render_page(selection, selected, meta), encoding="utf-8")
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
    (PODBORKI_DIR / "index.html").write_text(render_index(index_items), encoding="utf-8")
    update_sitemap(slugs)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n".join(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
