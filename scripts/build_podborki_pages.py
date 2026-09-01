#!/usr/bin/env python3
"""
Генерация страниц podborki/*.html из текстовых источников podbori_txt/*.txt
и метаданных podbori_txt/_collection_meta.json.

Боевой генератор — build_podborki_from_filters.py; этот скрипт —
ручной импорт/экспорт txt, в автопайплайне не используется.

Команды:
  python3 scripts/build_podborki_pages.py export-html
      — из текущих podborki/*/index.html создаёт источники в podbori_txt/

  python3 scripts/build_podborki_pages.py build
      — пересобирает все podborki/*/index.html из podbori_txt/

  python3 scripts/build_podborki_pages.py import-podbori /path/to/ПОДБОРКИ
      — копирует подборка_*_сайт.txt из папок подборок в podbori_txt/{slug}.txt
        (удобно запускать локально, где доступен каталог Documents)

Вёрстка и классы совместимы с существующими страницами подборок.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
PODBORKI_DIR = REPO / "podborki"
PODBORI_TXT = REPO / "podbori_txt"
META_JSON = PODBORI_TXT / "_collection_meta.json"
INDEX_HTML = REPO / "index.html"
KVARTIRA_INDEX = REPO / "kvartira" / "index.html"
ASSET_VERSION_PATH = REPO / "data" / "asset-version.txt"
YANDEX_MEDIA_BASE = "https://media.xn--80aacbklan7f0b.xn--p1ai/media"
# Публичный URL раздела подборок (канон: кирилический .рф)
CANONICAL_ORIGIN = "https://абхазберег.рф"

# Подпись в источниках ≠ официальное имя в каталоге (ключи после simp()).
HEADLINE_QP_ALIASES: dict[str, str] = {
    "БЗЫБЬ": "ГРАСС ОТЕЛЬ",
    "ЧЕРНОМОРСКАЯ-1": "ЧЕРНОМОРСКАЯ-2",
    "МАНСАРДА": "СЕКРЕТ ГАРДЕН",
}

# Имя папки подборки (Documents/ПОДБОРКИ/...) → slug страницы на сайте
FOLDER_TO_SLUG: dict[str, str] = {}
for k, v in {
    "алахадзы все варианты": "alahadzy-vse-varianty",
    "балконы": "balkony",
    "бассейн все варианты": "basseyn-vse-varianty",
    "берег моря. отели на берегу": "bereg-morya-oteli-na-beregu",
    "варианты 5-12 тр, средняк": "varianty-5-12-tr-srednyak",
    "варианты до 5 тр, эконом": "varianty-do-5-tr-ekonom",
    "варианты дороже 12 тр, премиум": "varianty-dorozhe-12-tr-premium",
    "веранда": "veranda",
    "вид на море": "vid-na-more-pryamoy-bokovoy",
    "гагра все варианты": "gagra-vse-varianty",
    "горы - отели в горах": "gory-oteli-v-gorah",
    "гудаута все варианты": "gudauta-vse-varianty",
    "двухкомнатные и более": "dvuhkomnatnye-i-bolee",
    "дома под ключ все варианты": "doma-pod-klyuch-vse-varianty",
    "домики все варианты": "domiki-vse-varianty",
    "квартиры все варианты": "kvartiry-vse-varianty",
    "лдзаа все варианты": "ldzaa-vse-varianty",
    "новый афон все варианты": "novyy-afon-vse-varianty",
    "песчаный пляж сухум": "peschanyy-plyazh-suhum",
    "песчаный пляж лдзаа": "peschanyy-ldzaa",
    "питание и свое кафе": "pitanie-v-otele-ili-svoe-kafe",
    "пицунда все варианты": "pitsunda-vse-varianty",
    "пятеро гостей и более": "pyatero-gostey-i-bolee",
    "своя кухня в номере": "svoya-kuhnya-v-nomere",
    "собаки варианты": "sobaki-varianty",
    "сосновый пляж лдзаа и пицунда": "sosnovyy-plyazh",
    "сухум все варианты": "suhum-vse-varianty",
}.items():
    FOLDER_TO_SLUG[unicodedata.normalize("NFC", k.casefold())] = v


def asset_version() -> str:
    return ASSET_VERSION_PATH.read_text(encoding="utf-8").strip()


def simp(s: str) -> str:
    s = unicodedata.normalize("NFC", s).upper().replace("Ё", "Е")
    s = re.sub(r'[«»""]', "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def quoted_part_title(title: str) -> str:
    tit = html.unescape(title.replace("&quot;", '"'))
    m = re.search(r"«([^»]+)»", tit)
    if m:
        return simp(m.group(1))
    m = re.search(r'"([^"]+)"', tit)
    if m:
        return simp(m.group(1))
    return simp(re.sub(r"<[^>]+>", "", tit))


def augment_resolver_from_detail_pages(by_qp: dict[str, list[dict[str, Any]]]) -> None:
    """Карточки со страниц объекта, если их нет в главном каталоге /kvartira/."""
    seen: set[tuple[str, str]] = {(r["kind"], r["slug"]) for rows in by_qp.values() for r in rows}

    def add_row(row: dict[str, Any]) -> None:
        key = (row["kind"], row["slug"])
        if key in seen:
            return
        seen.add(key)
        by_qp.setdefault(row["qp"], []).append(row)

    for root, kind, prefix in (
        (REPO / "hotels", "hotels", "/hotels/"),
        (REPO / "kvartira", "kvartira", "/kvartira/"),
    ):
        if not root.is_dir():
            continue
        for sub in root.iterdir():
            if not sub.is_dir():
                continue
            slug = sub.name
            ip = sub / "index.html"
            if not ip.is_file():
                continue
            raw = ip.read_text(encoding="utf-8")
            mt = re.search(
                r'<meta[^>]+property="og:title"[^>]+content="([^"]*)"',
                raw,
                re.I,
            )
            if not mt:
                mt = re.search(r"<title>([^<]+)</title>", raw, re.I)
            if not mt:
                continue
            tit = html.unescape(mt.group(1).strip()).replace("&quot;", '"')
            tit_short = tit.split("—")[0].strip()
            qp = quoted_part_title(tit_short)
            if not qp or len(qp) < 2:
                continue
            add_row(
                {
                    "slug": slug,
                    "kind": kind,
                    "href": f"{prefix}{slug}/",
                    "h3": tit_short,
                    "alt": tit_short,
                    "qp": qp,
                    "img_remote": "",
                }
            )


def collect_candidates(key: str, by_qp: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    key = HEADLINE_QP_ALIASES.get(key, key)
    if key in by_qp:
        return list(by_qp[key])
    acc: dict[tuple[str, str], dict[str, Any]] = {}
    for k, rows in by_qp.items():
        if k.startswith(key + " ") or k.startswith(key + "-"):
            for r in rows:
                acc[(r["kind"], r["slug"])] = r
        elif key.startswith(k + " ") or key.startswith(k + "-"):
            for r in rows:
                acc[(r["kind"], r["slug"])] = r
    return list(acc.values())


def strip_tags(t: str) -> str:
    return re.sub(r"<[^>]+>", "", t)


def parse_catalog_index(text: str, prefix: str, pattern: str) -> list[dict[str, Any]]:
    """prefix: /hotels/ или /kvartira/; pattern: hotels|kvartira для путей картинок."""
    out: list[dict[str, Any]] = []
    rx = re.compile(
        rf'<a class="catalog-card"[^>]*href="{re.escape(prefix)}([^/]+)/"[^>]*>(.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )
    for m in rx.finditer(text):
        slug = m.group(1)
        body = m.group(2)
        im = re.search(r'<img[^>]+src="([^"]*)"[^>]*alt="([^"]*)"', body, re.I)
        h3m = re.search(r"<h3>(.*?)</h3>", body, re.I | re.DOTALL)
        src = html.unescape(im.group(1)) if im else ""
        alt = html.unescape(im.group(2)) if im else ""
        h3_raw = html.unescape(strip_tags(h3m.group(1))) if h3m else alt
        qp = quoted_part_title(h3_raw)
        out.append(
            {
                "slug": slug,
                "kind": pattern,
                "href": f"{prefix}{slug}/",
                "h3": h3_raw.strip(),
                "alt": alt.strip() or h3_raw.strip(),
                "qp": qp,
                "img_remote": src,
            }
        )
    return out


def load_catalog_resolver() -> dict[str, list[dict[str, Any]]]:
    by_qp: dict[str, list[dict[str, Any]]] = {}
    catalog_txt = INDEX_HTML.read_text(encoding="utf-8")
    for row in parse_catalog_index(catalog_txt, "/hotels/", "hotels"):
        by_qp.setdefault(row["qp"], []).append(row)
    for row in parse_catalog_index(catalog_txt, "/kvartira/", "kvartira"):
        by_qp.setdefault(row["qp"], []).append(row)
    augment_resolver_from_detail_pages(by_qp)
    return by_qp


def pick_catalog_row(headline_line: str, by_qp: dict[str, list[dict[str, Any]]]) -> dict[str, Any] | None:
    """Подбирает карточку каталога по первой строке объекта в подборке."""
    m = re.search(r'[«"\u201c\u201e\u2018„]\s*([^»"\u201d]{2,}?)\s*[»"\u201d]', headline_line)
    if not m:
        return None
    key = simp(m.group(1))
    cands = collect_candidates(key, by_qp)
    if not cands:
        return None
    if len(cands) == 1:
        return cands[0]
    hl = simp(headline_line)
    best = cands[0]
    best_score = -1
    for c in cands:
        t = simp(c["h3"])
        score = sum(1 for w in hl.split() if len(w) > 2 and w in t)
        if score > best_score:
            best_score = score
            best = c
    return best


def local_card_image(row: dict[str, Any]) -> str:
    slug = row["slug"]
    kind = row["kind"]
    remote = str(row.get("img_remote") or "").strip()
    if remote.startswith("https://storage.yandexcloud.net/"):
        return remote
    if remote.startswith("/media/"):
        return YANDEX_MEDIA_BASE + remote.removeprefix("/media")
    if remote.startswith("http://") or remote.startswith("https://"):
        return remote
    if kind == "hotels":
        return f"{YANDEX_MEDIA_BASE}/cards/{slug}.jpg"
    return f"{YANDEX_MEDIA_BASE}/kvartira-cards/{slug}-cover.jpg"


def is_hotel_headline_line(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    if s[0] not in "«\"“„\u201c\u201e\u2018":
        return False
    m = re.search(r'[«"\u201c\u201e\u2018„]\s*([^»"\u201d]{2,}?)\s*[»"\u201d]', s)
    if m and simp(m.group(1)) == "ЛЮКС":
        return False
    return True


def is_region_line(line: str) -> bool:
    s = line.strip()
    if not s or len(s) > 55:
        return False
    if s.startswith(("#", "«", '"', "🏖", "👥", "http", "clck")):
        return False
    if "Наш сайт:" in s:
        return False
    lo = sum(1 for c in s if "а" <= c <= "я" or c == "ё")
    if lo:
        return False
    up = sum(1 for c in s if "А" <= c <= "Я" or c == "Ё")
    return up >= 2


def extract_podborki_cards(segment: str) -> list[str]:
    chunks: list[str] = []
    pos = 0
    while True:
        m = re.search(r'<a class="catalog-card podborki-catalog-card"[^>]*>', segment[pos:])
        if not m:
            break
        start = pos + m.start()
        end_a = segment.find("</a>", start)
        if end_a == -1:
            break
        chunks.append(segment[start : end_a + 4])
        pos = end_a + 4
    return chunks


def card_to_txt_lines(card_html: str) -> list[str]:
    h3m = re.search(r"<h3>(.*?)</h3>", card_html, re.I | re.DOTALL)
    pm = re.search(r"<p>(.*?)</p>", card_html, re.I | re.DOTALL)
    h3 = html.unescape(strip_tags(h3m.group(1))).strip() if h3m else ""
    p_html = pm.group(1) if pm else ""
    parts = [
        html.unescape(strip_tags(x)).strip()
        for x in re.split(r"<br\s*/?>", p_html, flags=re.I)
    ]
    lines = [h3]
    lines.extend(p for p in parts if p)
    lines.append("")
    return lines


def parse_podbori_txt(raw: str) -> list[tuple[str, list[tuple[str, list[str]]]]]:
    """
    Возвращает [(region, [(headline_line, detail_lines]), ...], ...]
    """
    lines = raw.replace("\r\n", "\n").split("\n")
    regions: list[tuple[str, list[tuple[str, list[str]]]]] = []
    current_region = "БЕЗ РЕГИОНА"
    current_entries: list[tuple[str, list[str]]] = []
    i = 0

    def flush_region() -> None:
        nonlocal current_region, current_entries
        if current_entries:
            regions.append((current_region, current_entries))
        current_entries = []

    while i < len(lines):
        line = lines[i]
        if line.strip().startswith("#"):
            i += 1
            continue
        if not line.strip():
            i += 1
            continue
        if is_region_line(line):
            flush_region()
            current_region = line.strip()
            i += 1
            continue
        if is_hotel_headline_line(line):
            headline = line.strip()
            details: list[str] = []
            i += 1
            while i < len(lines):
                ln = lines[i]
                if not ln.strip():
                    break
                if is_region_line(ln):
                    break
                if is_hotel_headline_line(ln):
                    break
                sl = ln.strip()
                if sl.startswith("clck.ru") or sl.startswith("http"):
                    i += 1
                    continue
                if sl.startswith("👥"):
                    i += 1
                    continue
                details.append(sl)
                i += 1
            current_entries.append((headline, details))
            continue
        i += 1

    flush_region()
    return regions


def export_html_to_txt() -> None:
    PODBORI_TXT.mkdir(parents=True, exist_ok=True)
    meta: dict[str, Any] = {}
    for sub in sorted(PODBORKI_DIR.iterdir()):
        if not sub.is_dir():
            continue
        slug = sub.name
        html_path = sub / "index.html"
        if not html_path.is_file():
            continue
        raw = html_path.read_text(encoding="utf-8")
        tm = re.search(r"<title>([^<]+)</title>", raw, re.I)
        dm = re.search(r'<meta name="description" content="([^"]*)"', raw, re.I)
        h1m = re.search(r"<h1>([^<]+)</h1>", raw, re.I)
        meta[slug] = {
            "page_title": html.unescape(tm.group(1).strip()) if tm else f"{slug} — подборка",
            "meta_description": html.unescape(dm.group(1).strip()) if dm else "",
            "h1": html.unescape(h1m.group(1).strip()) if h1m else slug,
        }
        body_m = re.search(
            r'<section class="site-concept__section-block podborki-body"[^>]*>(.*?)</section>',
            raw,
            re.I | re.DOTALL,
        )
        if not body_m:
            continue
        body = body_m.group(1)
        lines_out: list[str] = []

        if not re.search(r'class="podborki-region"', body):
            lines_out.append("БЕЗ РЕГИОНА")
            lines_out.append("")
            for card in extract_podborki_cards(body):
                lines_out.extend(card_to_txt_lines(card))
            out_path = PODBORI_TXT / f"{slug}.txt"
            out_path.write_text("\n".join(lines_out).strip() + "\n", encoding="utf-8")
            print("export txt:", out_path.relative_to(REPO))
            continue

        pos = 0
        while True:
            h2m = re.search(
                r'<h2 class="podborki-region">\s*([^<]+?)\s*</h2>',
                body[pos:],
            )
            if not h2m:
                break
            region = html.unescape(strip_tags(h2m.group(1))).strip()
            seg_start = pos + h2m.end()
            next_h2 = re.search(r'<h2 class="podborki-region">', body[seg_start:])
            seg_end = seg_start + next_h2.start() if next_h2 else len(body)
            segment = body[seg_start:seg_end]
            pos = seg_end

            lines_out.append(region)
            lines_out.append("")
            for card in extract_podborki_cards(segment):
                lines_out.extend(card_to_txt_lines(card))
            lines_out.append("")

        out_path = PODBORI_TXT / f"{slug}.txt"
        out_path.write_text("\n".join(lines_out).strip() + "\n", encoding="utf-8")
        print("export txt:", out_path.relative_to(REPO))

    META_JSON.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print("meta:", META_JSON.relative_to(REPO))


def render_collection_page(
    slug: str,
    regions: list[tuple[str, list[tuple[str, list[str]]]]],
    meta: dict[str, Any],
    by_qp: dict[str, list[dict[str, Any]]],
    version: str,
) -> str:
    m = meta.get(slug, {})
    page_title = m.get("page_title") or f"{slug} — подборка | АБХАЗБЕРЕГ"
    description = m.get("meta_description") or ""
    h1 = m.get("h1") or strip_tags(page_title.split("|")[0]).strip()

    parts_body: list[str] = []
    rank = 0
    unresolved: list[str] = []

    for region, entries in regions:
        if not entries:
            continue
        if region != "БЕЗ РЕГИОНА":
            parts_body.append(f'        <h2 class="podborki-region">{html.escape(region)}</h2>')
        parts_body.append('        <div class="catalog-grid podborki-catalog-grid">')

        for headline, details in entries:
            row = pick_catalog_row(headline, by_qp)
            if not row:
                unresolved.append(headline)
                continue
            rank += 1
            href = row["href"]
            h3_final = html.escape(row["h3"])
            alt = html.escape(row.get("alt") or row["h3"])
            img_src = html.escape(local_card_image(row))
            p_inner = "<br />".join(html.escape(d) for d in details if d.strip())
            if not p_inner:
                p_inner = " "
            parts_body.append(
                f'          <a class="catalog-card podborki-catalog-card" href="{html.escape(href)}">'
                f'<div class="catalog-card__media-wrap">'
                f'<span class="catalog-card__badge catalog-card__badge--rank" aria-label="Место в подборке — {rank}">{rank}</span>'
                f'<img src="{img_src}" alt="{alt}" loading="lazy" decoding="async" />'
                f"</div><h3>{h3_final}</h3><p>{p_inner}</p></a>"
            )

        parts_body.append("        </div>")

    if unresolved:
        print(f"  [{slug}] не сопоставлено с каталогом ({len(unresolved)}):", file=sys.stderr)
        for u in unresolved[:12]:
            print(f"    - {u[:80]}", file=sys.stderr)
        if len(unresolved) > 12:
            print("    ...", file=sys.stderr)

    body_html = "\n".join(parts_body)

    return f"""<!DOCTYPE html>
