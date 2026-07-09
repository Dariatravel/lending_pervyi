#!/usr/bin/env python3
"""
Генерирует статические страницы подборок из текстовых файлов ПОДБОРКИ.
Источник: первая строка = название подборки; порядок блоков = ранжирование.
Ссылки t.me разбираются для внутренних URL отелей/квартир; без сопоставления — только текст.
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

_TOOLS_DIR = Path(__file__).resolve().parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

REPO = Path(__file__).resolve().parents[1]
PODBORKI_ROOT = Path("/Users/darya_botova/Documents/ПОДБОРКИ")
OUT_DIR = REPO / "podborki"
CURRENT_PAGES = REPO / "output" / "current_pages.json"
KVARTIRA_CARDS = REPO / "kvartira_cards.json"
ASSET_VERSION = "202607091130"
YANDEX_MEDIA_BASE = "https://storage.yandexcloud.net/abhazbereg-media/media"

from podborki_hotel_match import (
    guess_podborki_href_from_title,
    load_hotel_catalog,
    load_kvartira_catalog,
)

_SLUG_CYR = str.maketrans(
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

SPECIAL_BOOKING_SLUGS = {
    "villalubov": "villa-lyubov-vyhod-iz-otelya-srazu-na-plyazh-2716",
}

# Алиасы старых message_id из файлов подборок -> актуальные source_message_id карточек отелей
BOOKING_MESSAGE_ID_ALIASES = {
    1694: 4279,  # "БЕРЕГ СВЯТОЙ СОФИИ"
}

# Алиасы старых message_id квартир из файлов подборок -> актуальные message_id в kvartira_cards.json
KVARTIRA_MESSAGE_ID_ALIASES = {
    1025: 1378,  # "МОНРО": в подборках старый пост, на сайте актуальная карточка 1378
    1185: 1193,  # "ЧЕРНОМОРСКАЯ-1": в каталоге актуальная карточка "ЧЕРНОМОРСКАЯ-2"
}

# Фиксированные названия для конкретных подборок:
# сохраняются даже после повторной генерации из исходных txt.
TITLE_OVERRIDES = {
    "novyy-afon-vse-varianty": "Варианты размещения в г. Новый Афон",
}


def slugify_segment(s: str) -> str:
    s = unicodedata.normalize("NFKC", s).lower().translate(_SLUG_CYR)
    s = re.sub(r"[^a-z0-9]+", "-", s, flags=re.I)
    return s.strip("-")


def file_to_slug(path: Path) -> str:
    name = path.name
    if name.endswith(".txt"):
        name = name[:-4]
    if name.startswith("подборка_"):
        name = name[len("подборка_") :]
    return slugify_segment(name) or "podboraka"


def load_maps():
    hotels: dict[int, dict] = {}
    with CURRENT_PAGES.open(encoding="utf-8") as f:
        for row in json.load(f):
            sid = row.get("source_id")
            if isinstance(sid, int):
                hotels[sid] = {"slug": row["slug"], "title": row.get("title") or ""}
    kv: dict[int, dict] = {}
    with KVARTIRA_CARDS.open(encoding="utf-8") as f:
        for row in json.load(f):
            mid = row.get("message_id")
            if isinstance(mid, int):
                kv[mid] = {
                    "slug": row["slug"],
                    "title": row.get("title") or "",
                    "url": (row.get("url") or "").replace("https://абхазберег.рф", "")
                    or f"/kvartira/{row['slug']}/",
                    "image": (row.get("image") or "").strip(),
                }
    return hotels, kv


def parse_link_line(raw: str) -> tuple[str | None, list[str]]:
    """Возвращает (kind, ids_or_handles). kind: booking | kvartira | special | channel | unknown."""
    line = raw.strip().split("?")[0].strip().replace("т.me/", "t.me/")
    m = re.search(r"abhazbooking/(\d+)", line)
    if m:
        return "booking", [m.group(1)]
    if "abhkvartira" in line:
        nums = re.findall(r"/(\d+)", line.split("?")[0])
        if len(nums) >= 1:
            return "kvartira", nums
        if "t.me/abhkvartira" in line and not nums:
            return "channel", []
    m = re.search(r"t\.me/([a-zA-Z0-9_]+)", line)
    if m:
        h = m.group(1).lower()
        if h != "abhazbooking" and h != "abhkvartira":
            return "special", [h]
    return "unknown", []


def is_region_line(line: str) -> bool:
    s = line.strip()
    if not s or len(s) < 2:
        return False
    if s.startswith("🏖") or s.startswith("👥") or s.startswith("http"):
        return False
    if '"' in s or "«" in s:
        return False
    if "т.me" in s or "t.me" in s:
        return False
    if s.endswith(":") and len(s) < 50:
        return False
    # Регионы в файлах обычно ВЕРХНИМ РЕГИСТРОМ
    letters = [c for c in s if c.isalpha()]
    if not letters:
        return False
    return s == s.upper()


def parse_podborka_text(text: str) -> tuple[str, list[dict]]:
    lines = text.splitlines()
    title = (lines[0].strip() if lines else "") or "Подборка"
    current_region: str | None = None
    items: list[dict] = []
    i = 1
    n = len(lines)
    while i < n:
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            i += 1
            continue
        if stripped.startswith("Наш сайт") or stripped.startswith("Варианты квартир"):
            break
        if stripped.startswith("🏖") or stripped.startswith("👥"):
            i += 1
            continue
        if is_region_line(stripped):
            current_region = stripped
            i += 1
            continue
        if "t.me/" in stripped and not stripped.startswith('"'):
            i += 1
            continue
        if not stripped.startswith('"'):
            i += 1
            continue
        # заголовок объекта (в исходниках — в кавычках)
        block_title = stripped
        details: list[str] = []
        i += 1
        while i < n:
            ln = lines[i].strip()
            if not ln:
                i += 1
                continue
            if "t.me/" in ln or "т.me/" in ln:
                kind, ids = parse_link_line(ln.replace("т.me/", "t.me/"))
                items.append(
                    {
                        "region": current_region,
                        "title": block_title,
                        "details": details,
                        "link_kind": kind,
                        "link_ids": ids,
                        "link_raw": ln,
                    }
                )
                i += 1
                break
            if is_region_line(ln) or (ln.startswith('"') and block_title != ln):
                break
            details.append(ln)
            i += 1
        else:
            continue
    return title, items


def resolve_item_href(
    item: dict,
    hotels: dict[int, dict],
    kv: dict[int, dict],
) -> tuple[str | None, str | None]:
    kind = item["link_kind"]
    ids = item["link_ids"]
    if kind == "booking" and ids:
        hid = int(ids[0])
        hid = BOOKING_MESSAGE_ID_ALIASES.get(hid, hid)
        if hid in hotels:
            h = hotels[hid]
            return f"/hotels/{h['slug']}/", h.get("title")
    if kind == "kvartira" and ids:
        for sid in reversed(ids):
            mid = int(sid)
            mid = KVARTIRA_MESSAGE_ID_ALIASES.get(mid, mid)
            if mid in kv:
                k = kv[mid]
                return k["url"].rstrip("/") + "/", k.get("title")
    if kind == "special" and ids:
        handle = ids[0].lower()
        slug = SPECIAL_BOOKING_SLUGS.get(handle)
        if slug:
            return f"/hotels/{slug}/", None
    return None, None


def item_card_cover(href: str | None, kv: dict[int, dict]) -> str:
    """Public card cover URL for generated podborki pages."""
    if not href:
        return ""
    h = href.strip().rstrip("/")
    parts = h.split("/")
    if len(parts) < 3 or parts[0] != "":
        return ""
    kind, slug = parts[1], parts[2]
    if kind == "hotels":
        return f"{YANDEX_MEDIA_BASE}/cards/{slug}.jpg"
    if kind == "kvartira":
        for row in kv.values():
            if row.get("slug") == slug:
                img = (row.get("image") or "").strip()
                if img.startswith("https://storage.yandexcloud.net/"):
                    return img
                if img.startswith("/media/"):
                    return YANDEX_MEDIA_BASE + img.removeprefix("/media")
                if img.startswith("http://") or img.startswith("https://"):
                    return img
                break
        return f"{YANDEX_MEDIA_BASE}/kvartira-cards/{slug}-cover.jpg"
    return ""


def render_item_catalog_card(
    rank: int,
    href: str | None,
    title: str,
    details: list[str],
    kv: dict[int, dict],
) -> str:
    cover = item_card_cover(href, kv)
    details_html = "<br />".join(esc(d) for d in details if d)
    badge = (
        f'<span class="catalog-card__badge catalog-card__badge--rank" '
        f'aria-label="Место в подборке — {rank}">{rank}</span>'
    )
    if cover:
        media = (
            f'<div class="catalog-card__media-wrap">{badge}'
            f'<img src="{esc(cover)}" alt="{esc(title)}" loading="lazy" decoding="async" />'
            f"</div>"
        )
    else:
        media = (
            f'<div class="catalog-card__media-wrap">{badge}'
            f'<div class="catalog-card__media-fallback" role="img" aria-hidden="true">Фото</div>'
            f"</div>"
        )
    inner = f"{media}<h3>{esc(title)}</h3><p>{details_html}</p>"
    if href:
        return f'          <a class="catalog-card podborki-catalog-card" href="{esc(href)}">{inner}</a>'
    return f'          <div class="catalog-card podborki-catalog-card catalog-card--no-link">{inner}</div>'


def esc(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def display_title(raw: str) -> str:
    return raw.rstrip().rstrip(":").rstrip("—").strip() or "Подборка"


def render_page(slug: str, page_title: str, items: list[dict], hotels, kv) -> str:
    title_clean = TITLE_OVERRIDES.get(slug, display_title(page_title))
    hotel_catalog = load_hotel_catalog()
    kv_catalog = load_kvartira_catalog()
    sections: list[str] = []
    by_region: dict[str | None, list[dict]] = {}
    for it in items:
        by_region.setdefault(it["region"], []).append(it)

    order_keys = list(by_region.keys())
    rank = 0
    blocks: list[str] = []
    for reg in order_keys:
        chunk: list[str] = []
        if reg:
            chunk.append(f'        <h2 class="podborki-region">{esc(reg)}</h2>')
        chunk.append('        <div class="catalog-grid podborki-catalog-grid">')
        for it in by_region[reg]:
            rank += 1
            href, _canonical_title = resolve_item_href(it, hotels, kv)
            if not href:
                href = guess_podborki_href_from_title(it["title"], hotel_catalog, kv_catalog)
            title = it["title"]
            chunk.append(render_item_catalog_card(rank, href, title, it["details"], kv))
        chunk.append("        </div>")
        blocks.append("\n".join(chunk))

    body_blocks = "\n".join(blocks)
    return f"""<!DOCTYPE html>
