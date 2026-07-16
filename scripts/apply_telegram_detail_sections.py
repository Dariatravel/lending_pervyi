#!/usr/bin/env python3
"""
Перенос текста из поста Telegram в детальные блоки HTML (отели / квартиры).

Политика (см. .cursor/rules/telegram-content-sync.mdc):
- Не трогает шапку карточки, benefit-grid, блок «Фото и видео», FAQ, контакты.
- Не трогает первый абзац под галереей без заголовка (дубликат лида).
- Обновляет секции с заголовками ✔️… и блок ЦЕНЫ (без <strong> в пунктах).
- Не переносит футер поста (контакты, @abhazbooking_online, предупреждения).

Использование:
  python3 scripts/apply_telegram_detail_sections.py hotels/pegas-otel-na-pervoy-linii-vid-na-more-2574
  python3 scripts/apply_telegram_detail_sections.py --from-audit --dry-run
  python3 scripts/apply_telegram_detail_sections.py --from-audit
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
SKIP_FILE = ROOT / "tools" / "skip_new_objects.json"
AUDIT_FILE = ROOT / "output" / "telegram_site_parity_audit.txt"

SESSION = requests.Session()
SESSION.headers["User-Agent"] = "Mozilla/5.0 (compatible; AbhazberegSync/1.0)"

HEADER_RE = re.compile(r"^\s*✔️?\s*(.+?):\s*$")

# Строка про цены живёт в статическом блоке «✔️ВАЖНО:» (data-static-important),
# который рендерит sync_catalog_from_telegram. Из переносимых текстов постов
# её вырезаем, а сам блок «ВАЖНО» не трогаем.
def strip_commission_line(paras: list[str]) -> list[str]:
    return [p for p in paras if "точь" not in p.lower()]

FOOTER_LINE = re.compile(
    r"abhazbooking_online|whatsapp|telegram\.me|t\.me/|\+7|\+7940|только этот контакт|"
    r"будьте внимательны|по бронированию и наличию|я на связи",
    re.I,
)


def load_skip() -> set[str]:
    if not SKIP_FILE.exists():
        return set()
    return set(json.loads(SKIP_FILE.read_text(encoding="utf-8")))


def normalize_section_key(name: str) -> str:
    s = name.strip().upper()
    s = s.replace("Ё", "Е")
    return s


def fetch_og_description(channel: str, message_id: int) -> str | None:
    url = f"https://t.me/{channel}/{message_id}"
    r = SESSION.get(url, timeout=45)
    if r.status_code != 200:
        return None
    soup = BeautifulSoup(r.text, "html.parser")
    meta = soup.select_one('meta[property="og:description"]')
    if not meta or not meta.get("content"):
        return None
    return html.unescape(meta["content"]).strip()


def parse_sections(raw: str) -> dict[str, str]:
    """Разбивает текст поста по строкам-заголовкам ✔️КЛЮЧ: значение — до следующего заголовка или футера."""
    lines = raw.splitlines()
    sections: dict[str, str] = {}
    current: str | None = None
    buf: list[str] = []

    for line in lines:
        stripped = line.strip()
        m = HEADER_RE.match(stripped)
        if m:
            if current is not None:
                sections[current] = "\n".join(buf).strip()
            current = normalize_section_key(m.group(1))
            buf = []
            continue
        if current is not None:
            if current == "УСЛОВИЯ" and stripped and FOOTER_LINE.search(stripped):
                sections[current] = "\n".join(buf).strip()
                current = None
                buf = []
                break
            buf.append(line)
    if current is not None:
        sections[current] = "\n".join(buf).strip()
    return sections


def paragraphs_from_block(text: str) -> list[str]:
    if not text.strip():
        return []
    parts = re.split(r"\n\s*\n", text.strip())
    return [p.strip() for p in parts if p.strip()]


def price_lines_from_block(text: str) -> list[str]:
    out: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        if FOOTER_LINE.search(s):
            break
        out.append(s)
    return out


def heading_matches_canonical(h2_text: str, canonical: str) -> bool:
    h = normalize_section_key(re.sub(r"^✔️?\s*", "", h2_text.replace(":", "").strip()))
    return h == canonical or h.startswith(canonical + " ")


def resolve_message_id(html_text: str, channel: str, fallback: int) -> int:
    if channel == "abhazbooking":
        m = re.search(r'data-telegram-post="abhazbooking/(\d+)"', html_text)
        if m:
            return int(m.group(1))
        m = re.search(r"<!--\s*source:\s*https://t\.me/abhazbooking/(\d+)\s*-->", html_text)
        if m:
            return int(m.group(1))
        m = re.search(r"https://t\.me/abhazbooking/(\d+)", html_text)
        if m:
            return int(m.group(1))
    else:
        m = re.search(r'data-telegram-post="abhkvartira/(\d+)"', html_text)
        if m:
            return int(m.group(1))
        m = re.search(r"https://t\.me/abhkvartira/(\d+)", html_text)
        if m:
            return int(m.group(1))
    return fallback


def apply_to_page(path: Path, channel: str, message_id: int, dry_run: bool) -> tuple[bool, str]:
    html_text = path.read_text(encoding="utf-8")
    raw = fetch_og_description(channel, message_id)
    if not raw:
        return False, "no telegram text"

    sections = parse_sections(raw)
    if not sections:
        return False, "no sections parsed"

    soup = BeautifulSoup(html_text, "html.parser")
    main = soup.select_one("main.hotel-site-concept") or soup.select_one("main")
    if not main:
        return False, "no main"

    detail_main = main.select_one(".hotel-site-concept__detail-main")
    if not detail_main:
        return False, "no detail-main"

    updated = False

    # Секции с h2 в основной колонке (кроме «Фото и видео»)
    for sec in detail_main.select("section.hotel-site-concept__detail-section"):
        art = sec.select_one("article.card")
        if not art or art.get("data-static-important"):
            continue
        h2 = art.find("h2")
        if not h2:
            continue
        title = h2.get_text(strip=True)
        if "фото и видео" in title.lower():
            continue

        canon = None
        for key in sections:
            if heading_matches_canonical(title, key):
                canon = key
                break
        if not canon:
            continue

        if canon == "ЦЕНЫ":
            continue

        block = art.select_one(".paragraph-blocks")
        if not block:
            continue

        body = sections.get(canon, "")
        paras = paragraphs_from_block(body)
        if not paras:
            continue
        paras = strip_commission_line(paras)
        if not paras:
            continue

        for tag in block.find_all(True):
            tag.decompose()
        for para in paras:
            p = soup.new_tag("p")
            p.string = para
            block.append(p)
        updated = True

    # УСЛОВИЯ: вставить секцию, если есть в TG и нет в разметке
    if "УСЛОВИЯ" in sections and sections["УСЛОВИЯ"].strip():
        has_uslov = False
        for sec in detail_main.select("section.hotel-site-concept__detail-section"):
            h2 = sec.select_one("h2")
            if h2 and heading_matches_canonical(h2.get_text(strip=True), "УСЛОВИЯ"):
                has_uslov = True
                break
        if not has_uslov:
            paras = paragraphs_from_block(sections["УСЛОВИЯ"])
            paras = [p for p in paras if not FOOTER_LINE.search(p)]
            paras = strip_commission_line(paras)
            if paras:
                new_sec = soup.new_tag(
                    "section", attrs={"class": "section hotel-site-concept__detail-section"}
                )
                art = soup.new_tag("article", attrs={"class": "card"})
                h2t = soup.new_tag("h2")
                h2t.string = "✔️УСЛОВИЯ:"
                pb = soup.new_tag("div", attrs={"class": "paragraph-blocks"})
                art.append(h2t)
                art.append(pb)
                new_sec.append(art)
                for para in paras:
                    p = soup.new_tag("p")
                    p.string = para
                    pb.append(p)
                detail_main.append(new_sec)
                updated = True

    # Цены в aside
    price_ul = soup.select_one("ul.price-card__seasons")
    if price_ul and "ЦЕНЫ" in sections:
        lines = price_lines_from_block(sections["ЦЕНЫ"])
        if lines:
            price_ul.clear()
            for line in lines:
                li = soup.new_tag("li")
                li.string = line
                price_ul.append(li)
            updated = True

    if not updated:
        return False, "nothing to update"

    if dry_run:
        return True, "dry-run OK"

    path.write_text(str(soup), encoding="utf-8")
    return True, "written"


def parse_audit_mismatch() -> list[tuple[str, str, int]]:
    """Возвращает [(kind_slug_path, channel, msg_id), ...] из строк '- slug (@chan/id): MISMATCH'."""
    if not AUDIT_FILE.exists():
        return []
    rows: list[tuple[str, str, int]] = []
    text = AUDIT_FILE.read_text(encoding="utf-8")
    for line in text.splitlines():
        if "MISMATCH" not in line or line.strip().startswith("*"):
            continue
        m = re.match(r"-\s+([^\s]+)\s+\(@?(abhazbooking|abhkvartira)/(\d+)\)", line)
        if not m:
            continue
        slug = m.group(1)
        channel = m.group(2)
        mid = int(m.group(3))
        kind = "hotels" if channel == "abhazbooking" else "kvartira"
        rows.append((f"{kind}/{slug}", channel, mid))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("page", nargs="?", help="Папка объекта, напр. hotels/slug или kvartira/slug")
    ap.add_argument("--from-audit", action="store_true", help="Все MISMATCH из telegram_site_parity_audit.txt")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    skip = load_skip()
    tasks: list[tuple[Path, str, int]] = []

    if args.from_audit:
        for rel, ch, mid in parse_audit_mismatch():
            slug = rel.split("/", 1)[1]
            if slug in skip:
                print(f"skip (new): {rel}", file=sys.stderr)
                continue
            tasks.append((ROOT / rel / "index.html", ch, mid))
    elif args.page:
        parts = args.page.strip("/").split("/")
        if len(parts) != 2:
            print("Укажите путь вида hotels/slug или kvartira/slug", file=sys.stderr)
            return 2
        kind, slug = parts
        if slug in skip:
            print("Объект в списке новых — пропуск.", file=sys.stderr)
            return 0
        path = ROOT / kind / slug / "index.html"
        ch = "abhazbooking" if kind == "hotels" else "abhkvartira"
        data = json.loads((ROOT / "output" / "current_pages.json").read_text(encoding="utf-8")) if kind == "hotels" else None
        mid = 0
        if kind == "hotels":
            for row in data or []:
                if row.get("slug") == slug:
                    mid = int(row["source_id"])
                    break
        else:
            for row in json.loads((ROOT / "kvartira_cards.json").read_text(encoding="utf-8")):
                if row.get("slug") == slug:
                    mid = int(row.get("message_id") or 0)
                    break
        html_text = path.read_text(encoding="utf-8")
        mid = resolve_message_id(html_text, ch, mid)
        tasks.append((path, ch, mid))
    else:
        ap.print_help()
        return 2

    ok = 0
    fail = 0
    for path, ch, mid in tasks:
        time.sleep(0.22)
        if not path.exists():
            print(f"missing {path}", file=sys.stderr)
            fail += 1
            continue
        html_text = path.read_text(encoding="utf-8")
        rid = resolve_message_id(html_text, ch, mid)
        success, msg = apply_to_page(path, ch, rid, args.dry_run)
        rel = path.relative_to(ROOT)
        if success:
            print(f"OK {rel} — {msg}")
            ok += 1
        else:
            print(f"SKIP {rel} — {msg}", file=sys.stderr)
            fail += 1

    print(f"\nГотово: ok={ok}, skip/fail={fail}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
