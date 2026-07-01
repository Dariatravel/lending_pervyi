#!/usr/bin/env python3
"""Apply site-wide SEO improvements to generated static pages.

The script is intentionally conservative: it updates metadata and semantic
structure, but does not change catalog filters, business logic, data files, or
object content.
"""
from __future__ import annotations

import html
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
CANON_ORIGIN = "https://абхазберег.рф"
YANDEX_MEDIA = "https://storage.yandexcloud.net/abhazbereg-media/media"
SNAPSHOT_PATH = ROOT / "data" / "catalog-snapshot.json"
SITEMAP_PATH = ROOT / "sitemap.xml"
FAVICON_BLOCK = """<link href="https://storage.yandexcloud.net/abhazbereg-media/media/branding/favicon-abhazbereg.png" rel="icon" type="image/png"/>
<link href="https://storage.yandexcloud.net/abhazbereg-media/media/branding/favicon-abhazbereg.png" rel="shortcut icon" type="image/png"/>
<link href="https://storage.yandexcloud.net/abhazbereg-media/media/branding/apple-touch-icon.png" rel="apple-touch-icon"/>"""


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def escape_attr(value: str) -> str:
    return html.escape(value, quote=True)


def normalized_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def clean_title(value: str) -> str:
    value = normalized_text(value)
    value = re.sub(r"\s*[💥🔥🩵💦😍🌟].*$", "", value).strip()
    return value or normalized_text(value)


def city_from_row(row: dict[str, Any]) -> str:
    return normalized_text(row.get("city") or row.get("location_text") or "").split(",", 1)[0]


def build_object_description(row: dict[str, Any]) -> str:
    title = clean_title(str(row.get("title") or "Объект"))
    city = city_from_row(row) or "Абхазия"
    distance = normalized_text(row.get("distance_text") or row.get("beach_text") or "")
    capacity = normalized_text(row.get("capacity_text") or "")
    kind = "квартира" if row.get("source_kind") == "kvartira" else "отель"

    parts = [f"{title} в {city}: {kind} для отдыха в Абхазии"]
    if distance:
        parts.append(distance)
    if capacity:
        parts.append(capacity)
    parts.append("фото, видео, сезонные цены и бронирование напрямую через АБХАЗБЕРЕГ")
    desc = ", ".join(parts).replace("..", ".")
    if len(desc) > 178:
        desc = desc[:175].rstrip(" ,.") + "..."
    return desc


def build_object_title(row: dict[str, Any]) -> str:
    title = clean_title(str(row.get("title") or "Объект"))
    city = city_from_row(row)
    suffix = "цены, фото, бронь"
    full = f"{title} — {city}, {suffix}" if city else f"{title} — {suffix}"
    if len(full) <= 75:
        return full
    short_title = title[: max(32, 70 - len(suffix) - 5)].rstrip(" ,.-")
    return f"{short_title}… — {suffix}"


def set_meta(soup: BeautifulSoup, selector: dict[str, str], content: str) -> None:
    tag = soup.find("meta", attrs=selector)
    if tag:
        tag["content"] = content


def set_title(soup: BeautifulSoup, content: str) -> None:
    tag = soup.find("title")
    if tag:
        tag.string = content


def replace_header_h2_with_h1(soup: BeautifulSoup) -> bool:
    if soup.select_one(".hotel-card__header-main h1"):
        return False
    h2 = soup.select_one(".hotel-card__header-main h2")
    if not h2:
        return False
    h1 = soup.new_tag("h1")
    for attr, value in h2.attrs.items():
        h1[attr] = value
    h1.string = h2.get_text()
    h2.replace_with(h1)
    return True


def script_json_ld(soup: BeautifulSoup, data: dict[str, Any], schema_name: str) -> Any:
    tag = soup.new_tag("script")
    tag["type"] = "application/ld+json"
    tag["data-schema"] = schema_name
    tag.string = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    return tag