<html lang="ru" id="top">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{html.escape(page_title)}</title>
  <meta name="description" content="{html.escape(description)}" />
  <meta name="robots" content="index, follow" />
  <link rel="canonical" href="{CANONICAL_ORIGIN}/podborki/{slug}/" />
  <link rel="preconnect" href="https://media.xn--80aacbklan7f0b.xn--p1ai" />
  <link rel="preconnect" href="https://media.xn--80aacbklan7f0b.xn--p1ai" crossorigin />
  <link rel="icon" type="image/png" href="{YANDEX_MEDIA_BASE}/branding/favicon-48.png" />
  <link rel="stylesheet" href="../../styles.min.css?v={version}" />
</head>
<body>
  <div class="grain" aria-hidden="true"></div>
  <main class="page-shell site-concept podborki-page">
    <div class="bg-blur bg-blur--mint" aria-hidden="true"></div>
    <div class="bg-blur bg-blur--sand" aria-hidden="true"></div>

    <header class="site-concept__topbar" role="banner">
      <a class="site-concept__brand" href="/">
        <img class="site-concept__brand-mark" src="{YANDEX_MEDIA_BASE}/branding/logo-emblem-160.png" width="80" height="80" alt="АБХАЗБЕРЕГ — на главную" decoding="async" />
        <span class="site-concept__brand-copy">
          <strong>АБХАЗБЕРЕГ - жилье напрямую</strong>
        </span>
      </a>
      <nav class="site-concept__topnav" aria-label="Основная навигация">
        <a href="/">Главная</a>
        <a href="/podborki/">Подборки</a>
        <a href="/blog/">Полезно узнать</a>
        <a href="/#contacts">Контакты</a>
      </nav>
    </header>

    <section class="site-concept__hero-card podborki-hero">
      <p class="site-concept__eyebrow"><a href="/podborki/">Подборки</a></p>
      <h1>{html.escape(h1)}</h1>

    </section>

    <section class="site-concept__section-block podborki-body" aria-label="Список объектов">
{body_html}
    </section>
  </main>
  <script src="../../scripts.min.js?v={version}" defer></script>
  <a class="back-to-top" href="#top" aria-label="Наверх"><span class="back-to-top__icon" aria-hidden="true">↑</span></a>