<html lang="ru" id="top">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{esc(title_clean)} — подборка | АБХАЗБЕРЕГ</title>
  <meta name="description" content="{esc(title_clean)}: подборка проверенных вариантов размещения в Абхазии." />
  <meta name="robots" content="index, follow" />
  <link rel="canonical" href="https://абхазберег.рф/podborki/{esc(slug)}/" />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link rel="preconnect" href="https://storage.yandexcloud.net" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;700;800&family=Prata&display=swap" rel="stylesheet" />
  <link rel="icon" type="image/png" href="{YANDEX_MEDIA_BASE}/branding/favicon-abhazbereg.png" />
  <link rel="stylesheet" href="../../styles.css?v={ASSET_VERSION}" />
</head>
<body>
  <div class="grain" aria-hidden="true"></div>
  <main class="page-shell site-concept podborki-page">
    <div class="bg-blur bg-blur--mint" aria-hidden="true"></div>
    <div class="bg-blur bg-blur--sand" aria-hidden="true"></div>

    <header class="site-concept__topbar" role="banner">
      <a class="site-concept__brand" href="/">
        <img class="site-concept__brand-mark" src="{YANDEX_MEDIA_BASE}/branding/logo-emblem.png" width="80" height="80" alt="АБХАЗБЕРЕГ — на главную" decoding="async" />
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
      <h1>{esc(title_clean)}</h1>
      
    </section>

    <section class="site-concept__section-block podborki-body" aria-label="Список объектов">
{body_blocks}
    </section>
  </main>
  <script src="../../image-lite.js?v={ASSET_VERSION}" defer></script>
  <script src="../../scripts.js?v={ASSET_VERSION}" defer></script>
  <a class="back-to-top" href="#top" aria-label="Наверх"><span class="back-to-top__icon" aria-hidden="true">↑</span></a>
