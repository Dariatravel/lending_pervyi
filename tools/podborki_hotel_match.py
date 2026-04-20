"""
Сопоставление строки подборки с отелем или квартирой по названию (если нет t.me-ссылки в исходнике).
Отели: current_pages.json + hotels/<slug>/index.html.
Квартиры: kvartira_cards.json.
"""
from __future__ import annotations

import json
import re
from html import unescape
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CURRENT_PAGES = REPO / "output" / "current_pages.json"
HOTELS_DIR = REPO / "hotels"
KVARTIRA_CARDS = REPO / "kvartira_cards.json"

_WORD = re.compile(r"[a-zа-яё]{4,}", re.I)
_H2_HOTEL = re.compile(
    r'<div class="hotel-card__header-main"[^>]*>\s*<h2[^>]*>(.*?)</h2>',
    re.I | re.S,
)


def normalize_podborki_title(s: str) -> str:
    t = unescape(s or "")
    t = re.sub(r"\s+", " ", t.strip().lower())
    return t


def extract_quoted_brand(title: str) -> str:
    t = unescape(title or "")
    m = re.search(r'[«""]([^»""]+)[»""]', t)
    if m:
        return m.group(1).strip().lower()
    return ""


def _title_from_hotel_page(path: Path) -> str:
    raw = path.read_text(encoding="utf-8")
    m = _H2_HOTEL.search(raw)
    if not m:
        m = re.search(r"<h2[^>]*>(.*?)</h2>", raw, re.I | re.S)
    if not m:
        return ""
    inner = re.sub(r"<[^>]+>", "", m.group(1))
    return unescape(inner).strip()


def load_hotel_catalog() -> list[dict[str, str]]:
    by_slug: dict[str, str] = {}
    if CURRENT_PAGES.is_file():
        try:
            for row in json.loads(CURRENT_PAGES.read_text(encoding="utf-8")):
                slug = row.get("slug")
                t = (row.get("title") or "").strip()
                if isinstance(slug, str) and slug and t:
                    by_slug[slug] = t
        except (OSError, json.JSONDecodeError):
            pass
    if HOTELS_DIR.is_dir():
        for idx in HOTELS_DIR.glob("*/index.html"):
            slug = idx.parent.name
            if slug in by_slug and by_slug[slug]:
                continue
            t = _title_from_hotel_page(idx)
            if t:
                by_slug[slug] = t
    return [{"slug": s, "title": t} for s, t in sorted(by_slug.items())]


