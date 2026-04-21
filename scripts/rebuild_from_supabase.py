from __future__ import annotations

import html
import json
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

import requests


ROOT = Path("/Users/darya_botova/Documents/New project")
ENV_PATH = ROOT / ".env.supabase.local"
INDEX_PATH = ROOT / "index.html"
KVARTIRA_DIR = ROOT / "kvartira"
KVARTIRA_PATH = ROOT / "kvartira" / "index.html"
SITEMAP_PATH = ROOT / "sitemap.xml"
HOTEL_POSTS_PATH = ROOT / "output" / "abhazbooking_2026_posts.json"


FILTER_GROUPS = ("distance", "food", "price", "city", "beach", "room", "stay")
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

OLD_PRICE_MAP = {
    "up-to-3000": "economy",
    "up-to-4000": "economy",
    "up-to-5000": "economy",
    "up-to-6000": "midrange",
    "up-to-7000": "midrange",
    "up-to-8000": "midrange",
    "up-to-9000": "midrange",
    "up-to-10000": "midrange",
}

OLD_BEACH_MAP = {
    "sand": "sand-ldzaa",
    "pine-pebble": "pine-pebble-ldzaa-pitsunda",
    "mixed": "pitsunda-bay-mixed",
    "pebble": "pebble",
}

OLD_ROOM_MAP = {
    "two-room": "two-room-plus",
    "beachfront": "beachfront-room",
}

LABEL_VALUE_MAP = {
    "price": {
        "эконом до 5000 руб. за номер": "economy",
        "эконом и комфорт до 5000 руб.": "economy",
        "от 5000 до 10000 руб. за номер": "midrange",
        "средний бюджет до 10000 руб.": "midrange",
        "премиум-сегмент": "premium",
    },
    "beach": {
        "песчаный пляж лдзаа": "sand-ldzaa",
        "песчаный пляж сухум": "sand-sukhum",
        "сосновый галечный берег лдзаа и пицунда": "pine-pebble-ldzaa-pitsunda",
        "пицундская бухта (мелкая галька и песок)": "pitsunda-bay-mixed",
        "галечные пляжи": "pebble",
    },
    "room": {
        "вид на море": "sea-view",
        "прямо на берегу": "beachfront-room",
        "берег моря. отели на берегу": "beachfront-room",
        "бассейн": "pool",
        "с балконом": "balcony",
        "с террасой": "terrace",
        "своя кухня в номере": "kitchen",
        "пять гостей и более": "five-plus",
        "две комнаты и более": "two-room-plus",
    },
    "stay": {
        "домики и коттеджи": "cottages",
        "квартиры": "apartments",
        "дома под ключ": "turnkey-house",
        "можно с животными": "pets",
        "без маленьких детей": "no-small-kids",
    },
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


def get_text_from_page(page_path: str) -> str:
    path = Path(page_path)
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8")
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text)).strip()


def text_blob(row: dict[str, Any]) -> str:
    parts = [
        row.get("title") or "",
        row.get("summary") or "",
        row.get("excerpt") or "",
        row.get("city") or "",
        ((row.get("details") or {}).get("lead") or ""),
    ]
    page_path = ((row.get("details") or {}).get("page_path") or "")
    if page_path:
        parts.append(get_text_from_page(page_path))
    return " ".join(parts).lower()


def detect_distance(blob: str) -> list[str]:
    values: list[str] = []
    beachfront_phrases = (
        "на первой линии",
        "прямо на пляже",
        "выход из отеля сразу на пляж",
        "выход к морю сразу",
        "вышел за калитку и вот оно",
    )
    beachfront_regex = (
        r"(?:^|\D)0\s*(?:минут|мин)\s*(?:до\s*)?(?:моря|пляжа)",
        r"(?:^|\D)100\s*шаг(?:ов|а)?\s*до",
    )
    if any(phrase in blob for phrase in beachfront_phrases) or any(re.search(pattern, blob) for pattern in beachfront_regex):
        values.append("beachfront")

    minutes = [int(match) for match in re.findall(r"(\d{1,2})\s*(?:минут|минуты|мин|минутах)", blob)]
    if minutes:
        best = min(minutes)
        if best <= 5:
            values.append("up-to-5")
        elif best <= 10:
            values.append("up-to-10")
        else:
            values.append("over-10")
    elif "пляж в шаговой доступности" in blob:
        values.append("up-to-5")

    return sorted(set(values), key=values.index)


