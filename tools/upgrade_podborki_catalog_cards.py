#!/usr/bin/env python3
"""
Заменяет списки podborki-ranked-list на сетку catalog-grid с карточками как на главной.
Запуск из корня репозитория: python tools/upgrade_podborki_catalog_cards.py
"""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

_TOOLS = Path(__file__).resolve().parent
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from podborki_hotel_match import (
    guess_podborki_href_from_title,
    load_hotel_catalog,
    load_kvartira_catalog,
)

REPO = Path(__file__).resolve().parents[1]
PODBORKI = REPO / "podborki"
KV_PATH = REPO / "kvartira_cards.json"


def load_kv_images_by_slug() -> dict[str, str]:
    out: dict[str, str] = {}
    with KV_PATH.open(encoding="utf-8") as f:
        for row in json.load(f):
            slug = row.get("slug")
            if not slug:
                continue
            img = (row.get("image") or "").strip()
            out[slug] = img or f"/media/kvartira-cards/{slug}-cover.jpg"
    return out


def cover_src_for_href(href: str | None, kv_img: dict[str, str]) -> str | None:
    if not href:
        return None
    m = re.match(r"/hotels/([^/]+)/?", href)
    if m:
        slug = m.group(1)
        return f"../../media/cards/{slug}.jpg"
    m = re.match(r"/kvartira/([^/]+)/?", href)
    if m:
        slug = m.group(1)
        path = kv_img.get(slug) or f"/media/kvartira-cards/{slug}-cover.jpg"
        if path.startswith("/"):
            return "../.." + path
        return path
    return None


def li_to_catalog_card(li, kv_img: dict[str, str]) -> str:
    a = li.find("a", class_=lambda c: c and "podborki-card--link" in str(c))
    href = a.get("href") if a and a.get("href") else None
    root = a if a else li.find("div", class_=lambda c: c and "podborki-card" in str(c))
    if root is None:
        return ""
    body = root.find("div", class_="podborki-card__body")
    if body is None:
        return ""
    rank_el = body.find("span", class_="podborki-card__rank")
    title_el = body.find("p", class_="podborki-card__title")
    meta = body.find("div", class_="podborki-card__meta")
    rank = rank_el.get_text(strip=True) if rank_el else ""
    title = title_el.get_text() if title_el else ""
    details: list[str] = []
    if meta:
        for sp in meta.find_all("span"):
            t = sp.get_text(strip=True)
            if t:
                details.append(t)
    title_esc = html.escape(title)
    p_inner = "<br />".join(html.escape(d) for d in details)
    cover = cover_src_for_href(href, kv_img)
    badge = (
        f'<span class="catalog-card__badge catalog-card__badge--rank" '
        f'aria-label="Место в подборке — {html.escape(rank)}">{html.escape(rank)}</span>'
    )
    if cover:
        media = (
            f'<div class="catalog-card__media-wrap">{badge}'
            f'<img src="{html.escape(cover)}" alt="{title_esc}" loading="lazy" decoding="async" />'
            f"</div>"
        )
    else:
        media = (
            f'<div class="catalog-card__media-wrap">{badge}'
            f'<div class="catalog-card__media-fallback" role="img" aria-hidden="true">Фото</div>'
            f"</div>"
        )
    inner = f"{media}<h3>{title_esc}</h3><p>{p_inner}</p>"
    if href:
        return (
            f'<a class="catalog-card podborki-catalog-card" href="{html.escape(href)}">{inner}</a>'
        )
    return f'<div class="catalog-card podborki-catalog-card catalog-card--no-link">{inner}</div>'


def upgrade_file(path: Path, kv_img: dict[str, str]) -> bool:
    raw = path.read_text(encoding="utf-8")
    soup = BeautifulSoup(raw, "html.parser")
    ols = soup.select("ol.podborki-ranked-list")
    if not ols:
        return False
    for ol in ols:
        grid = soup.new_tag("div")
        grid["class"] = ["catalog-grid", "podborki-catalog-grid"]
        for li in ol.find_all("li", recursive=False):
            chunk = li_to_catalog_card(li, kv_img).strip()
            if not chunk:
                continue
            parsed = BeautifulSoup(chunk, "html.parser")
            el = parsed.find(["a", "div"])
            if el:
                grid.append(el)
        ol.replace_with(grid)
    path.write_text(str(soup), encoding="utf-8")
    return True


def repair_no_link_cards(path: Path) -> bool:
    """Карточки без href → ссылка и обложка по названию (отель или квартира)."""
    raw = path.read_text(encoding="utf-8")
    if "catalog-card--no-link" not in raw:
        return False
    hotel_catalog = load_hotel_catalog()
    kv_catalog = load_kvartira_catalog()
    soup = BeautifulSoup(raw, "html.parser")
    changed = False
    for div in soup.select("div.catalog-card.podborki-catalog-card.catalog-card--no-link"):
        h3 = div.find("h3")
        if not h3:
            continue
        title_plain = h3.get_text(strip=True)
        href = guess_podborki_href_from_title(title_plain, hotel_catalog, kv_catalog)
        if not href:
            continue
        m = re.match(r"/(hotels|kvartira)/([^/]+)/?", href.strip())
        if not m:
            continue
        kind, slug = m.group(1), m.group(2)
        if kind == "hotels":
            cover = f"../../media/cards/{slug}.jpg"
        else:
            row = next((r for r in kv_catalog if r.get("slug") == slug), None)
            img = (row.get("image") if row else "") or f"/media/kvartira-cards/{slug}-cover.jpg"
            cover = f"../..{img}" if img.startswith("/") else img
        media = div.find("div", class_=lambda c: c and "catalog-card__media-wrap" in str(c))
        if not media:
            continue
        for fb in media.select(".catalog-card__media-fallback"):
            fb.decompose()
        if not media.find("img"):
            img = soup.new_tag(
                "img",
                src=cover,
                alt=title_plain,
                loading="lazy",
                decoding="async",
            )
            media.append(img)
        div.name = "a"
        div["href"] = href
        classes = div.get("class", [])
        if isinstance(classes, str):
            classes = [classes]
        div["class"] = [c for c in classes if c != "catalog-card--no-link"]
        changed = True
    if changed:
        path.write_text(str(soup), encoding="utf-8")
    return changed


def main() -> None:
    kv_img = load_kv_images_by_slug()
    n_upgrade = 0
    n_repair = 0
    for sub in sorted(PODBORKI.iterdir()):
        if not sub.is_dir():
            continue
        idx = sub / "index.html"
        if not idx.is_file():
            continue
        if upgrade_file(idx, kv_img):
            print("OK ol→grid", idx.relative_to(REPO))
            n_upgrade += 1
        if repair_no_link_cards(idx):
            print("OK repair", idx.relative_to(REPO))
            n_repair += 1
    print("Секций ol→grid:", n_upgrade, "| починено без ссылки:", n_repair)


if __name__ == "__main__":
    main()