</body>
</html>
"""


def find_source_files() -> list[Path]:
    out: list[Path] = []
    if not PODBORKI_ROOT.is_dir():
        return out
    for p in sorted(PODBORKI_ROOT.rglob("подборка_*.txt")):
        name = unicodedata.normalize("NFC", p.name)
        if "_сайт" in name or "_макс_канал" in name or "_вк_пост" in name:
            continue
        out.append(p)
    return out


def main() -> None:
    hotels, kv = load_maps()
    files = find_source_files()
    if not files:
        print("Нет файлов подборок в", PODBORKI_ROOT)
        return

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    index_entries: list[tuple[str, str]] = []
    slug_count: dict[str, int] = {}

    for path in files:
        text = path.read_text(encoding="utf-8")
        page_title, items = parse_podborka_text(text)
        base_slug = file_to_slug(path)
        n = slug_count.get(base_slug, 0)
        slug_count[base_slug] = n + 1
        slug = f"{base_slug}-{n}" if n else base_slug

        html = render_page(slug, page_title, items, hotels, kv)
        dest = OUT_DIR / slug / "index.html"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(html, encoding="utf-8")
        index_entries.append((slug, TITLE_OVERRIDES.get(slug, display_title(page_title))))
        print("OK", slug, len(items), "объектов")

    # index
    links = "\n".join(
        f'        <li><a class="podborki-index__link" href="/podborki/{esc(s)}/">{esc(t)}</a></li>'
        for s, t in sorted(index_entries, key=lambda x: x[1].lower())
    )
    index_html = f"""<!DOCTYPE html>
