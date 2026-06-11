#!/usr/bin/env python3
"""Собирает точки карты из Yandex Map Constructor + сопоставляет со страницами сайта."""

from __future__ import annotations

import hashlib
import html
import json
import re
import time
import unicodedata
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "data" / "objects-map-points.json"
GEOCODE_CACHE_PATH = ROOT / "data" / "objects-map-geocode-cache.json"
MAPS_CONFIG_PATH = ROOT / "supabase" / "maps-config.js"
CONSTRUCTOR_ID = "80408220233bb515383a3bc3da359eb235d60e8dd3dddfe843612590179aabd1"
WIDGET_URL = (
    "https://yandex.ru/map-widget/v1/?um=constructor%3A"
    + CONSTRUCTOR_ID
    + "&ll=40.5%2C43.15&z=9"
)

CITY_TEXT_TO_KEY = [
    ("новый афон", "new-afon"),
    ("цандрипш", "tsandripsh"),
    ("алахадз", "alakhadzy"),
    ("гагрск", "gagra"),
    ("гагра", "gagra"),
    ("пицунд", "pitsunda"),
    ("гудаут", "gudauta"),
    ("лдзаа", "ldzaa"),
    ("сухум", "sukhum"),
    ("сухуми", "sukhum"),
    ("гулрыпш", "gagra"),
    ("хыпст", "gagra"),
    ("псырцх", "new-afon"),
    ("цитрусов", "alakhadzy"),
    ("рицинск", "gudauta"),
    ("амзара", "tsandripsh"),
    ("мачара", "sukhum"),
    ("багрипш", "gagra"),
]

CITY_CENTROIDS = {
    "ldzaa": {"lat": 43.05, "lon": 40.32},
    "pitsunda": {"lat": 43.16, "lon": 40.34},
    "gagra": {"lat": 43.28, "lon": 40.27},
    "alakhadzy": {"lat": 43.22, "lon": 40.29},
    "gudauta": {"lat": 43.10, "lon": 40.62},
    "new-afon": {"lat": 43.09, "lon": 40.82},
    "sukhum": {"lat": 43.00, "lon": 41.02},
    "tsandripsh": {"lat": 43.38, "lon": 40.34},
    "": {"lat": 43.15, "lon": 40.50},
}

TITLE_TYPE_WORDS = (
    "отель",
    "гостевой дом",
    "гостевой комплекс",
    "гостиница",
    "домики",
    "квартира",
    "апартаменты",
    "апарт отель",
    "мини отель",
    "мини-отель",
    "база отдыха",
    "комплекс",
    "студия",
    "коттедж",
    "глэмпинг",
    "номера",
    "апартамент",
    "дом под ключ",
    "жилье под ключ",
    "эко-комплекс",
    "эко комплекс",
    "резорт",
    "студио",
    "studio",
    "люкс",
    "lux",
    "новый",
    "new",
    "эко",
    "eco",
    "видовой",
    "видовые",
    "номер",
    "номера",
    "апартамент",
)

GENERIC_ADDRESS_TOKENS = frozenset(
    {
        "абхазия",
        "абхазии",
        "алахадзе",
        "алахадзы",
        "амзара",
        "афон",
        "багрипш",
        "бывшая",
        "гагра",
        "гагрский",
        "гудаута",
        "гудаутский",
        "д",
        "дом",
        "квартира",
        "лдзаа",
        "марухская",
        "новый",
        "пос",
        "поселок",
        "посёлок",
        "пицунда",
        "птицефабрика",
        "район",
        "республика",
        "село",
        "сухум",
        "сухуми",
        "ул",
        "улица",
        "улице",
        "шоссе",
        "пр",
        "проспект",
        "пр-т",
        "переулок",
        "пер",
        "км",
        "этаж",
        "напротив",
        "мин",
        "минут",
        "минуту",
        "минуты",
        "пляж",
        "пляжа",
        "размещение",
        "человек",
        "чел",
        "вместимость",
        "галечный",
        "песчаный",
        "песок",
        "галька",
        "сосновый",
        "пешком",
        "авто",
        "брони",
        "пишите",
        "what",
        "telegram",
    }
)

