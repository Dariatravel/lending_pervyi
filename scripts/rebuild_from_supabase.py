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

PODBORKI_ROOT = Path("/Users/darya_botova/Documents/ПОДБОРКИ")
_PODBORKI_TITLE_FILTERS_CACHE: dict[str, dict[str, set[str]]] | None = None
_PODBORKI_FILTER_BY_FOLDER_SLUG: dict[str, tuple[str, str]] = {
    "bereg-morya-oteli-na-beregu": ("distance", "beachfront"),
    "varianty-do-5-tr-ekonom": ("price", "economy"),
    "varianty-5-12-tr-srednyak": ("price", "midrange"),
    "varianty-dorozhe-12-tr-premium": ("price", "premium"),
    "alahadzy-vse-varianty": ("city", "alakhadzy"),
    "gagra-vse-varianty": ("city", "gagra"),
    "gudauta-vse-varianty": ("city", "gudauta"),
    "ldzaa-vse-varianty": ("city", "ldzaa"),
    "novyy-afon-vse-varianty": ("city", "new-afon"),
    "pitsunda-vse-varianty": ("city", "pitsunda"),
    "suhum-vse-varianty": ("city", "sukhum"),
    "peschanyy-ldzaa": ("beach", "sand"),
    "peschanyy-plyazh-suhum": ("beach", "sand"),
    "sosnovyy-plyazh": ("beach", "pine-pebble"),
    "vid-na-more-pryamoy-bokovoy": ("room", "sea-view"),
    "basseyn-vse-varianty": ("room", "pool"),
    "balkony": ("room", "balcony"),
    "veranda": ("room", "terrace"),
    "svoya-kuhnya-v-nomere": ("room", "kitchen"),
    "pyatero-gostey-i-bolee": ("room", "five-plus"),
    "dvuhkomnatnye-i-bolee": ("room", "two-room"),
    "domiki-vse-varianty": ("stay", "cottages"),
    "kvartiry-vse-varianty": ("stay", "apartments"),
    "doma-pod-klyuch-vse-varianty": ("stay", "turnkey-house"),
    "sobaki-varianty": ("stay", "pets"),
    "pitanie-v-otele-ili-svoe-kafe": ("food", "cafe"),
}
_PODBORKI_SOURCE_SLUG_ALIASES: dict[str, str] = {
    "peschanyy-plyazh-ldzaa": "peschanyy-ldzaa",
    "sosnovyy-plyazh-ldzaa-i-pitsunda": "sosnovyy-plyazh",
    "vid-na-more": "vid-na-more-pryamoy-bokovoy",
    "pitanie-i-svoe-kafe": "pitanie-v-otele-ili-svoe-kafe",
}


def _slugify_folder_name(text: str) -> str:
    s = unicodedata.normalize("NFKC", text or "").lower().replace("ё", "е")
    s = re.sub(r"[^a-z0-9а-я]+", "-", s)
    # грубая транслитерация достаточно для известных папок
    tr = str.maketrans(
        {
            "а": "a",
            "б": "b",
            "в": "v",
            "г": "g",
            "д": "d",
            "е": "e",
            "ж": "zh",
            "з": "z",
            "и": "i",
            "й": "y",
            "к": "k",
            "л": "l",
            "м": "m",
            "н": "n",
            "о": "o",
            "п": "p",
            "р": "r",
            "с": "s",
            "т": "t",
            "у": "u",
            "ф": "f",
            "х": "h",
            "ц": "ts",
            "ч": "ch",
            "ш": "sh",
            "щ": "sch",
            "ъ": "",
            "ы": "y",
            "ь": "",
            "э": "e",
            "ю": "yu",
            "я": "ya",
        }
    )
    s = s.translate(tr)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s


def _norm_title(text: str) -> str:
    t = (text or "").strip().lower()
    t = t.replace("«", '"').replace("»", '"').replace("“", '"').replace("”", '"')
    t = t.replace("ё", "е")
    t = re.sub(r"\s+", " ", t)
    return t