def ensure_breadcrumb_schema(soup: BeautifulSoup, crumbs: list[tuple[str, str]]) -> bool:
    if soup.find("script", attrs={"data-schema": "breadcrumbs"}):
        return False
    head = soup.find("head")
    if not head:
        return False
    data = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": i + 1,
                "name": name,
                "item": url,
            }
            for i, (name, url) in enumerate(crumbs)
        ],
    }
    head.append(script_json_ld(soup, data, "breadcrumbs"))
    return True


def ensure_itemlist_schema(soup: BeautifulSoup, page_url: str) -> bool:
    if soup.find("script", attrs={"data-schema": "itemlist"}):
        return False
    cards = soup.select(".podborki-catalog-card")
    if not cards:
        return False
    items = []
    for i, card in enumerate(cards[:100], start=1):
        href = card.get("href") or ""
        name = normalized_text(card.find("h3").get_text(" ", strip=True) if card.find("h3") else "")
        if not href or not name:
            continue
        url = href if href.startswith("http") else f"{CANON_ORIGIN}{href}"
        items.append({"@type": "ListItem", "position": i, "url": url, "name": name})
    if not items:
        return False
    head = soup.find("head")
    if not head:
        return False
    data = {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": normalized_text(soup.find("h1").get_text(" ", strip=True) if soup.find("h1") else "Подборка жилья"),
        "url": page_url,
        "numberOfItems": len(items),
        "itemListElement": items,
    }
    head.append(script_json_ld(soup, data, "itemlist"))
    return True


def canonical_url(soup: BeautifulSoup) -> str:
    tag = soup.find("link", rel="canonical")
    return str(tag.get("href") or "").strip() if tag else ""


def update_object_page(row: dict[str, Any]) -> bool:
    details = row.get("details") or {}
    raw_path = details.get("page_path")
    if raw_path:
        path = Path(raw_path)
    else:
        folder = "kvartira" if row.get("source_kind") == "kvartira" else "hotels"
        path = ROOT / folder / str(row.get("slug")) / "index.html"
    if not path.is_file():
        return False
    before = path.read_text(encoding="utf-8")
    soup = BeautifulSoup(before, "html.parser")

    page_url = str(row.get("page_url") or canonical_url(soup) or "")
    desc = build_object_description(row)
    title = build_object_title(row)
    set_title(soup, title)
    set_meta(soup, {"name": "description"}, desc)
    set_meta(soup, {"property": "og:title"}, f"{clean_title(str(row.get('title') or 'Объект'))} — обзор и цены")
    set_meta(soup, {"property": "og:description"}, desc)
    replace_header_h2_with_h1(soup)
    crumbs = [
        ("Главная", f"{CANON_ORIGIN}/"),
        ("Каталог", f"{CANON_ORIGIN}/#catalog"),
        (clean_title(str(row.get("title") or "Объект")), page_url),
    ]
    ensure_breadcrumb_schema(soup, crumbs)
    after = str(soup)
    if after != before:
        path.write_text(after, encoding="utf-8")
        return True
    return False


def update_legacy_object_page(path: Path) -> bool:
    """Update object pages that are no longer present in catalog-snapshot."""
    before = path.read_text(encoding="utf-8")
    soup = BeautifulSoup(before, "html.parser")
    if not soup.select_one(".hotel-card__header-main"):
        return False
    page_url = canonical_url(soup)
    if not page_url:
        return False
    heading = soup.select_one(".hotel-card__header-main h1") or soup.select_one(".hotel-card__header-main h2")
    raw_title = normalized_text(heading.get_text(" ", strip=True) if heading else "")
    title = clean_title(raw_title.title() if raw_title.isupper() else raw_title)
    location = normalized_text(soup.select_one(".hotel-card__rating-summary").get_text(" ", strip=True) if soup.select_one(".hotel-card__rating-summary") else "")
    kind = "квартира" if "/kvartira/" in page_url else "отель"
    desc_parts = [f"{title}: {kind} для отдыха в Абхазии"]
    if location:
        desc_parts.append(location)
    desc_parts.append("фото, видео, условия, сезонные цены и бронирование напрямую через АБХАЗБЕРЕГ")
    desc = ", ".join(desc_parts)
    if len(desc) > 178:
        desc = desc[:175].rstrip(" ,.") + "..."
    city = location.split(".", 1)[0] if location else ""
    page_title = f"{title} — {city}, цены, фото, бронь" if city else f"{title} — цены, фото, бронь"
    if len(page_title) > 75:
        page_title = f"{title[:48].rstrip()}… — цены, фото, бронь"
    set_title(soup, page_title)
    set_meta(soup, {"name": "description"}, desc)
    set_meta(soup, {"property": "og:title"}, f"{title} — обзор и цены")
    set_meta(soup, {"property": "og:description"}, desc)
    replace_header_h2_with_h1(soup)
    ensure_breadcrumb_schema(
        soup,
        [
            ("Главная", f"{CANON_ORIGIN}/"),
            ("Каталог", f"{CANON_ORIGIN}/#catalog"),
            (title, page_url),
        ],
    )
    after = str(soup)
    if after != before:
        path.write_text(after, encoding="utf-8")
        return True
    return False