</body>
</html>
"""


def build_pages() -> None:
    if not META_JSON.is_file():
        print("Нет", META_JSON, "— сначала запустите export-html", file=sys.stderr)
        sys.exit(1)
    meta = json.loads(META_JSON.read_text(encoding="utf-8"))
    version = asset_version()
    by_qp = load_catalog_resolver()
    for sub in sorted(PODBORKI_DIR.iterdir()):
        if not sub.is_dir():
            continue
        slug = sub.name
        txt_path = PODBORI_TXT / f"{slug}.txt"
        if not txt_path.is_file():
            print("пропуск (нет txt):", slug, file=sys.stderr)
            continue
        regions = parse_podbori_txt(txt_path.read_text(encoding="utf-8"))
        page = render_collection_page(slug, regions, meta, by_qp, version)
        out = sub / "index.html"
        out.write_text(page, encoding="utf-8")
        print("build:", out.relative_to(REPO))


def import_podbori(root: Path) -> None:
    PODBORI_TXT.mkdir(parents=True, exist_ok=True)
    copied = 0
    for p in root.rglob("*.txt"):
        if "telegram_export" in str(p):
            continue
        name_raw = p.name
        nfc_name = unicodedata.normalize("NFC", name_raw)
        cf = nfc_name.casefold()
        if "_вк_" in cf or "_макс_" in cf:
            continue
        if "_сайт" not in nfc_name and "_site" not in cf:
            continue
        parent = unicodedata.normalize("NFC", p.parent.name.casefold())
        slug = FOLDER_TO_SLUG.get(parent)
        if not slug:
            print("пропуск папки (нет маппинга):", p.parent.name, file=sys.stderr)
            continue
        dest = PODBORI_TXT / f"{slug}.txt"
        dest.write_bytes(p.read_bytes())
        copied += 1
        print("import:", dest.relative_to(REPO), "<-", p)
    print("импортировано файлов:", copied)


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("export-html")
    sub.add_parser("build")
    ip = sub.add_parser("import-podbori")
    ip.add_argument("root", type=Path)

    args = ap.parse_args()
    if args.cmd == "export-html":
        export_html_to_txt()
    elif args.cmd == "build":
        build_pages()
    elif args.cmd == "import-podbori":
        if not args.root.is_dir():
            print("Не каталог:", args.root, file=sys.stderr)
            return 1
        import_podbori(args.root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