CYR_TO_LAT = str.maketrans(
    {
        "а": "a",
        "б": "b",
        "в": "v",
        "г": "g",
        "д": "d",
        "е": "e",
        "ё": "e",
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

BRAND_ALIASES = {
    "kastl": "castle",
    "kastel": "castle",
    "castle": "castle",
    "grant": "grant",
    "grants": "grant",
    "seaside": "seaside",
    "sisayd": "seaside",
    "siside": "seaside",
    "sunamra": "sunamra",
    "sanamra": "sunamra",
    "studiosanamra": "sunamra",
    "soluna": "soluna",
    "heppilend": "happiland",
    "happyland": "happiland",
    "heppilenddomiki": "happiland",
    "mimi": "mimi",
    "colibri": "colibri",
    "kolibri": "colibri",
    "sitigagra": "citygagra",
    "citygagra": "citygagra",
    "greyhaus": "greyhouse",
    "greyhouse": "greyhouse",
    "fyuzhn": "fusion",
    "fusion": "fusion",
    "biheppi": "behappy",
    "behappy": "behappy",
    "avrorainn": "aurorainn",
    "aurorainn": "aurorainn",
    "aurora": "aurorainn",
    "aurorainngagra": "aurorainn",
    "sialend": "sealand",
    "sealand": "sealand",
    "sealandcottage": "sealand",
    "whitehorse": "whitehorse",
    "belayaloshad": "whitehorse",
    "demimokko": "demimokko",
    "peschanyybereg": "peschanyybereg",
    "sunpino": "sunpino",
    "sanpino": "sunpino",
    "lnd": "lnd",
    "lnnd": "lnd",
    "ekohoum": "ecohome",
    "ekohome": "ecohome",
    "grafithaus": "grafithouse",
    "grafithouse": "grafithouse",
    "ecohousepitiunt": "ecohousepitiunt",
    "ekohauspitiunt": "ecohousepitiunt",
    "housepitiunt": "ecohousepitiunt",
    "greenhouse": "greenhouse",
    "grinhaus": "greenhouse",
    "atthesea": "atthesea",
    "thesea": "atthesea",
    "umorya": "atthesea",
    "belochka": "belochka",
    "ubelochki": "belochka",
    "vgostyahubelochki": "belochka",
    "sinophouses": "sinophouses",
    "sinophaus": "sinophouses",
    "moreon": "moreon",
    "moryeon": "moreon",
}

CITY_LATIN_SUFFIXES = (
    "gagra",
    "sukhum",
    "ldzaa",
    "pitsunda",
    "gudauta",
    "newafon",
    "tsandripsh",
    "alakhadzy",
    "abhazia",
)


def norm_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", value or "")
    text = html.unescape(text)
    text = text.replace("«", "").replace("»", "").replace('"', "").replace("'", "")
    text = re.sub(r"[^\w\sа-яёa-z0-9]+", " ", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


def decode_json_string(raw: str) -> str:
    try:
        return json.loads('"' + raw + '"')
    except json.JSONDecodeError:
        return raw.replace("\\n", "\n").replace('\\"', '"')


def fetch_constructor_html() -> str:
    req = Request(WIDGET_URL, headers={"User-Agent": "abhazbereg-map-builder/1.0"})
    with urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def parse_constructor_placemarks(html: str) -> list[dict]:
    pattern = re.compile(
        r'\{"title":"((?:\\.|[^"\\])*)"(?:,"subtitle":"((?:\\.|[^"\\])*)")?'
        r'[^}]*?"type":"placemark"[^}]*?"coordinates":\[([0-9.]+),([0-9.]+)\]',
        re.S,
    )
    items: list[dict] = []
    for match in pattern.finditer(html):
        title = decode_json_string(match.group(1))
        subtitle = decode_json_string(match.group(2) or "")
        lon = float(match.group(3))
        lat = float(match.group(4))
        items.append(
            {
                "title": title.strip(),
                "address": subtitle.strip(),
                "lat": lat,
                "lon": lon,
            }
        )
    return items


def infer_city_key(text: str) -> str:
    normalized = norm_text(text)
    for needle, key in CITY_TEXT_TO_KEY:
        if needle in normalized:
            return key
    return ""


def extract_address_line(location: str) -> str:
    text = html.unescape(location or "")
    text = text.split("\n", 1)[0]
    text = re.sub(r"[📍🏖👥️]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\b(\d{2}\.\d{4,})\s*,\s*(\d{2}\.\d{4,})\b", "", text).strip(" ,.")
    text = re.split(
        r"\s+(?:\d+\s*)?(?:минут(?:ы|у|а)?|мин\.|пешком|до пляжа|размещение|вместимость|пляж)\b",
        text,
        maxsplit=1,
        flags=re.I,
    )[0].strip(" ,.")
    text = re.sub(r"\s+\d+\s*$", "", text).strip(" ,.")
    text = re.sub(r"\s*\([^)]*\)\s*", " ", text).strip(" ,.")
    return text


def extract_coords_from_location(location: str) -> tuple[float, float] | None:
    match = re.search(r"(\d{2}\.\d{4,})\s*,\s*(\d{2}\.\d{4,})", location or "")
    if not match:
        return None
    lat = float(match.group(1))
    lon = float(match.group(2))
    if 42.0 <= lat <= 44.5 and 40.0 <= lon <= 42.5:
        return lat, lon
    if 40.0 <= lat <= 42.5 and 42.0 <= lon <= 44.5:
        return lon, lat
    return None


def page_records() -> list[dict]:
    records: list[dict] = []
    for pattern in ("hotels/*/index.html", "kvartira/*/index.html"):
        for path in sorted(ROOT.glob(pattern)):
            raw_html = path.read_text(encoding="utf-8", errors="ignore")
            canonical = re.search(r'rel="canonical"\s+href="([^"]+)"', raw_html) or re.search(
                r'href="([^"]+)"\s+rel="canonical"', raw_html
            )
            page_url = canonical.group(1) if canonical else ""
            parsed = urlparse(page_url)
            url_path = parsed.path or f"/{path.parent.as_posix().split('/', 1)[-1]}/"
            if not url_path.endswith("/"):
                url_path += "/"

            title_match = re.search(r"<h2[^>]*>(.*?)</h2>", raw_html, re.S | re.I)
            title = re.sub(r"<[^>]+>", " ", title_match.group(1) if title_match else "")
            title = html.unescape(re.sub(r"\s+", " ", title).strip())

            loc_match = re.search(r'class="location"[^>]*>(.*?)</p>', raw_html, re.S | re.I)
            loc_text = re.sub(r"<[^>]+>", " ", loc_match.group(1) if loc_match else "")
            loc_text = html.unescape(re.sub(r"\s+", " ", loc_text).strip())

            records.append(
                {
                    "slug": path.parent.name,
                    "title": title,
                    "title_norm": norm_text(title),
                    "location": loc_text,
                    "address_line": extract_address_line(loc_text),
                    "city_key": infer_city_key(loc_text),
                    "url": url_path,
                }
            )
    return records


def quoted_core(title: str) -> str:
    match = re.search(r"[«\"']([^«\"']+)[»\"']", html.unescape(title or ""))
    return norm_text(match.group(1)) if match else ""


def latin_key(value: str) -> str:
    return norm_text(value).translate(CYR_TO_LAT).replace(" ", "")


def canonical_brand_key(value: str) -> str:
    key = latin_key(value)
    key = BRAND_ALIASES.get(key, key)
    for city in CITY_LATIN_SUFFIXES:
        if key.endswith(city) and len(key) > len(city) + 3:
            trimmed = key[: -len(city)]
            if len(trimmed) >= 4:
                key = BRAND_ALIASES.get(trimmed, trimmed)
    return key


def brand_keys(title: str) -> set[str]:
    keys: set[str] = set()
    quoted = quoted_core(title)
    brand = extract_brand(title)
    for raw in (quoted, brand):
        if not raw:
            continue
        keys.add(canonical_brand_key(raw))
        words = raw.split()
        if len(words) >= 2:
            keys.add(canonical_brand_key("".join(words[-2:])))
    normalized = norm_text(title)
    for marker in ("san amra", "sun amra", "sea side", "black sea", "green village"):
        if marker.replace(" ", "") in normalized.replace(" ", ""):
            keys.add(canonical_brand_key(marker.replace(" ", "")))
    return {key for key in keys if len(key) >= 3}


def brands_equivalent(title_a: str, title_b: str) -> bool:
    keys_a = brand_keys(title_a)
    keys_b = brand_keys(title_b)
    if keys_a & keys_b:
        return True
    for key_a in keys_a:
        for key_b in keys_b:
            if len(key_a) >= 5 and len(key_b) >= 5 and SequenceMatcher(None, key_a, key_b).ratio() >= 0.92:
                return True
    return False


def address_signature(text: str) -> tuple[list[str], list[str]]:
    normalized = norm_text(extract_address_line(text))
    numbers = re.findall(r"\d+[a-zа-я]?", normalized)
    tokens = [token for token in normalized.split() if token not in GENERIC_ADDRESS_TOKENS and len(token) >= 3]
    return numbers, tokens


def address_match_score(addr_a: str, addr_b: str) -> float:
    nums_a, tokens_a = address_signature(addr_a)
    nums_b, tokens_b = address_signature(addr_b)
    if not tokens_a or not tokens_b:
        return 0.0

    norm_a = norm_text(extract_address_line(addr_a))
    norm_b = norm_text(extract_address_line(addr_b))
    if norm_a and norm_b and norm_a == norm_b:
        return 0.93

    common_tokens = set(tokens_a) & set(tokens_b)
    if len(common_tokens) < 2:
        return 0.0

    common_numbers = set(nums_a) & set(nums_b)
    if not common_numbers:
        return 0.0

    return 0.9 + 0.02 * min(len(common_tokens), 3)


def extract_brand(title: str) -> str:
    core = quoted_core(title)
    if core:
        return core
    text = norm_text(title)
    for word in TITLE_TYPE_WORDS:
        text = text.replace(word, " ")
    return re.sub(r"\s+", " ", text).strip()


def cities_compatible(placemark: dict, page: dict) -> bool:
    city_page = page.get("city_key") or infer_city_key(page.get("location", ""))
    city_pm = infer_city_key(f"{placemark.get('address', '')} {placemark['title']}")
    if not city_page or not city_pm:
        return True
    if city_pm == city_page:
        return True
    district_neighbors = {"ldzaa", "pitsunda", "tsandripsh", "alakhadzy"}
    if city_pm == "gagra" and city_page in district_neighbors:
        return True
    if city_page == "gagra" and city_pm in district_neighbors:
        return True
    return False


def has_distinct_brand(title: str) -> bool:
    return bool(quoted_core(title) or extract_brand(title))


def match_score(placemark: dict, page: dict) -> float:
    if brands_equivalent(placemark["title"], page["title"]):
        if cities_compatible(placemark, page):
            return 0.97
        return 0.0

    pt = norm_text(placemark["title"])
    pn = page["title_norm"]
    if not pt or not pn:
        return 0.0

    if pt == pn:
        return 1.0
    if pt in pn or pn in pt:
        return 0.95

    core_p = quoted_core(placemark["title"])
    core_n = quoted_core(page["title"])
    if core_p and core_n and (core_p == core_n or core_p in core_n or core_n in core_p):
        return 0.94

    ratio = SequenceMatcher(None, pt, pn).ratio()
    if ratio >= 0.84:
        if has_distinct_brand(placemark["title"]) and has_distinct_brand(page["title"]):
            if not brands_equivalent(placemark["title"], page["title"]):
                return 0.0
        return ratio

    if has_distinct_brand(placemark["title"]) and has_distinct_brand(page["title"]):
        return 0.0

    city_pm = infer_city_key(f"{placemark.get('address', '')} {placemark['title']}")
    city_page = page.get("city_key") or infer_city_key(page.get("location", ""))
    if city_pm and city_page and city_pm != city_page:
        return 0.0

    return address_match_score(
        placemark.get("address", ""),
        page.get("address_line", "") or page.get("location", ""),
    )


def looks_like_address(text: str) -> bool:
    blob = norm_text(text)
    if not blob:
        return False
    if any(
        token in blob
        for token in (
            "ул",
            "улиц",
            "шоссе",
            "район",
            "пос",
            "село",
            "гагра",
            "сухум",
            "лдзаа",
            "пицунд",
            "гудаут",
            "афон",
        )
    ):
        return True
    return "," in text or re.search(r"\d", text) is not None


def resolve_address(page: dict, placemark: dict | None = None) -> str:
    if placemark and looks_like_address(placemark.get("address", "")):
        address = placemark["address"]
    elif page.get("address_line"):
        address = page["address_line"]
    else:
        address = page.get("location", "")
    return address.split("\n", 1)[0].strip() or page["title"]


def clean_display_text(text: str) -> str:
    text = html.unescape(text or "")
    text = re.sub(r"<br\s*/?>", ", ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def make_point(page: dict, lat: float, lon: float, address: str, source: str) -> dict:
    city_key = infer_city_key(f"{address} {page['location']}") or page["city_key"]
    return {
        "title": clean_display_text(page["title"]),
        "address": clean_display_text(address),
        "lat": lat,
        "lon": lon,
        "url": page["url"],
        "cityKey": city_key,
        "source": source,
    }


def exact_address_key(text: str) -> str:
    numbers, tokens = address_signature(text)
    if not numbers or not tokens:
        return ""
    return "|".join(tokens) + "|" + "|".join(sorted(numbers))


def match_remaining_placemarks(
    pages: list[dict],
    placemarks: list[dict],
    matched_slugs: set[str],
    used_placemark_indexes: set[int],
) -> dict[str, dict]:
    pairs: list[tuple[float, int, int]] = []
    for page_index, page in enumerate(pages):
        if page["slug"] in matched_slugs:
            continue
        for placemark_index, placemark in enumerate(placemarks):
            if placemark_index in used_placemark_indexes:
                continue
            score = 0.0
            if brands_equivalent(placemark["title"], page["title"]):
                if cities_compatible(placemark, page):
                    score = 0.97
            else:
                page_key = exact_address_key(page.get("address_line", "") or page.get("location", ""))
                placemark_key = exact_address_key(placemark.get("address", ""))
                if page_key and page_key == placemark_key:
                    score = 0.95
            if score >= 0.95:
                pairs.append((score, page_index, placemark_index))
    pairs.sort(reverse=True)

    matches: dict[str, dict] = {}
    used_pages: set[int] = set()
    for score, page_index, placemark_index in pairs:
        if page_index in used_pages or placemark_index in used_placemark_indexes:
            continue
        page = pages[page_index]
        placemark = placemarks[placemark_index]
        used_pages.add(page_index)
        used_placemark_indexes.add(placemark_index)
        matches[page["slug"]] = {
            "page": page,
            "placemark": placemark,
            "score": score,
        }
    return matches


def share_coords_from_existing(
    points_by_slug: dict[str, dict],
    pages_by_slug: dict[str, dict],
    pending_pages: list[dict],
    *,
    by: str,
) -> list[dict]:
    still_pending: list[dict] = []
    lookup: dict[str, tuple[float, float]] = {}

    if by == "title":
        for slug, point in points_by_slug.items():
            page = pages_by_slug[slug]
            key = page["title_norm"]
            if key and key not in lookup:
                lookup[key] = (point["lat"], point["lon"])
    elif by == "brand":
        for slug, point in points_by_slug.items():
            page = pages_by_slug[slug]
            for key in brand_keys(page["title"]):
                if key not in lookup:
                    lookup[key] = (point["lat"], point["lon"])
    elif by == "address":
        for slug, point in points_by_slug.items():
            page = pages_by_slug[slug]
            key = exact_address_key(page.get("address_line", "") or page.get("location", ""))
            if key and key not in lookup:
                lookup[key] = (point["lat"], point["lon"])

    for page in pending_pages:
        coords = None
        if by == "title":
            coords = lookup.get(page["title_norm"])
        elif by == "brand":
            for key in brand_keys(page["title"]):
                coords = lookup.get(key)
                if coords:
                    break
        elif by == "address":
            key = exact_address_key(page.get("address_line", "") or page.get("location", ""))
            coords = lookup.get(key) if key else None

        if coords:
            address = resolve_address(page)
            points_by_slug[page["slug"]] = make_point(page, coords[0], coords[1], address, f"shared_{by}")
        else:
            still_pending.append(page)
    return still_pending


def match_pages_to_placemarks(pages: list[dict], placemarks: list[dict]) -> dict[str, dict]:
    pairs: list[tuple[float, int, int]] = []
    for page_index, page in enumerate(pages):
        for placemark_index, placemark in enumerate(placemarks):
            score = match_score(placemark, page)
            if score >= 0.84:
                pairs.append((score, page_index, placemark_index))
    pairs.sort(reverse=True)

    used_pages: set[int] = set()
    used_placemarks: set[int] = set()
    matches: dict[str, dict] = {}

    for score, page_index, placemark_index in pairs:
        if page_index in used_pages or placemark_index in used_placemarks:
            continue
        page = pages[page_index]
        placemark = placemarks[placemark_index]
        used_pages.add(page_index)
        used_placemarks.add(placemark_index)
        matches[page["slug"]] = {
            "page": page,
            "placemark": placemark,
            "score": score,
        }
    return matches


def city_fallback_coords(slug: str, city_key: str) -> tuple[float, float]:
    base = CITY_CENTROIDS.get(city_key) or CITY_CENTROIDS[""]
    digest = hashlib.md5(slug.encode("utf-8")).hexdigest()
    lat_seed = int(digest[:8], 16)
    lon_seed = int(digest[8:16], 16)
    lat = base["lat"] + ((lat_seed % 1000) / 1000 - 0.5) * 0.035
    lon = base["lon"] + ((lon_seed % 1000) / 1000 - 0.5) * 0.035
    return lat, lon


def load_maps_api_key() -> str:
    if MAPS_CONFIG_PATH.is_file():
        match = re.search(r'apiKey:\s*"([^"]+)"', MAPS_CONFIG_PATH.read_text(encoding="utf-8"))
        if match and match.group(1) and match.group(1) != "YOUR_YANDEX_MAPS_API_KEY":
            return match.group(1)
    return ""


def load_geocode_cache() -> dict[str, dict]:
    if not GEOCODE_CACHE_PATH.is_file():
        return {}
    try:
        payload = json.loads(GEOCODE_CACHE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def save_geocode_cache(cache: dict[str, dict]) -> None:
    GEOCODE_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    GEOCODE_CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def geocode_with_yandex(address: str, api_key: str) -> tuple[float, float] | None:
    query = quote(f"{address}, Абхазия")
    url = (
        "https://geocode-maps.yandex.ru/1.x/?format=json&results=1&apikey="
        + quote(api_key)
        + "&geocode="
        + query
    )
    req = Request(url, headers={"User-Agent": "abhazbereg-map-builder/1.0"})
    with urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read().decode("utf-8", errors="ignore"))
    members = (
        payload.get("response", {})
        .get("GeoObjectCollection", {})
        .get("featureMember", [])
    )
    if not members:
        return None
    pos = members[0].get("GeoObject", {}).get("Point", {}).get("pos", "")
    if not pos:
        return None
    lon_str, lat_str = pos.split()
    return float(lat_str), float(lon_str)


def build_points() -> dict:
    html = fetch_constructor_html()
    placemarks = parse_constructor_placemarks(html)
    pages = page_records()
    pages_by_slug = {page["slug"]: page for page in pages}
    matches = match_pages_to_placemarks(pages, placemarks)
    used_placemark_indexes = set()
    for match in matches.values():
        for index, placemark in enumerate(placemarks):
            if placemark is match["placemark"]:
                used_placemark_indexes.add(index)
                break

    remaining = match_remaining_placemarks(pages, placemarks, set(matches.keys()), used_placemark_indexes)
    matches.update(remaining)

    points_by_slug: dict[str, dict] = {}
    stats = {
        "placemarks_total": len(placemarks),
        "pages_total": len(pages),
        "from_constructor": 0,
        "from_coords_in_text": 0,
        "from_shared_title": 0,
        "from_shared_brand": 0,
        "from_shared_address": 0,
        "from_geocode": 0,
        "from_city_fallback": 0,
    }

    for slug, match in matches.items():
        page = match["page"]
        placemark = match["placemark"]
        address = resolve_address(page, placemark)
        points_by_slug[slug] = make_point(page, placemark["lat"], placemark["lon"], address, "constructor")
        stats["from_constructor"] += 1

    pending = [page for page in pages if page["slug"] not in points_by_slug]

    for page in pending[:]:
        coords = extract_coords_from_location(page["location"])
        if coords:
            lat, lon = coords
            address = resolve_address(page)
            points_by_slug[page["slug"]] = make_point(page, lat, lon, address, "coords_in_text")
            stats["from_coords_in_text"] += 1

    pending = [page for page in pages if page["slug"] not in points_by_slug]
    before = len(pending)
    pending = share_coords_from_existing(points_by_slug, pages_by_slug, pending, by="title")
    stats["from_shared_title"] += before - len(pending)

    before = len(pending)
    pending = share_coords_from_existing(points_by_slug, pages_by_slug, pending, by="brand")
    stats["from_shared_brand"] += before - len(pending)

    before = len(pending)
    pending = share_coords_from_existing(points_by_slug, pages_by_slug, pending, by="address")
    stats["from_shared_address"] += before - len(pending)

    api_key = load_maps_api_key()
    geocode_cache = load_geocode_cache()
    cache_dirty = False

    if pending and api_key:
        for page in pending[:]:
            address = resolve_address(page)
            cache_key = norm_text(address)
            cached = geocode_cache.get(cache_key)
            if cached and "lat" in cached and "lon" in cached:
                points_by_slug[page["slug"]] = make_point(
                    page, float(cached["lat"]), float(cached["lon"]), address, "geocode"
                )
                stats["from_geocode"] += 1
                pending.remove(page)
                continue
            try:
                coords = geocode_with_yandex(address, api_key)
            except OSError:
                coords = None
            time.sleep(0.25)
            if not coords:
                continue
            lat, lon = coords
            geocode_cache[cache_key] = {"lat": lat, "lon": lon, "address": address}
            cache_dirty = True
            points_by_slug[page["slug"]] = make_point(page, lat, lon, address, "geocode")
            stats["from_geocode"] += 1
            pending.remove(page)

    if cache_dirty:
        save_geocode_cache(geocode_cache)

    for page in pending:
        lat, lon = city_fallback_coords(page["slug"], page["city_key"])
        address = resolve_address(page)
        points_by_slug[page["slug"]] = make_point(page, lat, lon, address, "city_fallback")
        stats["from_city_fallback"] += 1

    points = list(points_by_slug.values())
    for point in points:
        point.pop("source", None)
    points.sort(key=lambda item: (item.get("cityKey") or "", item["title"]))

    stats["points_total"] = len(points)
    stats["unmatched_pages"] = stats["pages_total"] - stats["points_total"]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "constructor_id": CONSTRUCTOR_ID,
        "points": points,
        "stats": stats,
    }


def main() -> int:
    payload = build_points()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    stats = payload["stats"]
    print(
        f"OK: {stats['points_total']} точек -> {OUTPUT_PATH.relative_to(ROOT)} "
        f"(страниц {stats['pages_total']}; конструктор {stats['from_constructor']}, "
        f"координаты в тексте {stats['from_coords_in_text']}, "
        f"общий бренд {stats['from_shared_brand']}, общий адрес {stats['from_shared_address']}, "
        f"общее название {stats['from_shared_title']}, "
        f"геокодер {stats['from_geocode']}, город {stats['from_city_fallback']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