<html lang="ru" id="top">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Подборки жилья в Абхазии — АБХАЗБЕРЕГ</title>
  <meta name="description" content="Тематические подборки отелей, домов и квартир в Абхазии: море, бюджет, удобства, локации." />
  <link rel="canonical" href="https://абхазберег.рф/podborki/" />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link rel="preconnect" href="https://storage.yandexcloud.net" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;700;800&family=Prata&display=swap" rel="stylesheet" />
  <link rel="icon" type="image/png" href="{YANDEX_MEDIA_BASE}/branding/favicon-abhazbereg.png" />
  <link rel="stylesheet" href="../styles.css?v={ASSET_VERSION}" />
</head>
<body>
  <div class="grain" aria-hidden="true"></div>
  <main class="page-shell site-concept podborki-page">
    <div class="bg-blur bg-blur--mint" aria-hidden="true"></div>
    <div class="bg-blur bg-blur--sand" aria-hidden="true"></div>
    <header class="site-concept__topbar" role="banner">
      <a class="site-concept__brand" href="/">
        <img class="site-concept__brand-mark" src="{YANDEX_MEDIA_BASE}/branding/logo-emblem.png" width="80" height="80" alt="АБХАЗБЕРЕГ — на главную" decoding="async" />
        <span class="site-concept__brand-copy"><strong>АБХАЗБЕРЕГ - жилье напрямую</strong></span>
      </a>
      <nav class="site-concept__topnav" aria-label="Основная навигация">
        <a href="/">Главная</a>
        <a href="/podborki/" aria-current="page">Подборки</a>
        <a href="/kvartira/">Квартиры и дома</a>
        <a href="/blog/">Полезно узнать</a>
        <a href="/#contacts">Контакты</a>
      </nav>
    </header>
    <section class="site-concept__section-block podborki-index-panel">
      <div class="podborki-index-head">
        <h1>Подборки жилья</h1>
        <p class="podborki-index-head__lead">Выберите подборку под свой формат отдыха</p>
      </div>
      <ul class="podborki-index-list">
{links}
      </ul>
    </section>
  </main>
  <script src="../image-lite.js?v={ASSET_VERSION}" defer></script>
  <script src="../scripts.js?v={ASSET_VERSION}" defer></script>
  <a class="back-to-top" href="#top" aria-label="Наверх"><span class="back-to-top__icon" aria-hidden="true">↑</span></a>
</body>
</html>
"""
    (OUT_DIR / "index.html").write_text(index_html, encoding="utf-8")
    print("Записано страниц:", len(index_entries), "+ индекс")
    patch_sitemap(index_entries)


def patch_sitemap(index_entries: list[tuple[str, str]]) -> None:
    path = REPO / "sitemap.xml"
    text = path.read_text(encoding="utf-8")
    if "абхазберег.рф/podborki/" in text:
        return
    urls = ["https://абхазберег.рф/podborki/"]
    urls += [
        f"https://абхазберег.рф/podborki/{s}/"
        for s, _ in sorted(index_entries, key=lambda x: x[0])
    ]
    frag = "".join(f"<ns0:url><ns0:loc>{u}</ns0:loc></ns0:url>" for u in urls)
    text = text.replace("</ns0:urlset>", frag + "</ns0:urlset>")
    path.write_text(text, encoding="utf-8")
    print("Обновлён sitemap.xml (подборки)")


if __name__ == "__main__":
    main()