def detect_food(blob: str) -> list[str]:
    values: list[str] = []
    if "полупансион" in blob:
        values.append("half-board")
    if any(marker in blob for marker in ("завтрак, обед, ужин", "трехразовое питание", "трёхразовое питание")):
        values.append("full-board")
    if "завтрак" in blob:
        values.append("breakfast")
    if any(marker in blob for marker in ("кафе", "столов", "ресторан", "своя столовая")):
        values.append("cafe")
    if any(marker in blob for marker in ("без питания", "питания нет")):
        values.append("no-food")
    return sorted(set(values), key=values.index)


def detect_price(blob: str) -> list[str]:
    prices = [int(match) for match in re.findall(r"(?<!\d)(\d{3,5})(?:\s*(?:₽|руб|р\b|р/сут|р\.)|\s*/\s*сут|\s*сутк)", blob)]
    if not prices:
        prices = [int(match) for match in re.findall(r"(?<!\d)(\d{3,5})(?!\d)\s*(?:₽|руб|р\b|р\.)", blob)]
    if not prices:
        return []
    value = max(prices)
    if value <= 5000:
        return ["economy"]
    if value <= 10000:
        return ["midrange"]
    return ["premium"]


def detect_city(blob: str) -> list[str]:
    values: list[str] = []
    for key, markers in CITY_MAP.items():
        if any(marker in blob for marker in markers):
            values.append(key)
    return values


def detect_beach(blob: str, city_values: list[str]) -> list[str]:
    values: list[str] = []
    city_set = set(city_values)
    is_sukhum = "sukhum" in city_set
    is_ldzaa_or_pitsunda = "ldzaa" in city_set or "pitsunda" in city_set

    if any(marker in blob for marker in ("соснов", "сосновый пляж")) and is_ldzaa_or_pitsunda:
        values.append("pine-pebble-ldzaa-pitsunda")

    if any(marker in blob for marker in ("пицундская бухта",)):
        values.append("pitsunda-bay-mixed")

    if "песчан" in blob and "галеч" in blob:
        values.append("pitsunda-bay-mixed" if is_ldzaa_or_pitsunda else "pebble")
    elif "песчан" in blob or "песок" in blob:
        values.append("sand-sukhum" if is_sukhum else "sand-ldzaa")

    if "галеч" in blob or "гальк" in blob:
        values.append("pebble")
    return sorted(set(values), key=values.index)


def detect_room(blob: str) -> list[str]:
    values: list[str] = []
    if any(marker in blob for marker in ("вид на море", "с видом на море")):
        values.append("sea-view")
    if any(marker in blob for marker in ("прямо на берегу", "отели на берегу", "на берегу моря", "на первой линии")):
        values.append("beachfront-room")
    if "балкон" in blob:
        values.append("balcony")
    if "террас" in blob:
        values.append("terrace")
    if "бассейн" in blob:
        values.append("pool")
    if any(marker in blob for marker in ("двухкомнат", "2к", "2-к")):
        values.append("two-room-plus")
    guest_counts = [int(match) for match in re.findall(r"до\s*(\d{1,2})\s*(?:чел|человек|гостей)", blob)]
    if guest_counts and max(guest_counts) >= 5:
        values.append("five-plus")
    if "кухн" in blob:
        values.append("kitchen")
    return sorted(set(values), key=values.index)


def detect_stay(blob: str, row: dict[str, Any]) -> list[str]:
    values: list[str] = []
    if any(marker in blob for marker in ("дом под ключ",)):
        values.append("turnkey-house")
    if any(marker in blob for marker in ("домик", "коттедж", "шале", "бунгало", "глэмпинг", "glemping", "glamping")):
        values.append("cottages")
    if any(marker in blob for marker in ("квартир", "апартамент", "студи")):
        values.append("apartments")
    if any(marker in blob for marker in ("с животными", "с питомц", "с собачк", "pet friendly")):
        values.append("pets")
    if any(marker in blob for marker in ("без маленьких детей", "без детей до", "только взрослые")):
        values.append("no-small-kids")

    source_kind = str(row.get("source_kind") or "")
    title_blob = str(row.get("title") or "").lower()
    if source_kind == "kvartira" and "apartments" not in values:
        values.append("apartments")
    if "дом под ключ" in title_blob and "turnkey-house" not in values:
        values.append("turnkey-house")
    return sorted(set(values), key=values.index)