def collection_intro_text(h1: str, count: int) -> str:
    lower = h1.lower()
    if "гагра" in lower:
        return "Гагра подойдёт тем, кому важны активная инфраструктура, кафе, прогулки и быстрый доступ к развлечениям. В подборке собраны проверенные варианты с фото, расстоянием до пляжа и сезонными ценами."
    if "пицунд" in lower or "лдзаа" in lower:
        return "Пицунда и Лдзаа чаще выбирают за спокойное море, сосны и пляжный отдых без городской суеты. Сравните варианты по пляжу, вместимости, питанию и бюджету."
    if "сухум" in lower:
        return "Сухум — более городской формат отдыха: набережная, кафе, рынки и широкие пляжи в отдельных районах. Ниже — варианты размещения для разных сценариев поездки."
    if "бассейн" in lower:
        return "Бассейн особенно важен для семей с детьми и отдыха в жаркие месяцы. В подборке — объекты, где бассейн указан среди ключевых удобств."
    if "мор" in lower or "берег" in lower:
        return "Если хочется жить ближе к пляжу, начинайте с этой подборки. Здесь собраны варианты, где путь к морю занимает минимум времени."
    if "питан" in lower:
        return "Питание на месте экономит время и делает отдых спокойнее, особенно с детьми. Сравните объекты с завтраками, кафе или полным питанием."
    return f"В подборке {count} проверенных вариантов размещения в Абхазии. Сравните локацию, расстояние до пляжа, формат жилья и условия перед бронированием."


def collection_faq_items(h1: str) -> list[tuple[str, str]]:
    return [
        ("Как выбрать подходящий вариант?", "Смотрите на район, расстояние до пляжа, состав гостей, питание, наличие кухни, бассейна и реальные фото объекта."),
        ("Цены на странице актуальны?", "Цены регулярно обновляются, но перед бронированием лучше подтвердить стоимость и наличие у менеджера."),
        ("Можно ли подобрать замену?", "Да. Если объект занят или не подходит по деталям, можно написать в АБХАЗБЕРЕГ и получить подборку похожих вариантов."),
    ]


