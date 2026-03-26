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
KVARTIRA_PATH = ROOT / "kvartira" / "index.html"
SITEMAP_PATH = ROOT / "sitemap.xml"


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
    if "балкон" in blob:
        values.append("balcony")
    if "бассейн" in blob:
        values.append("pool")
    if any(marker in blob for marker in ("однокомнат", "1к", "1-к", "студия")):
        values.append("one-room")
    if any(marker in blob for marker in ("двухкомнат", "2к", "2-к")):
        values.append("two-room")
    if "кухн" in blob:
        values.append("kitchen")
    if "кондиционер" in blob:
        values.append("ac")
    return sorted(set(values), key=values.index)


def detect_stay(blob: str) -> list[str]:
    values: list[str] = []
    if any(marker in blob for marker in ("с детьми", "для детей", "детская площадка", "семейн")):
        values.append("kids")
    if any(marker in blob for marker in ("с животными", "с питомц", "с собачк", "pet friendly")):
        values.append("pets")
    return values


def infer_filters(row: dict[str, Any]) -> dict[str, list[str]]:
    blob = text_blob(row)
    return {
        "distance": detect_distance(blob),
        "food": detect_food(blob),
        "price": detect_price(blob),
        "city": detect_city(blob),
        "beach": detect_beach(blob),
        "room": detect_room(blob),
        "stay": detect_stay(blob),
    }


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


def render_hotel_card(row: dict[str, Any]) -> str:
    filters = (row.get("details") or {}).get("filters") or {}
    attrs = " ".join(
        f'data-filter-{group}="{html.escape("|".join(filters.get(group) or []), quote=True)}"'
        for group in FILTER_GROUPS
    )
    href = page_path_from_url(row.get("page_url"), f"/hotels/{row['slug']}/")
    image = pick_cover_url(row)
    title = html.escape(row.get("title") or "")
    summary = html.escape(row.get("summary") or row.get("excerpt") or "")
    alt = title
    return (
        f'<a class="catalog-card" {attrs} href="{html.escape(href, quote=True)}">'
        f'<img alt="{alt}" loading="lazy" src="{html.escape(image, quote=True)}"/>'
        f"<h3>{title}</h3>"
        f"<p>{summary}</p>"
        f"</a>"
    )


def render_kvartira_card(row: dict[str, Any]) -> str:
    href = row.get("telegram_url") or row.get("page_url") or "/kvartira/"
    title = html.escape(row.get("title") or "")
    summary = html.escape(row.get("summary") or row.get("excerpt") or ((row.get("details") or {}).get("excerpt") or ""))
    image = pick_cover_url(row)
    badge = '<span class="catalog-card__badge">Видео</span>' if row.get("has_video") else ""
    return (
        f'<a class="catalog-card" href="{html.escape(href, quote=True)}" target="_blank" rel="noopener noreferrer">'
        f'<div class="catalog-card__media-wrap">{badge}<img src="{html.escape(image, quote=True)}" alt="{title}" loading="lazy" /></div>'
        f"<h3>{title}</h3>"
        f"<p>{summary}</p>"
        f"</a>"
    )


def replace_catalog_block(file_path: Path, marker: str, html_block: str) -> None:
    """Replace inner HTML of the catalog-grid div (handles nested <div> inside cards)."""
    text = file_path.read_text(encoding="utf-8")
    start = text.index(marker) + len(marker)
    depth = 1
    pos = start
    end_close = -1
    while depth > 0:
        next_open = text.find("<div", pos)
        next_close = text.find("</div>", pos)
        if next_close == -1:
            raise ValueError(f"Unclosed catalog block after {marker!r} in {file_path}")
        if next_open != -1 and next_open < next_close:
            depth += 1
            pos = next_open + 4
        else:
            depth -= 1
            end_close = next_close
            pos = next_close + len("</div>")
    if end_close == -1:
        raise ValueError(f"Could not find closing </div> for catalog grid in {file_path}")
    updated = text[:start] + html_block + text[end_close:]
    file_path.write_text(updated, encoding="utf-8")


def replace_once(text: str, pattern: str, replacement: str) -> str:
    return re.sub(pattern, replacement, text, count=1, flags=re.S)


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
    published = row.get("published_at")
    published_human = human_date(published)

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
    # Убрать строку «Источник: @…» из разметки (не показываем на сайте)
    text = re.sub(
        r'\s*<p class="media-note">Источник: <a href=".*?" target="_blank" rel="noopener noreferrer">.*?</a>\.</p>',
        "",
        text,
        count=1,
    )
    path.write_text(text, encoding="utf-8")


def rebuild_sitemap(rows: list[dict[str, Any]]) -> None:
    urlset = ET.Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
    urls = ["https://абхазберег.рф/", "https://абхазберег.рф/kvartira/"]
    urls.extend(row["page_url"] for row in rows if row.get("page_url") and row.get("source_kind") == "hotel")
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
            "select": "id,slug,source_kind,title,summary,excerpt,city,page_url,telegram_url,published_at,has_video,cover_url,details,is_active,listing_media(id,media_role,sort_order,public_url,storage_path,mime_type)",
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
        "".join(render_hotel_card(row) for row in hotel_rows),
    )
    replace_catalog_block(
        KVARTIRA_PATH,
        '<div class="catalog-grid" id="kvartira-catalog-grid">',
        "".join(render_kvartira_card(row) for row in kvartira_rows),
    )

    for row in hotel_rows:
        update_hotel_page(row)

    rebuild_sitemap(rows)

    print(f"Нормализовано фильтров: {updated}")
    print(f"Пересобрано отелей: {len(hotel_rows)}")
    print(f"Пересобрано квартир: {len(kvartira_rows)}")


if __name__ == "__main__":
    main()