def load_podborki_title_filters() -> dict[str, dict[str, set[str]]]:
    global _PODBORKI_TITLE_FILTERS_CACHE
    if _PODBORKI_TITLE_FILTERS_CACHE is not None:
        return _PODBORKI_TITLE_FILTERS_CACHE

    out: dict[str, dict[str, set[str]]] = {}
    if not PODBORKI_ROOT.is_dir():
        _PODBORKI_TITLE_FILTERS_CACHE = out
        return out

    for txt in sorted(PODBORKI_ROOT.glob("*/подборка_*.txt")):
        name = txt.name
        if "_сайт" in name or "_макс_канал" in name or "_вк_пост" in name:
            continue
        src_slug = _slugify_folder_name(txt.parent.name)
        slug = _PODBORKI_SOURCE_SLUG_ALIASES.get(src_slug, src_slug)
        mapping = _PODBORKI_FILTER_BY_FOLDER_SLUG.get(slug)
        if not mapping:
            continue
        group, value = mapping
        try:
            rows = txt.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in rows:
            s = line.strip()
            if not s:
                continue
            if not (s.startswith('"') or s.startswith("«") or s.startswith("“")):
                continue
            title_key = _norm_title(s)
            by_group = out.setdefault(title_key, {})
            by_group.setdefault(group, set()).add(value)

    _PODBORKI_TITLE_FILTERS_CACHE = out
    return out

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


def get_text_from_page(page_path: str) -> str:
    path = Path(page_path)
    if not path.is_file():
        alt = Path(page_path.replace("/New project/", "/GitHub/lending_pervyi/"))
        if alt.is_file():
            path = alt
        else:
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
    beachfront_markers = (
        "на первой линии",
        "прямо на пляже",
        "выход из отеля сразу на пляж",
        "выход к морю сразу",
        "до моря 0 минут",
        "до моря 0 мин",
        "0 минут до пляжа",
        "0 мин до пляжа",
        "вышел за калитку и вот оно",
        "в одном шаге",
        "100 шагов до",
    )
    if any(marker in blob for marker in beachfront_markers):
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
    prices = [int(match) for match in re.findall(r"(?<!\d)(\d{3,5})(?!\d)", blob)]
    if not prices:
        return []
    value = max(prices)
    if value < 5000:
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


def detect_beach(blob: str) -> list[str]:
    values: list[str] = []
    if any(marker in blob for marker in ("соснов", "сосновый пляж")):
        values.append("pine-pebble")
    if "песчан" in blob and "галеч" in blob:
        values.append("mixed")
    elif "песчан" in blob or "песок" in blob:
        values.append("sand")
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
    if "террас" in blob or "веранд" in blob:
        values.append("terrace")
    if "бассейн" in blob:
        values.append("pool")
    if any(marker in blob for marker in ("однокомнат", "1к", "1-к", "студия")):
        values.append("one-room")
    if any(marker in blob for marker in ("двухкомнат", "2к", "2-к", "трехкомнат", "3к", "3-к", "четырехкомнат", "4к", "4-к")):
        values.append("two-room")
    if re.search(r"до\s*(?:[5-9]|1[0-2])\s*чел", blob):
        values.append("five-plus")
    if "кухн" in blob:
        values.append("kitchen")
    if "кондиционер" in blob:
        values.append("ac")
    return sorted(set(values), key=values.index)


def detect_stay(blob: str) -> list[str]:
    values: list[str] = []
    if any(marker in blob for marker in ("домик", "домики", "коттедж", "коттеджи")):
        values.append("cottages")
    if any(marker in blob for marker in ("квартир", "апартамент", "студия")):
        values.append("apartments")
    if "дом под ключ" in blob:
        values.append("turnkey-house")
    if any(marker in blob for marker in ("с детьми", "для детей", "детская площадка", "семейн")):
        values.append("kids")
    if any(marker in blob for marker in ("с животными", "с питомц", "с собачк", "pet friendly")):
        values.append("pets")
    if any(marker in blob for marker in ("без детей", "без маленьких детей")):
        values.append("no-small-kids")
    return values