def update_collection_page(path: Path) -> bool:
    before = path.read_text(encoding="utf-8")
    soup = BeautifulSoup(before, "html.parser")
    if not soup.select_one(".podborki-page"):
        return False
    h1_tag = soup.find("h1")
    h1 = normalized_text(h1_tag.get_text(" ", strip=True) if h1_tag else "Подборка жилья в Абхазии")
    cards_count = len(soup.select(".podborki-catalog-card"))
    desc = f"{h1}: {cards_count} проверенных вариантов жилья в Абхазии с фото, расстоянием до пляжа, условиями и прямым бронированием."
    if len(desc) > 178:
        desc = desc[:175].rstrip(" ,.") + "..."
    set_meta(soup, {"name": "description"}, desc)
    page_url = canonical_url(soup)
    if page_url:
        ensure_breadcrumb_schema(
            soup,
            [
                ("Главная", f"{CANON_ORIGIN}/"),
                ("Подборки", f"{CANON_ORIGIN}/podborki/"),
                (h1, page_url),
            ],
        )
        ensure_itemlist_schema(soup, page_url)

    body = soup.select_one(".podborki-body")
    if body and not body.select_one(".podborki-seo-copy"):
        intro = soup.new_tag("section")
        intro["class"] = "podborki-seo-copy"
        h2 = soup.new_tag("h2")
        h2.string = f"Как смотреть подборку «{h1}»"
        p = soup.new_tag("p")
        p.string = collection_intro_text(h1, cards_count)
        intro.append(h2)
        intro.append(p)
        body.insert(0, intro)
    if body and not body.select_one(".podborki-faq"):
        faq = soup.new_tag("section")
        faq["class"] = "podborki-faq"
        h2 = soup.new_tag("h2")
        h2.string = "Частые вопросы"
        faq.append(h2)
        for q, a in collection_faq_items(h1):
            item = soup.new_tag("article")
            q_tag = soup.new_tag("h3")
            q_tag.string = q
            a_tag = soup.new_tag("p")
            a_tag.string = a
            item.append(q_tag)
            item.append(a_tag)
            faq.append(item)
        body.append(faq)
    after = str(soup)
    if after != before:
        path.write_text(after, encoding="utf-8")
        return True
    return False


def media_url(value: str) -> str:
    if value.startswith("/media/"):
        return f"{YANDEX_MEDIA}/{value.removeprefix('/media/')}"
    if value.startswith("../media/"):
        return f"{YANDEX_MEDIA}/{value.removeprefix('../media/')}"
    if value.startswith("../../media/"):
        return f"{YANDEX_MEDIA}/{value.removeprefix('../../media/')}"
    if value.startswith(f"{CANON_ORIGIN}/media/"):
        return f"{YANDEX_MEDIA}/{value.removeprefix(CANON_ORIGIN + '/media/')}"
    return value


def ensure_site_icons(path: Path) -> bool:
    before = path.read_text(encoding="utf-8")
    if "</head>" not in before:
        return False
    cleaned = "\n".join(
        line
        for line in before.splitlines()
        if "favicon-abhazbereg.png" not in line and "apple-touch-icon.png" not in line
    )
    if before.endswith("\n"):
        cleaned += "\n"
    stylesheet = re.search(r"(?m)^([ \t]*<link[^>]+rel=[\"']stylesheet[\"'][^>]*>\s*)", cleaned)
    if stylesheet:
        insert_at = stylesheet.start()
        indent = re.match(r"[ \t]*", stylesheet.group(1)).group(0)
        block = "\n".join(indent + line for line in FAVICON_BLOCK.splitlines()) + "\n"
        after = cleaned[:insert_at] + block + cleaned[insert_at:]
    else:
        head = re.search(r"(?m)^([ \t]*)</head>", cleaned)
        indent = head.group(1) if head else ""
        block = "\n".join(indent + line for line in FAVICON_BLOCK.splitlines()) + "\n"
        after = cleaned.replace("</head>", block + "</head>", 1)
    if after != before:
        path.write_text(after, encoding="utf-8")
        return True
    return False


def update_blog_index() -> bool:
    path = ROOT / "blog" / "index.html"
    if not path.is_file():
        return False
    before = path.read_text(encoding="utf-8")
    after = re.sub(r'(src|href|content)="([^"]*media/[^"]+)"', lambda m: f'{m.group(1)}="{escape_attr(media_url(m.group(2)))}"', before)
    if after != before:
        path.write_text(after, encoding="utf-8")
        return True
    return False


def update_generic_breadcrumbs(path: Path) -> bool:
    before = path.read_text(encoding="utf-8")
    soup = BeautifulSoup(before, "html.parser")
    page_url = canonical_url(soup)
    if not page_url or soup.find("script", attrs={"data-schema": "breadcrumbs"}):
        return False
    rel = path.relative_to(ROOT)
    h1 = normalized_text(soup.find("h1").get_text(" ", strip=True) if soup.find("h1") else "")
    if not h1:
        return False
    if rel.parts[0] == "blog":
        crumbs = [("Главная", f"{CANON_ORIGIN}/"), ("Блог", f"{CANON_ORIGIN}/blog/"), (h1, page_url)]
    elif rel.parts[0] == "podborki":
        crumbs = [("Главная", f"{CANON_ORIGIN}/"), ("Подборки", f"{CANON_ORIGIN}/podborki/"), (h1, page_url)]
    else:
        crumbs = [("Главная", f"{CANON_ORIGIN}/"), (h1, page_url)]
    if ensure_breadcrumb_schema(soup, crumbs):
        path.write_text(str(soup), encoding="utf-8")
        return True
    return False


