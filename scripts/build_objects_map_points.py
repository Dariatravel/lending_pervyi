#!/usr/bin/env python3
"""Собирает точки карты из Yandex Map Constructor + сопоставляет со страницами сайта."""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "data" / "objects-map-points.json"
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
]

SKIP_TITLE_HINTS = (
    "аэропорт",
    "жд вокзал",
    "аквапарк",
    "дельфинарий",
    "пляж",
    "набереж",
    "канат",
    "музей",
    "храм",
    "крепост",
    "водопад",
    "озеро",
    "парк ",
    "смотров",
)


def norm_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", value or "")
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


def page_records() -> list[dict]:
    records: list[dict] = []
    for pattern in ("hotels/*/index.html", "kvartira/*/index.html"):
        for path in sorted(ROOT.glob(pattern)):
            html = path.read_text(encoding="utf-8", errors="ignore")
            canonical = re.search(r'rel="canonical"\s+href="([^"]+)"', html) or re.search(
                r'href="([^"]+)"\s+rel="canonical"', html
            )
            page_url = canonical.group(1) if canonical else ""
            parsed = urlparse(page_url)
            url_path = parsed.path or f"/{path.parent.as_posix().split('/', 1)[-1]}/"
            if not url_path.endswith("/"):
                url_path += "/"

            title_match = re.search(r"<h2[^>]*>(.*?)</h2>", html, re.S | re.I)
            title = re.sub(r"<[^>]+>", " ", title_match.group(1) if title_match else "")
            title = re.sub(r"\s+", " ", title).strip()

            loc_match = re.search(r'class="location"[^>]*>(.*?)</p>', html, re.S | re.I)
            loc_text = re.sub(r"<[^>]+>", " ", loc_match.group(1) if loc_match else "")
            loc_text = re.sub(r"\s+", " ", loc_text).strip()

            records.append(
                {
                    "slug": path.parent.name,
                    "title": title,
                    "title_norm": norm_text(title),
                    "location": loc_text,
                    "city_key": infer_city_key(loc_text),
                    "url": url_path,
                }
            )
    return records


def quoted_core(title: str) -> str:
    match = re.search(r"[«\"']([^«\"']+)[»\"']", title)
    return norm_text(match.group(1)) if match else ""


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

    ratio = SequenceMatcher(None, pt, pn).ratio()
    if ratio >= 0.72:
        return ratio
    return 0.0


def should_skip_unmatched(placemark: dict) -> bool:
    blob = norm_text(f"{placemark['title']} {placemark['address']}")
    if any(hint in blob for hint in SKIP_TITLE_HINTS):
        return True
    if not placemark["address"] and len(norm_text(placemark["title"])) < 8:
        return True
    return False


def looks_like_address(text: str) -> bool:
    blob = norm_text(text)
    if not blob:
        return False
    if any(token in blob for token in ("ул", "улиц", "шоссе", "район", "пос", "село", "гагра", "сухум", "лдзаа", "пицунд", "гудаут", "афон")):
        return True
    return "," in text or re.search(r"\d", text) is not None


def build_points() -> dict:
    html = fetch_constructor_html()
    placemarks = parse_constructor_placemarks(html)
    pages = page_records()
    used_placemark_indexes: set[int] = set()
    points: list[dict] = []
    unmatched_pages = 0

    for page in pages:
        best_index = None
        best_score = 0.0
        for index, placemark in enumerate(placemarks):
            if index in used_placemark_indexes:
                continue
            score = match_score(placemark, page)
            if score > best_score:
                best_score = score
                best_index = index

        if best_index is None or best_score < 0.68:
            unmatched_pages += 1
            continue

        placemark = placemarks[best_index]
        used_placemark_indexes.add(best_index)

        address = placemark["address"] if looks_like_address(placemark["address"]) else page["location"]
        address = address.split("\n", 1)[0].strip() or page["title"]
        city_key = infer_city_key(f"{address} {placemark['title']} {page['location']}") or page["city_key"]

        points.append(
            {
                "title": page["title"],
                "address": address,
                "lat": placemark["lat"],
                "lon": placemark["lon"],
                "url": page["url"],
                "cityKey": city_key,
            }
        )

    points.sort(key=lambda item: (item.get("cityKey") or "", item["title"]))
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "constructor_id": CONSTRUCTOR_ID,
        "points": points,
        "stats": {
            "placemarks_total": len(placemarks),
            "matched": len(points),
            "unmatched_pages": unmatched_pages,
            "pages_total": len(pages),
        },
    }


def main() -> int:
    payload = build_points()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    stats = payload["stats"]
    print(
        f"OK: {stats['matched']} точек -> {OUTPUT_PATH.relative_to(ROOT)} "
        f"(из {stats['placemarks_total']} меток конструктора, страниц {stats['pages_total']}, "
        f"без пары {stats['unmatched_pages']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