def load_kvartira_catalog() -> list[dict[str, str]]:
    if not KVARTIRA_CARDS.is_file():
        return []
    try:
        rows = json.loads(KVARTIRA_CARDS.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    out: list[dict[str, str]] = []
    for row in rows:
        slug = row.get("slug")
        if not isinstance(slug, str) or not slug:
            continue
        u = (row.get("url") or "").strip()
        u = u.replace("https://абхазберег.рф", "").replace("http://абхазберег.рф", "")
        if not u.startswith("/kvartira/"):
            u = f"/kvartira/{slug}/"
        if not u.endswith("/"):
            u = u + "/"
        img = (row.get("image") or "").strip()
        out.append(
            {
                "slug": slug,
                "title": (row.get("title") or "").strip(),
                "url": u,
                "image": img,
            }
        )
    return out


def match_podborki_title_to_hotel(
    podborki_title: str, catalog: list[dict[str, str]]
) -> dict[str, str] | None:
    pn = normalize_podborki_title(podborki_title)
    brand = extract_quoted_brand(podborki_title)
    scored: list[tuple[int, dict[str, str]]] = []

    for row in catalog:
        slug = row.get("slug") or ""
        ht = normalize_podborki_title(row.get("title") or "")
        slug_spaced = slug.replace("-", " ").lower()

        score = 0
        if brand:
            if brand in ht or brand in slug_spaced:
                score += 120
            else:
                continue
        else:
            if pn and ht and (pn in ht or ht in pn or pn[: min(20, len(pn))] in ht):
                score += 60
            else:
                continue

        pw = set(_WORD.findall(pn))
        hw = set(_WORD.findall(ht))
        score += 14 * len(pw & hw)

        if "коттедж" in pn or "коттеджи" in pn:
            if "мини" in ht and "коттедж" not in ht:
                score -= 85
            if "коттедж" in ht or "коттеджи" in ht:
                score += 35
        if "мини" in pn or "мини-отель" in pn:
            if "коттедж" in ht and "мини" not in ht:
                score -= 85
            if "мини" in ht:
                score += 35
        if "эконом" in pn and "эконом" not in ht:
            score -= 30
        if "эконом" in pn and "эконом" in ht:
            score += 25

        if score > 0:
            scored.append((score, row))

    scored.sort(key=lambda x: -x[0])
    if not scored:
        return None
    best, top_row = scored[0][0], scored[0][1]
    need = 90 if brand else 65
    if best < need:
        return None
    if len(scored) > 1 and scored[1][0] >= best - 5:
        return None
    return top_row


def match_podborki_title_to_kvartira(
    podborki_title: str, catalog: list[dict[str, str]]
) -> dict[str, str] | None:
    pn = normalize_podborki_title(podborki_title)
    brand = extract_quoted_brand(podborki_title)
    scored: list[tuple[int, dict[str, str]]] = []

    for row in catalog:
        slug = row.get("slug") or ""
        ht = normalize_podborki_title(row.get("title") or "")
        slug_spaced = slug.replace("-", " ").lower()

        score = 0
        if brand:
            if brand in ht or brand in slug_spaced:
                score += 120
            else:
                continue
        else:
            if pn and ht and (pn in ht or ht in pn or pn[: min(20, len(pn))] in ht):
                score += 60
            else:
                continue

        pw = set(_WORD.findall(pn))
        hw = set(_WORD.findall(ht))
        score += 14 * len(pw & hw)

        if "квартир" in pn or "студи" in pn:
            if "квартир" in ht or "студи" in ht:
                score += 30
            elif "дом" in pn and "дом" in ht:
                score += 20
        if "дом под ключ" in pn and ("дом" in ht or "коттедж" in ht):
            score += 25
        if "отель" in pn or "гостиниц" in pn:
            if "отель" not in ht and "гостиниц" not in ht:
                score -= 50

        if score > 0:
            scored.append((score, row))

    scored.sort(key=lambda x: -x[0])
    if not scored:
        return None
    best, top_row = scored[0][0], scored[0][1]
    need = 90 if brand else 65
    if best < need:
        return None
    if len(scored) > 1 and scored[1][0] >= best - 5:
        return None
    return top_row


def podborki_title_prefers_kvartira(title: str) -> bool:
    pn = normalize_podborki_title(title)
    if any(
        x in pn
        for x in (
            "квартир",
            "студи",
            "апартам",
            "дом под ключ",
        )
    ):
        return True
    return False


def podborki_title_prefers_hotel(title: str) -> bool:
    pn = normalize_podborki_title(title)
    return any(
        x in pn
        for x in (
            "отель",
            "гостиниц",
            "мини-отель",
            "мини отель",
            "гостевой комплекс",
            "гостевой дом",
        )
    )


def guess_podborki_href_from_title(
    podborki_title: str,
    hotel_catalog: list[dict[str, str]],
    kv_catalog: list[dict[str, str]],
) -> str | None:
    """Один href (/hotels/…/ или /kvartira/…/) или None, если не угадали однозначно."""
    kv_first = podborki_title_prefers_kvartira(podborki_title) and not podborki_title_prefers_hotel(
        podborki_title
    )
    hotel_first = podborki_title_prefers_hotel(podborki_title) and not podborki_title_prefers_kvartira(
        podborki_title
    )

    if kv_first:
        k = match_podborki_title_to_kvartira(podborki_title, kv_catalog)
        if k:
            return k["url"]
        h = match_podborki_title_to_hotel(podborki_title, hotel_catalog)
        if h:
            return f"/hotels/{h['slug']}/"
        return None

    if hotel_first:
        h = match_podborki_title_to_hotel(podborki_title, hotel_catalog)
        if h:
            return f"/hotels/{h['slug']}/"
        k = match_podborki_title_to_kvartira(podborki_title, kv_catalog)
        if k:
            return k["url"]
        return None

    h = match_podborki_title_to_hotel(podborki_title, hotel_catalog)
    k = match_podborki_title_to_kvartira(podborki_title, kv_catalog)
    if h and not k:
        return f"/hotels/{h['slug']}/"
    if k and not h:
        return k["url"]
    if h and k:
        if podborki_title_prefers_kvartira(podborki_title):
            return k["url"]
        return f"/hotels/{h['slug']}/"
    return None