def infer_filters(row: dict[str, Any]) -> dict[str, list[str]]:
    blob = text_blob(row)
    filters = {
        "distance": detect_distance(blob),
        "food": detect_food(blob),
        "price": detect_price(blob),
        "city": detect_city(blob),
        "beach": detect_beach(blob),
        "room": detect_room(blob),
        "stay": detect_stay(blob),
    }
    title_key = _norm_title(str(row.get("title") or ""))
    if title_key:
        by_group = load_podborki_title_filters().get(title_key, {})
        for group, values in by_group.items():
            current = list(filters.get(group) or [])
            for v in values:
                if v not in current:
                    current.append(v)
            filters[group] = current
    return filters


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
    label_attr = html.escape(f"Показать на карте объектов: {label}", quote=True)
    label_text = html.escape(label)
    return (
        f'<span class="catalog-card__map-plaque catalog-card__map-plaque--{city_attr}" '
        f'data-map-city="{city_attr}" role="link" tabindex="0" aria-label="{label_attr}">'
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
    title = html.escape(row.get("title") or "")
    summary_fallback = row.get("summary") or row.get("excerpt") or ""
    card_lines: list[str] = []
    location_text = str(row.get("location_text") or "").strip()
    beach_text = str(row.get("beach_text") or "").strip()
    if location_text:
        card_lines.append(location_text if location_text.startswith("📍") else f"📍{location_text}")
    if beach_text:
        card_lines.append(beach_text if beach_text.startswith("🏖") else f"🏖 {beach_text}")
    if not card_lines:
        source_message_id = resolve_source_message_id(row)
        if source_message_id is not None:
            meta = post_meta.get(source_message_id) or {}
            if meta.get("location_line"):
                card_lines.append(meta["location_line"])
            if meta.get("beach_line"):
                card_lines.append(meta["beach_line"])

    if card_lines:
        summary_html = "<br />".join(html.escape(line) for line in card_lines)
    else:
        summary_html = html.escape(summary_fallback)
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
    filters = (row.get("details") or {}).get("filters") or {}
    attrs = " ".join(
        f'data-filter-{group}="{html.escape("|".join(filters.get(group) or []), quote=True)}"'
        for group in FILTER_GROUPS
    )
    href = page_path_from_url(row.get("page_url"), row.get("telegram_url") or "/kvartira/")
    title = html.escape(row.get("title") or "")
    summary = html.escape(row.get("summary") or row.get("excerpt") or ((row.get("details") or {}).get("excerpt") or ""))
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
        f"<p>{summary}</p>"
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
              <span class="contact-messengers">(Ватсап, Телеграм, Макс, ВК-чат)</span>
            </p>
            <p class="note">Только сообщения, обычный звонок не пройдёт.</p>
            <p class="note">Прежде чем написать в МАКС, добавьте номер в контакты (иначе макс не даст ответить на входящее сообщение). Обращайтесь!</p>
          </div>
          <div class="contact-buttons">
            <a class="btn-book" href="https://max.ru/abhazbereg" rel="noopener noreferrer" target="_blank">НАПИСАТЬ В МАКС</a>
            <a class="btn-book" href="http://vk.cc/cQQnBn" rel="noopener noreferrer" target="_blank">НАПИСАТЬ В ВК-ЧАТ</a>
            <a class="btn-book" href="https://t.me/abhazbooking_online" rel="noopener noreferrer" target="_blank">НАПИСАТЬ В ТЕЛЕГРАМ</a>
            <a class="btn-book" href="https://wa.me/79409003340" rel="noopener noreferrer" target="_blank">НАПИСАТЬ В ВАТСАП</a>
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
        r'<div class="catalog-grid" id="catalog-grid">'
        r'[\s\S]*?'
        r'</div>\s*(?:<div class="catalog-grid" id="catalog-grid">[\s\S]*?</div>\s*)?'
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
                f"""            <video class="local-video" controls preload="metadata" playsinline{poster_attr}>
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
        text = replace_once(text, r'<meta property="og:image" content="https://storage.yandexcloud.net/abhazbereg-media/media/branding/site-cover.jpg" ?/?>', f'<meta property="og:image" content="https://storage.yandexcloud.net/abhazbereg-media/media/branding/site-cover.jpg" />')
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
                media_items.append({"kind": "video", "source_url": media_src_for_html(preferred_url, mime_type=mime)})
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


def rebuild_catalog(rows: list[dict[str, Any]]) -> None:
    rows = normalize_catalog_rows(rows)
    rows = [row for row in rows if row.get("is_active", True)]
    hotel_rows = [row for row in rows if row.get("source_kind") == "hotel"]
    kvartira_excluded = {"general-1409"}
    kvartira_rows = [
        row
        for row in rows
        if row.get("source_kind") == "kvartira" and row.get("slug") not in kvartira_excluded
    ]
    KVARTIRA_DIR.mkdir(parents=True, exist_ok=True)

    hotel_post_meta = load_hotel_card_meta()
    catalog_cards_html = "".join(render_hotel_card(row, hotel_post_meta) for row in hotel_rows) + "".join(
        render_kvartira_card(row) for row in kvartira_rows
    )
    replace_catalog_block(
        INDEX_PATH,
        '<div class="catalog-grid" id="catalog-grid">',
        catalog_cards_html,
    )
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
