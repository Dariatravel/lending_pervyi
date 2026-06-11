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
        r"\s+(?:\d+\s*)?(?:минут(?:ы|у|а)?|мин\.|пешком|до пляжа|размещение|вместимость)\b",
        text,
        maxsplit=1,
        flags=re.I,
    )[0].strip(" ,.")
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


def extract_brand(title: str) -> str:
    core = quoted_core(title)
    if core:
        return core
    text = norm_text(title)
    for word in TITLE_TYPE_WORDS:
        text = text.replace(word, " ")
    return re.sub(r"\s+", " ", text).strip()


def match_score(placemark: dict, page: dict) -> float:
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
        return 0.92

    brand_p = extract_brand(placemark["title"])
    brand_n = extract_brand(page["title"])
    if brand_p and brand_n and len(brand_p) >= 3:
        if brand_p == brand_n:
            return 0.96
        if brand_p in brand_n or brand_n in brand_p:
            return 0.90

    pa = norm_text(extract_address_line(placemark.get("address", "")))
    pl = norm_text(page.get("address_line", ""))
    if pa and pl and len(pa) > 6 and len(pl) > 6:
        if pa == pl:
            return 0.88
        if pa in pl or pl in pa:
            return 0.85
        common = set(pa.split()) & set(pl.split())
        if len(common) >= 3:
            return 0.75 + 0.03 * min(len(common), 5)

    ratio = SequenceMatcher(None, pt, pn).ratio()
    if ratio >= 0.72:
        return ratio
    return 0.0


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


def make_point(page: dict, lat: float, lon: float, address: str, source: str) -> dict:
    city_key = infer_city_key(f"{address} {page['location']}") or page["city_key"]
    return {
        "title": page["title"],
        "address": address,
        "lat": lat,
        "lon": lon,
        "url": page["url"],
        "cityKey": city_key,
        "source": source,
    }


def match_pages_to_placemarks(pages: list[dict], placemarks: list[dict]) -> dict[str, dict]:
    pairs: list[tuple[float, int, int]] = []
    for page_index, page in enumerate(pages):
        for placemark_index, placemark in enumerate(placemarks):
            score = match_score(placemark, page)
            if score >= 0.68:
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
    matches = match_pages_to_placemarks(pages, placemarks)

    points_by_slug: dict[str, dict] = {}
    stats = {
        "placemarks_total": len(placemarks),
        "pages_total": len(pages),
        "from_constructor": 0,
        "from_coords_in_text": 0,
        "from_duplicate_title": 0,
        "from_geocode": 0,
        "from_city_fallback": 0,
    }

    for slug, match in matches.items():
        page = match["page"]
        placemark = match["placemark"]
        address = resolve_address(page, placemark)
        points_by_slug[slug] = make_point(page, placemark["lat"], placemark["lon"], address, "constructor")
        stats["from_constructor"] += 1

    unmatched = [page for page in pages if page["slug"] not in points_by_slug]

    for page in unmatched:
        coords = extract_coords_from_location(page["location"])
        if coords:
            lat, lon = coords
            address = resolve_address(page)
            points_by_slug[page["slug"]] = make_point(page, lat, lon, address, "coords_in_text")
            stats["from_coords_in_text"] += 1

    unmatched = [page for page in pages if page["slug"] not in points_by_slug]
    coords_by_title: dict[str, tuple[float, float]] = {}
    for point in points_by_slug.values():
        title_norm = norm_text(point["title"])
        if title_norm and title_norm not in coords_by_title:
            coords_by_title[title_norm] = (point["lat"], point["lon"])

    for page in unmatched:
        coords = coords_by_title.get(page["title_norm"])
        if not coords:
            continue
        address = resolve_address(page)
        points_by_slug[page["slug"]] = make_point(page, coords[0], coords[1], address, "duplicate_title")
        stats["from_duplicate_title"] += 1

    unmatched = [page for page in pages if page["slug"] not in points_by_slug]
    api_key = load_maps_api_key()
    geocode_cache = load_geocode_cache()
    cache_dirty = False

    if unmatched and api_key:
        for page in unmatched[:]:
            address = resolve_address(page)
            cache_key = norm_text(address)
            cached = geocode_cache.get(cache_key)
            if cached and "lat" in cached and "lon" in cached:
                points_by_slug[page["slug"]] = make_point(
                    page, float(cached["lat"]), float(cached["lon"]), address, "geocode"
                )
                stats["from_geocode"] += 1
                unmatched.remove(page)
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
            unmatched.remove(page)

    if cache_dirty:
        save_geocode_cache(geocode_cache)

    for page in unmatched:
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
        f"дубликаты названия {stats['from_duplicate_title']}, "
        f"геокодер {stats['from_geocode']}, город {stats['from_city_fallback']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