def normalize_existing_filters(row: dict[str, Any], inferred: dict[str, list[str]]) -> dict[str, list[str]]:
    details = row.get("details") or {}
    raw = details.get("filters") or {}
    if not isinstance(raw, dict):
        return inferred

    normalized: dict[str, list[str]] = {}
    for group in FILTER_GROUPS:
        values = raw.get(group) or []
        if isinstance(values, str):
            values = [value for value in values.split("|") if value]
        if not isinstance(values, list):
            values = []
        cleaned = [str(value).strip() for value in values if str(value).strip()]
        cleaned = [LABEL_VALUE_MAP.get(group, {}).get(value.lower(), value) for value in cleaned]

        if group == "price":
            mapped = [OLD_PRICE_MAP.get(value, value) for value in cleaned]
            cleaned = mapped
        elif group == "beach":
            mapped: list[str] = []
            for value in cleaned:
                if value == "sand":
                    mapped.append("sand-sukhum" if "sukhum" in inferred.get("city", []) else "sand-ldzaa")
                else:
                    mapped.append(OLD_BEACH_MAP.get(value, value))
            cleaned = mapped
        elif group == "room":
            mapped = [OLD_ROOM_MAP.get(value, value) for value in cleaned if value not in {"one-room", "ac"}]
            cleaned = mapped
        elif group == "stay":
            cleaned = [value for value in cleaned if value != "kids"]

        normalized[group] = sorted(set(cleaned), key=cleaned.index)

    merged: dict[str, list[str]] = {}
    for group in FILTER_GROUPS:
        merged_values = normalized.get(group) or inferred.get(group) or []
        merged[group] = sorted(set(merged_values), key=merged_values.index)
    return merged


def infer_filters(row: dict[str, Any]) -> dict[str, list[str]]:
    blob = text_blob(row)
    city_values = detect_city(blob)
    inferred = {
        "distance": detect_distance(blob),
        "food": detect_food(blob),
        "price": detect_price(blob),
        "city": city_values,
        "beach": detect_beach(blob, city_values),
        "room": detect_room(blob),
        "stay": detect_stay(blob, row),
    }
    return normalize_existing_filters(row, inferred)


def pick_cover_url(row: dict[str, Any]) -> str:
    media = sorted(row.get("listing_media") or [], key=lambda item: item.get("sort_order") or 0)
    for item in media:
        if item.get("media_role") == "card" and item.get("public_url"):
            return item["public_url"]
    for item in media:
        if item.get("public_url") and str(item.get("mime_type") or "").startswith("image/"):
            return item["public_url"]
    return row.get("cover_url") or ""


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


