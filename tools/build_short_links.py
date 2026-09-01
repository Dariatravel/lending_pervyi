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
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "short-links.json"
GENERATED = ROOT / "data" / "short-links-generated.json"
SNAPSHOT = ROOT / "data" / "catalog-snapshot.json"
BLOG_MANIFEST = ROOT / "data" / "blog-posts.json"

STUB = """<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8"/>
<meta http-equiv="refresh" content="0;url={href}"/>
<link rel="canonical" href="https://абхазберег.рф{href}"/>
<meta name="robots" content="noindex"/>
<title>Открываем страницу — АБХАЗБЕРЕГ</title></head>
<body><p>Открываем страницу: <a href="{href}">{href}</a></p></body></html>
"""

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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="только показать, ничего не менять")
    args = parser.parse_args()

    manual = {str(k): str(v) for k, v in (load_json(MANIFEST).get("links") or {}).items()}
    previous = {str(k): str(v) for k, v in (load_json(GENERATED).get("links") or {}).items()}

    links: dict[str, str] = dict(manual)
    # Прошлые сгенерированные ключи сохраняются, пока жива цель, — старые
    # рассылки не ломаются. Ключ не должен конфликтовать с ручными.
    for key, href in previous.items():
        if key not in links and (ROOT / href.strip("/") / "index.html").is_file():
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
    for key, href in sorted(links.items()):
        target = ROOT / href.strip("/") / "index.html"
        if not target.is_file():
            print(f"  ! цель не найдена: /{key} → {href}")
            broken += 1
            continue
        if not args.check:
            out_dir = ROOT / key
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "index.html").write_text(STUB.format(href=href), encoding="utf-8")

    if not args.check:
        GENERATED.write_text(
            json.dumps({"_comment": "Автосгенерированные короткие ссылки (build_short_links.py). Не редактировать руками — ручные живут в short-links.json.", "links": generated},
                       ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(f"\nИтог: ссылок {len(links)} (ручных {len(manual)}, новых {added}), целей не найдено {broken}")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