def robots_allows_index(soup: BeautifulSoup) -> bool:
    tag = soup.find("meta", attrs={"name": "robots"})
    content = str(tag.get("content") or "").lower() if tag else ""
    return "noindex" not in content


def rebuild_sitemap() -> int:
    urls: list[tuple[str, Path]] = []
    seen: set[str] = set()
    for path in sorted(ROOT.rglob("index.html")):
        rel = path.relative_to(ROOT)
        if rel.parts[0] in {"output", "node_modules", ".git"}:
            continue
        if rel.parts[0].startswith("concept"):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        soup = BeautifulSoup(text, "html.parser")
        if not robots_allows_index(soup):
            continue
        url = canonical_url(soup)
        if not url or not url.startswith(CANON_ORIGIN):
            continue
        if url in seen:
            continue
        seen.add(url)
        urls.append((url, path))
    urls.sort(key=lambda row: (row[0].count("/"), row[0]))

    urlset = ET.Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
    for url, path in urls:
        node = ET.SubElement(urlset, "url")
        loc = ET.SubElement(node, "loc")
        loc.text = url
        lastmod = ET.SubElement(node, "lastmod")
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        lastmod.text = mtime.date().isoformat()
    tree = ET.ElementTree(urlset)
    try:
        ET.indent(tree.getroot(), space="  ")
    except (AttributeError, TypeError):
        pass
    tree.write(SITEMAP_PATH, encoding="utf-8", xml_declaration=True)
    return len(urls)


def main() -> int:
    snapshot = read_json(SNAPSHOT_PATH)
    rows = [row for row in snapshot.get("listings", []) if row.get("is_active", True)]
    snapshot_urls = {str(row.get("page_url") or "").strip() for row in rows if row.get("page_url")}
    object_updates = 0
    for row in rows:
        if row.get("source_kind") in {"hotel", "kvartira"} and update_object_page(row):
            object_updates += 1

    legacy_object_updates = 0
    for folder in ("hotels", "kvartira"):
        for path in sorted((ROOT / folder).glob("*/index.html")):
            try:
                soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
                if canonical_url(soup) in snapshot_urls:
                    continue
            except Exception:
                continue
            if update_legacy_object_page(path):
                legacy_object_updates += 1

    collection_updates = 0
    for path in sorted((ROOT / "podborki").glob("*/index.html")):
        if update_collection_page(path):
            collection_updates += 1

    blog_updated = update_blog_index()

    breadcrumb_updates = 0
    for path in sorted(ROOT.rglob("index.html")):
        if path.relative_to(ROOT).parts[0] in {"hotels", "kvartira", "blog", "podborki", "about"}:
            if update_generic_breadcrumbs(path):
                breadcrumb_updates += 1

    icon_updates = 0
    for path in sorted(ROOT.rglob("index.html")):
        rel = path.relative_to(ROOT)
        if rel.parts[0] in {"output", "node_modules", ".git"} or rel.parts[0].startswith("concept"):
            continue
        if ensure_site_icons(path):
            icon_updates += 1

    sitemap_urls = rebuild_sitemap()

    print(f"object_pages_updated={object_updates}")
    print(f"legacy_object_pages_updated={legacy_object_updates}")
    print(f"collection_pages_updated={collection_updates}")
    print(f"blog_index_media_updated={int(blog_updated)}")
    print(f"generic_breadcrumbs_added={breadcrumb_updates}")
    print(f"site_icons_added={icon_updates}")
    print(f"sitemap_urls={sitemap_urls}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
