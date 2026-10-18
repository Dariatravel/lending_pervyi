#!/usr/bin/env python3
"""Короткие ссылки для рассылок: /pamyatka → /blog/pamyatka-turistu-abkhazia/.

Два источника:
- ручные ссылки в data/short-links.json (всегда главнее);
- автоматика по всему сайту: объекты (имя объекта: /aisha, /sia-lend),
  подборки (суть: /gagra, /basseyn) и статьи блога (слаг без гео-хвоста).

Сгенерированные пары запоминаются в data/short-links-generated.json:
однажды выданный короткий адрес не меняется, пока жива его цель, — ссылки
из старых рассылок не ломаются. Страница-стрелка: мгновенный переезд,
canonical на цель и noindex — поисковую выдачу не трогает.

Запуск: python3 tools/build_short_links.py [--check]
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "short-links.json"
GENERATED = ROOT / "data" / "short-links-generated.json"
SNAPSHOT = ROOT / "data" / "catalog-snapshot.json"
BLOG_MANIFEST = ROOT / "data" / "blog-posts.json"

# Скрипт передаёт цели «?utm_…» и «#…» (без них реклама не видит, откуда
# гость): meta refresh их теряет и остаётся запасным путём без JS.
# og-теги — превью объекта в Telegram и ВК: по переадресации внутри страницы
# они не переходят и иначе показали бы «Открываем страницу» без фото.
STUB = """<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8"/>
<script>location.replace({href_js}+location.search+location.hash)</script>
<meta http-equiv="refresh" content="0;url={href}"/>
<link rel="canonical" href="https://абхазберег.рф{href}"/>
<meta name="robots" content="noindex"/>
<title>{title}</title>
{og}</head>
<body><p>Открываем страницу: <a href="{href}">{href}</a></p></body></html>
"""
STUB_TITLE = "Открываем страницу — АБХАЗБЕРЕГ"


def og_tags(href: str, listing: dict | None) -> tuple[str, str]:
    """(title, og-теги) страницы-стрелки: у объекта — его название, описание и обложка."""
    url = f"https://abhazbereg.com{href}"
    if not listing:
        return STUB_TITLE, f'<meta property="og:url" content="{html.escape(url)}"/>'
    title = str(listing.get("title") or "").strip() or "АБХАЗБЕРЕГ"
    description = str(listing.get("summary") or listing.get("excerpt") or "").strip()[:300]
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        from catalog_snapshot import _cover_for_index

        image = str(_cover_for_index(listing) or "")
    except Exception:  # noqa: BLE001 — без обложки превью всё равно с названием
        image = str(listing.get("cover_url") or "")
    tags = [
        '<meta property="og:type" content="website"/>',
        '<meta property="og:site_name" content="АБХАЗБЕРЕГ"/>',
        f'<meta property="og:title" content="{html.escape(title)}"/>',
        f'<meta property="og:url" content="{html.escape(url)}"/>',
    ]
    if description:
        tags.append(f'<meta property="og:description" content="{html.escape(description)}"/>')
    if image.startswith("https://"):
        tags.append(f'<meta property="og:image" content="{html.escape(image)}"/>')
    return html.escape(f"{title} — АБХАЗБЕРЕГ"), "\n".join(tags)


def listings_by_path() -> dict[str, dict]:
    result: dict[str, dict] = {}
    for row in load_json(SNAPSHOT).get("listings") or []:
        if row.get("is_active") is False or not row.get("slug"):
            continue
        kind = "hotels" if row.get("source_kind") == "hotel" else "kvartira"
        result[f"/{kind}/{row['slug']}/"] = row
    return result

# Типовые слова в слагах объектов: всё после них — описание, а не имя.
TYPE_WORDS = {
    "otel", "otelya", "gostevoy", "gostevoi", "gostinitsa", "gostinica", "baza",
    "domik", "domiki", "dom", "doma", "apartament", "apartamenty", "kvartira",
    "kvartiry", "kottedzh", "kottedzhi", "villa", "villy", "glamping", "glemping",
    "kompleks", "nomera", "studiya", "studio", "mini", "khostel", "hostel",
    "pansionat", "sanatoriy", "ekootel", "etnodvor",
}
TYPE_WORD_RE = re.compile(r"^\d+k$")  # 1k/2k/3k — тип квартиры

# Гео-хвосты слагов блога, без которых ссылка короче и не теряет смысл.
BLOG_TAIL = {
    "abkhazia", "abhazia", "abkhaziya", "abhaziya", "abhazii", "abkhazii",
    "v-abhazii", "abhaziyu", "abkhaziyu", "2026",
}

# Имена, которые нельзя занимать: служебные и существующие разделы сайта.
RESERVED_EXTRA = {"media", "data", "scripts", "tools", "output", "deploy", "ai",
                  "docs", "assets", "img", "images", "videos", "reviews"}


def object_name_part(slug: str) -> str:
    words = slug.split("-")
    if words and re.fullmatch(r"\d+", words[-1]):
        words = words[:-1]  # хвостовой id поста
    name: list[str] = []
    for word in words:
        if word in TYPE_WORDS or TYPE_WORD_RE.fullmatch(word):
            break
        name.append(word)
    return "-".join(name) or "-".join(words)


def blog_short(slug: str) -> str:
    words = slug.split("-")
    while words and words[-1] in BLOG_TAIL:
        words = words[:-1]
    return "-".join(words) or slug


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def auto_candidates() -> list[tuple[str, str]]:
    """(желаемый ключ, целевой путь) в порядке приоритета выдачи ключей."""
    pairs: list[tuple[str, str]] = []
    snapshot = load_json(SNAPSHOT)
    for row in snapshot.get("listings") or []:
        if row.get("is_active") is False:
            continue
        slug = str(row.get("slug") or "")
        kind = "hotels" if row.get("source_kind") == "hotel" else "kvartira"
        if slug and (ROOT / kind / slug / "index.html").is_file():
            pairs.append((object_name_part(slug), f"/{kind}/{slug}/"))
    for path in sorted((ROOT / "podborki").glob("*/index.html")):
        slug = path.parent.name
        pairs.append((slug.removesuffix("-vse-varianty"), f"/podborki/{slug}/"))
    try:
        posts = json.loads(BLOG_MANIFEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        posts = []
    for post in posts if isinstance(posts, list) else []:
        slug = str(post.get("slug") or "")
        if slug and (ROOT / "blog" / slug / "index.html").is_file():
            pairs.append((blog_short(slug), f"/blog/{slug}/"))
    return pairs


def reserved_keys() -> set[str]:
    taken = set(RESERVED_EXTRA)
    for item in ROOT.iterdir():
        if item.is_dir() and not item.name.startswith("."):
            taken.add(item.name)
    return taken


def refresh_catalog_index_short_urls(manual: dict[str, str], generated: dict[str, str]) -> None:
    """Дописывает short_url объектам в data/catalog-index.json: по нему шахматка
    берёт короткую ссылку для постов, Справочника и бота. Сбой не ломает ссылки."""
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        from catalog_snapshot import CATALOG_INDEX_PATH, apply_short_urls, short_key_by_path

        if not CATALOG_INDEX_PATH.is_file():
            return
        payload = json.loads(CATALOG_INDEX_PATH.read_text(encoding="utf-8"))
        items = payload.get("listings") or []
        before = json.dumps(items, ensure_ascii=False)
        found = apply_short_urls(items, short_key_by_path(manual, generated))
        if json.dumps(items, ensure_ascii=False) != before:
            CATALOG_INDEX_PATH.write_text(
                json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n",
                encoding="utf-8",
            )
        print(f"  короткие ссылки в каталоге: {found} из {len(items)}")
    except Exception as error:  # noqa: BLE001
        print(f"  ! каталог не обновлён короткими ссылками: {error}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="только показать, ничего не менять")
    args = parser.parse_args()

    manual = {str(k): str(v) for k, v in (load_json(MANIFEST).get("links") or {}).items()}
    previous = {str(k): str(v) for k, v in (load_json(GENERATED).get("links") or {}).items()}

    links: dict[str, str] = dict(manual)
    # Снятые объекты (is_active=false: скрыты, заменены, отельный двойник):
    # их страница — редирект, и короткая ссылка вела бы в общий каталог
    # («Джаннат», 13.10.2026). Такие сгенерированные ссылки убираем.
    inactive = {
        f"/{'hotels' if row.get('source_kind') == 'hotel' else 'kvartira'}/{row.get('slug')}/"
        for row in (load_json(SNAPSHOT).get("listings") or [])
        if row.get("is_active") is False and row.get("slug")
    }
    retired: list[str] = []
    # Прошлые сгенерированные ключи сохраняются, пока жива цель, — старые
    # рассылки не ломаются. Ключ не должен конфликтовать с ручными.
    for key, href in previous.items():
        if key in links:
            continue
        if href in inactive:
            retired.append(key)
            continue
        if (ROOT / href.strip("/") / "index.html").is_file():
            links[key] = href

    taken = reserved_keys()
    # Свои прежние короткие страницы не считаем занятыми разделами.
    taken -= set(previous) | set(manual)
    taken |= set(links)

    by_target = {href: key for key, href in links.items()}
    added = 0
    for want, href in auto_candidates():
        if href in by_target:
            continue
        want = re.sub(r"[^a-z0-9-]", "", want.lower()).strip("-")
        if not want:
            continue
        # Разрешение коллизий: имя → имя+следующее слово слага → полный слаг.
        slug_words = href.strip("/").split("/")[-1].split("-")
        candidates = [want]
        if len(want.split("-")) < len(slug_words):
            candidates.append("-".join(slug_words[: len(want.split("-")) + 1]))
        candidates.append("-".join(slug_words))
        key = next((c for c in candidates if c and c not in taken), "")
        if not key:
            print(f"  ! не подобрать ключ: {href}")
            continue
        links[key] = href
        by_target[href] = key
        taken.add(key)
        added += 1

    generated = {k: v for k, v in sorted(links.items()) if k not in manual}
    broken = 0
    by_path = listings_by_path()
    for key, href in sorted(links.items()):
        target = ROOT / href.strip("/") / "index.html"
        if not target.is_file():
            print(f"  ! цель не найдена: /{key} → {href}")
            broken += 1
            continue
        if not args.check:
            out_dir = ROOT / key
            out_dir.mkdir(parents=True, exist_ok=True)
            title, og = og_tags(href, by_path.get(href))
            page = STUB.format(href=href, href_js=json.dumps(href), title=title, og=og)
            (out_dir / "index.html").write_text(page, encoding="utf-8")

    for key in retired:
        stub = ROOT / key / "index.html"
        print(f"  - снята ссылка /{key}: объект {previous[key]} снят с сайта")
        # Удаляем только свою страницу-стрелку, чужие папки не трогаем.
        if not args.check and stub.is_file() and "Открываем страницу" in stub.read_text(encoding="utf-8"):
            stub.unlink()
            try:
                stub.parent.rmdir()
            except OSError:
                pass

    if not args.check:
        GENERATED.write_text(
            json.dumps({"_comment": "Автосгенерированные короткие ссылки (build_short_links.py). Не редактировать руками — ручные живут в short-links.json.", "links": generated},
                       ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        refresh_catalog_index_short_urls(manual, generated)
    print(f"\nИтог: ссылок {len(links)} (ручных {len(manual)}, новых {added}), целей не найдено {broken}")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