def ensure_prefixed_line(value: str | None, emoji: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text.startswith(("📍", "🏖", "🏝")):
        return text
    return f"{emoji} {text}"


def extract_lines_from_summary(value: str | None) -> tuple[str, str]:
    source = str(value or "")
    if not source.strip():
        return "", ""
    raw_lines = [part.strip() for part in re.split(r"<br\s*/?>|\n", source) if part.strip()]
    location_line = ""
    beach_line = ""
    for line in raw_lines:
        lowered = line.lower()
        if not location_line and ("📍" in line or "ул." in lowered or "улиц" in lowered or "пос." in lowered):
            location_line = ensure_prefixed_line(line.replace("📍", "").strip(), "📍")
            continue
        if not beach_line and ("🏖" in line or "🏝" in line or "пляж" in lowered or "мор" in lowered):
            beach_line = ensure_prefixed_line(line.replace("🏖", "").replace("🏝", "").strip(), "🏖")
    return location_line, beach_line


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


def render_hotel_card(row: dict[str, Any], post_meta: dict[int, dict[str, str]]) -> str:
    filters = (row.get("details") or {}).get("filters") or {}
    attrs = " ".join(
        f'data-filter-{group}="{html.escape("|".join(filters.get(group) or []), quote=True)}"'
        for group in FILTER_GROUPS
    )
    href = page_path_from_url(row.get("page_url"), f"/hotels/{row['slug']}/")
    image = pick_cover_url(row)
    title = html.escape(row.get("title") or "")
    summary_fallback = row.get("summary") or row.get("excerpt") or ""
    card_lines: list[str] = []

    location_line = ensure_prefixed_line(row.get("location_text"), "📍")
    beach_line = ensure_prefixed_line(row.get("beach_text"), "🏖")
    source_message_id = resolve_source_message_id(row)
    if source_message_id is not None:
        meta = post_meta.get(source_message_id) or {}
        if not location_line and meta.get("location_line"):
            location_line = ensure_prefixed_line(meta["location_line"], "📍")
        if not beach_line and meta.get("beach_line"):
            beach_line = ensure_prefixed_line(meta["beach_line"], "🏖")

    if not location_line or not beach_line:
        location_from_summary, beach_from_summary = extract_lines_from_summary(summary_fallback)
        if not location_line and location_from_summary:
            location_line = location_from_summary
        if not beach_line and beach_from_summary:
            beach_line = beach_from_summary

    if location_line:
        card_lines.append(location_line)
    if beach_line:
        card_lines.append(beach_line)

    if card_lines:
        summary_html = "<br />".join(html.escape(line) for line in card_lines)
    else:
        summary_html = html.escape(summary_fallback)
    alt = title
    return (
        f'<a class="catalog-card" {attrs} href="{html.escape(href, quote=True)}">'
        f'<img alt="{alt}" loading="lazy" src="{html.escape(image, quote=True)}"/>'
        f"<h3>{title}</h3>"
        f"<p>{summary_html}</p>"
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
    href = page_path_from_url(row.get("page_url"), row.get("telegram_url") or "/kvartira/")
    title = html.escape(row.get("title") or "")
    summary = html.escape(row.get("summary") or row.get("excerpt") or ((row.get("details") or {}).get("excerpt") or ""))
    image = pick_cover_url(row)
    badge = '<span class="catalog-card__badge">Видео</span>' if row.get("has_video") else ""
    return (
        f'<a class="catalog-card" href="{html.escape(href, quote=True)}">'
        f'<div class="catalog-card__media-wrap">{badge}<img src="{html.escape(image, quote=True)}" alt="{title}" loading="lazy" /></div>'
        f"<h3>{title}</h3>"
        f"<p>{summary}</p>"
        f"</a>"
    )


def render_kvartira_catalog_page(rows: list[dict[str, Any]]) -> str:
    grid = "".join(render_kvartira_card(row) for row in rows)
    return f"""<!doctype html>
<html lang="ru">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Квартиры и дома — Абхазия 2026</title>
    <meta name="description" content="Каталог квартир и домов из @abhkvartira: отдельная карточка товара на каждый объект, с фото, видео и описанием из Telegram." />
    <meta name="robots" content="index, follow, max-image-preview:large" />
    <link rel="canonical" href="https://абхазберег.рф/kvartira/" />
    <meta property="og:type" content="website" />
    <meta property="og:title" content="Квартиры и дома — Абхазия 2026" />
    <meta property="og:description" content="Отдельные карточки квартир и домов в едином стиле с отелями: фото, видео и описание из Telegram." />
    <meta property="og:url" content="https://абхазберег.рф/kvartira/" />
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;700;800&family=Prata&display=swap" rel="stylesheet" />
    <link rel="stylesheet" href="../styles.css" />
  </head>
  <body>
    <div class="grain" aria-hidden="true"></div>
    <main>
      <header class="hero section">
        <p class="eyebrow"><a href="/">Абхазберег</a></p>
        <h1>КВАРТИРЫ И ДОМА</h1>
        <p class="lead">Каталог объектов из группы <a href="https://t.me/abhkvartira" target="_blank" rel="noopener noreferrer">@abhkvartira</a>. Каждая карточка открывает отдельную страницу объекта с фото, видео и описанием.</p>
      </header>

      <section class="section">
        <article class="card">
          <h2>Каталог объектов</h2>
          <div class="catalog-grid" id="kvartira-catalog-grid">{grid}</div>
        </article>
      </section>
    </main>
    <script src="../scripts.js" defer></script>
  </body>
</html>
"""


def replace_catalog_block(file_path: Path, marker: str, html_block: str) -> None:
    text = file_path.read_text(encoding="utf-8")
    start = text.index(marker) + len(marker)
    end = text.index("</div>", start)
    updated = text[:start] + html_block + text[end:]
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
            parts.append(
                f'            <img src="{html.escape(preferred_url, quote=True)}" alt="{html.escape(title)} фото {image_index}" loading="lazy" />'
            )
            image_index += 1
            continue

        if mime.startswith("video/") and preferred_url:
            parts.append(
                f"""            <video class="local-video" controls preload="metadata" playsinline>
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
    details = row.get("details") or {}
    page_path = details.get("page_path")
    if not page_path:
      return
    path = Path(page_path)
    if not path.exists():
        return

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
        text = replace_once(text, r'<meta property="og:image" content=".*?" ?/?>', f'<meta property="og:image" content="{html.escape(cover, quote=True)}" />')
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

    path.write_text(text, encoding="utf-8")


def rebuild_kvartira_pages(rows: list[dict[str, Any]]) -> None:
    from sync_catalog_from_telegram import render_detail_page  # noqa: PLC0415

    for row in rows:
        details = row.get("details") or {}
        page_url = row.get("page_url") or f"https://абхазберег.рф/kvartira/{row['slug']}/"
        page_path = details.get("page_path")
        if page_path:
            path = Path(page_path)
        else:
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
                media_items.append({"kind": "photo", "source_url": preferred_url})
                continue
            if mime.startswith("video/") and preferred_url:
                media_items.append({"kind": "video", "source_url": preferred_url})
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
        path.write_text(html_page, encoding="utf-8")


def rebuild_sitemap(rows: list[dict[str, Any]]) -> None:
    urlset = ET.Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
    urls = ["https://абхазберег.рф/", "https://абхазберег.рф/kvartira/"]
    urls.extend(row["page_url"] for row in rows if row.get("page_url") and row.get("source_kind") in {"hotel", "kvartira"})
    for url in urls:
        node = ET.SubElement(urlset, "url")
        loc = ET.SubElement(node, "loc")
        loc.text = url
    tree = ET.ElementTree(urlset)
    tree.write(SITEMAP_PATH, encoding="utf-8", xml_declaration=True)


def main() -> None:
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
    rows = response.json()

    hotel_rows = [row for row in rows if row.get("source_kind") == "hotel"]
    kvartira_rows = [row for row in rows if row.get("source_kind") == "kvartira"]
    KVARTIRA_DIR.mkdir(parents=True, exist_ok=True)

    # Normalize filters in DB
    session = requests.Session()
    session.headers.update(headers)

    def patch_listing(listing_id: int, details: dict[str, Any]) -> None:
        last_error: Exception | None = None
        for attempt in range(5):
            try:
                patch = session.patch(
                    f"{base}/rest/v1/listings",
                    params={"id": f"eq.{listing_id}"},
                    headers={**headers, "Content-Type": "application/json", "Prefer": "return=minimal"},
                    json={"details": details},
                    timeout=60,
                )
                patch.raise_for_status()
                return
            except Exception as error:  # noqa: BLE001
                last_error = error
                time.sleep(1 + attempt)
        if last_error:
            raise last_error

    updated = 0
    hotel_post_meta = load_hotel_card_meta()
    for row in rows:
        filters = infer_filters(row)
        details = dict(row.get("details") or {})
        if details.get("filters") == filters:
            continue
        details["filters"] = filters
        patch_listing(row["id"], details)
        row["details"] = details
        updated += 1

    replace_catalog_block(
        INDEX_PATH,
        '<div class="catalog-grid" id="catalog-grid">',
        "".join(render_hotel_card(row, hotel_post_meta) for row in hotel_rows),
    )
    KVARTIRA_PATH.write_text(render_kvartira_catalog_page(kvartira_rows), encoding="utf-8")

    for row in hotel_rows:
        update_hotel_page(row)
    rebuild_kvartira_pages(kvartira_rows)

    rebuild_sitemap(rows)

    print(f"Нормализовано фильтров: {updated}")
    print(f"Пересобрано отелей: {len(hotel_rows)}")
    print(f"Пересобрано квартир: {len(kvartira_rows)}")


if __name__ == "__main__":
    main()
