#!/usr/bin/env python3
"""
Сверка текстов и медиа-блоков карточек на сайте с постами Telegram.

- Текст поста: публичная страница t.me (meta og:description) — без Telethon.
- Текст на сайте: видимый текст в main (карточка + детальные секции) без отзывов и скриптов.
- Медиа на сайте: подсчёт img / video / source в галерее и секциях медиа карточки.
  Полное число вложений в посте Telegram через HTTP недоступно (рендер в JS);
  в отчёте указывается только сторона сайта и пометка об ограничении.

Запуск из корня репозитория:
  python3 scripts/audit_telegram_site_parity.py
"""
from __future__ import annotations

import html as html_module
import json
import re
import unicodedata
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

CURRENT_PAGES = ROOT / "output" / "current_pages.json"
KV_CARDS = ROOT / "kvartira_cards.json"
OUT_REPORT = ROOT / "output" / "telegram_site_parity_audit.txt"

SESSION = requests.Session()
# Только ASCII: иначе requests падает с UnicodeEncodeError при кодировании заголовков.
SESSION.headers.update(
    {"User-Agent": "Mozilla/5.0 (compatible; AbhazberegAudit/1.0; +https://xn--80abcbbhhilbd.xn--p1ai)"}
)

RE_SKIP_LINE = re.compile(
    r"^\s*(#|@|https?://|t\.me/|telegram\.me/)",
    re.I,
)

# Стандартный хвост поста канала — на странице объектов обычно в другом виде / в блоке контактов.
FOOTER_SKIP_SUBSTR = (
    "abhazbooking_online",
    "whatsapp/max",
    "whatsapp",
    "max:",
    "только этот контакт",
    "+7940",
    "по бронированию и наличию",
)

# Удаление эмодзи для мягкого сравнения (🏖 vs 🏖️, ✔️ в заголовках).
EMOJI_STRIP_RE = re.compile(
    r"[\U0001F300-\U0001F9FF\u2600-\u26FF\u2700-\u27BF\u2714\u2713\uFE0F]+",
)


def normalize_blob(s: str) -> str:
    s = html_module.unescape(s or "")
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("\xa0", " ")
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s


def telegram_lines_from_og(raw: str) -> list[str]:
    """Строки поста для проверки вхождения в текст страницы."""
    raw = html_module.unescape(raw or "")
    lines = []
    for line in raw.splitlines():
        t = line.strip()
        if not t:
            continue
        if RE_SKIP_LINE.match(t):
            continue
        low = t.lower()
        if any(s in low for s in FOOTER_SKIP_SUBSTR):
            continue
        if len(t) <= 1 and not any(c.isalnum() for c in t):
            continue
        lines.append(t)
    return lines


def fetch_telegram_og_description(channel: str, message_id: int) -> tuple[str | None, str | None]:
    url = f"https://t.me/{channel}/{message_id}"
    try:
        r = SESSION.get(url, timeout=45)
        if r.status_code != 200:
            return None, f"HTTP {r.status_code}"
        soup = BeautifulSoup(r.text, "html.parser")
        meta = soup.select_one('meta[property="og:description"]')
        if not meta or not meta.get("content"):
            return None, "no og:description"
        return meta["content"].strip(), None
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)


def resolve_hotel_source_id(html_text: str, fallback: int) -> int:
    m = re.search(r'data-telegram-post="abhazbooking/(\d+)"', html_text)
    if m:
        return int(m.group(1))
    m = re.search(r"<!--\s*source:\s*https://t\.me/abhazbooking/(\d+)\s*-->", html_text)
    if m:
        return int(m.group(1))
    m = re.search(r"https://t\.me/abhazbooking/(\d+)", html_text)
    if m:
        return int(m.group(1))
    return fallback


def resolve_kv_source_id(html_text: str, fallback: int) -> int:
    m = re.search(r'data-telegram-post="abhkvartira/(\d+)"', html_text)
    if m:
        return int(m.group(1))
    m = re.search(r"<!--\s*source:\s*https://t\.me/abhkvartira/(\d+)\s*-->", html_text)
    if m:
        return int(m.group(1))
    m = re.search(r"https://t\.me/abhkvartira/(\d+)", html_text)
    if m:
        return int(m.group(1))
    return fallback


def extract_site_main_text(html_text: str) -> str:
    """Весь основной контент страницы объекта: карточка + детальные секции (номера, цены и т.д.)."""
    soup = BeautifulSoup(html_text, "html.parser")
    root = soup.select_one("main.hotel-site-concept") or soup.select_one("main")
    if not root:
        return ""
    for sel in (
        ".reviews-panel",
        "script",
        "style",
        ".hotel-card__footer",
        ".telegram-embed",
    ):
        for tag in root.select(sel):
            tag.decompose()
    return root.get_text("\n", strip=True)


def count_site_media(html_text: str) -> tuple[int, int, list[str]]:
    """Считает img, video и уникальные URL медиа на странице объекта (main)."""
    soup = BeautifulSoup(html_text, "html.parser")
    art = soup.select_one("main") or soup
    imgs = art.find_all("img")
    videos = art.find_all("video")
    sources = art.find_all("source")
    urls: list[str] = []
    for tag in imgs + videos + sources:
        src = tag.get("src") or tag.get("data-src")
        if src:
            urls.append(src)
    for v in videos:
        for s in v.find_all("source"):
            if s.get("src"):
                urls.append(s["src"])
    unique_urls = []
    seen = set()
    for u in urls:
        if u not in seen:
            seen.add(u)
            unique_urls.append(u)
    return len(imgs), len(videos), unique_urls


def _strip_emojis(s: str) -> str:
    s = EMOJI_STRIP_RE.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip().lower()


def line_found_on_site(tg_line: str, site_blob: str) -> bool:
    n_line = normalize_blob(tg_line)
    n_site = normalize_blob(site_blob)
    if len(n_line) < 6:
        return n_line in n_site or _strip_emojis(tg_line) in _strip_emojis(site_blob)
    if n_line in n_site:
        return True
    # Разные варианты эмодзи в строке «пляж» и в заголовках ✔️НОМЕРА
    if _strip_emojis(tg_line) and _strip_emojis(tg_line) in _strip_emojis(site_blob):
        return True
    # типичные отличия: пробелы у «₽», дефисы в ценах
    relaxed = re.sub(r"[\s\u200b]", "", n_line)
    relaxed_site = re.sub(r"[\s\u200b]", "", n_site)
    return relaxed in relaxed_site


@dataclass
class Row:
    kind: str
    slug: str
    channel: str
    message_id: int
    status: str
    missing: int
    total_lines: int
    samples: list[str]
    media_note: str
    error: str | None = None


def audit_hotels(rows: list[Row]) -> None:
    data = json.loads(CURRENT_PAGES.read_text(encoding="utf-8"))
    for item in data:
        slug = item["slug"]
        sid = int(item["source_id"])
        path = ROOT / "hotels" / slug / "index.html"
        if not path.exists():
            rows.append(
                Row(
                    "hotel",
                    slug,
                    "abhazbooking",
                    sid,
                    "MISSING_FILE",
                    0,
                    0,
                    [],
                    "",
                    str(path),
                )
            )
            continue
        html_text = path.read_text(encoding="utf-8")
        msg_id = resolve_hotel_source_id(html_text, sid)
        og, err = fetch_telegram_og_description("abhazbooking", msg_id)
        time.sleep(0.25)
        if err:
            rows.append(
                Row(
                    "hotel",
                    slug,
                    "abhazbooking",
                    msg_id,
                    "FETCH_FAIL",
                    0,
                    0,
                    [],
                    "",
                    err,
                )
            )
            continue
        lines = telegram_lines_from_og(og or "")
        site_text = extract_site_main_text(html_text)
        missing_list = [ln for ln in lines if not line_found_on_site(ln, site_text)]
        img_n, vid_n, urls = count_site_media(html_text)
        ext_media = sum(1 for u in urls if u.startswith("http"))
        media_note = (
            f"сайт: img={img_n}, video={vid_n}, абсолютных URL медиа={ext_media}; "
            "Telegram: число вложений по HTTP не извлекается"
        )
        st = "OK" if not missing_list else "MISMATCH"
        samples = missing_list[:8]
        rows.append(
            Row(
                "hotel",
                slug,
                "abhazbooking",
                msg_id,
                st,
                len(missing_list),
                len(lines),
                samples,
                media_note,
            )
        )


def audit_kvartira(rows: list[Row]) -> None:
    data = json.loads(KV_CARDS.read_text(encoding="utf-8"))
    for item in data:
        slug = item.get("slug") or ""
        mid = int(item.get("message_id") or 0)
        path = ROOT / "kvartira" / slug / "index.html"
        if not path.exists():
            rows.append(
                Row(
                    "kvartira",
                    slug,
                    "abhkvartira",
                    mid,
                    "MISSING_FILE",
                    0,
                    0,
                    [],
                    "",
                    str(path),
                )
            )
            continue
        html_text = path.read_text(encoding="utf-8")
        msg_id = resolve_kv_source_id(html_text, mid)
        og, err = fetch_telegram_og_description("abhkvartira", msg_id)
        time.sleep(0.25)
        if err:
            rows.append(
                Row(
                    "kvartira",
                    slug,
                    "abhkvartira",
                    msg_id,
                    "FETCH_FAIL",
                    0,
                    0,
                    [],
                    "",
                    err,
                )
            )
            continue
        lines = telegram_lines_from_og(og or "")
        site_text = extract_site_main_text(html_text)
        missing_list = [ln for ln in lines if not line_found_on_site(ln, site_text)]
        img_n, vid_n, urls = count_site_media(html_text)
        ext_media = sum(1 for u in urls if u.startswith("http"))
        media_note = (
            f"сайт: img={img_n}, video={vid_n}, абсолютных URL медиа={ext_media}; "
            "Telegram: число вложений по HTTP не извлекается"
        )
        st = "OK" if not missing_list else "MISMATCH"
        samples = missing_list[:8]
        rows.append(
            Row(
                "kvartira",
                slug,
                "abhkvartira",
                msg_id,
                st,
                len(missing_list),
                len(lines),
                samples,
                media_note,
            )
        )


def write_report(rows: Iterable[Row], path: Path) -> None:
    lines_out: list[str] = []
    rows = list(rows)
    hotels = [r for r in rows if r.kind == "hotel"]
    kv = [r for r in rows if r.kind == "kvartira"]

    def summarize(section: list[Row]) -> tuple[int, int, int, int]:
        ok = sum(1 for r in section if r.status == "OK")
        bad = sum(1 for r in section if r.status == "MISMATCH")
        ff = sum(1 for r in section if r.status == "FETCH_FAIL")
        mf = sum(1 for r in section if r.status == "MISSING_FILE")
        return ok, bad, ff, mf

    h_ok, h_bad, h_ff, h_mf = summarize(hotels)
    k_ok, k_bad, k_ff, k_mf = summarize(kv)

    lines_out.append("Сверка карточек сайта с постами Telegram (HTTP og:description ↔ текст в HTML)")
    lines_out.append("")
    lines_out.append(
        "Метод: строки из описания поста Telegram (кроме служебных и типового футера бронирования) "
        "проверяются на вхождение в видимый текст страницы объекта (main без отзывов), "
        "с учётом различий в эмодзи."
    )
    lines_out.append(
        "Медиа: на сайте считаются img/video/source в карточке; количество файлов в посте Telegram "
        "по статической разметке недоступно — нужен Telegram API (Telethon)."
    )
    lines_out.append("")
    lines_out.append(f"Отели: OK={h_ok}, расхождения текста={h_bad}, ошибка загрузки TG={h_ff}, нет файла={h_mf}")
    lines_out.append(f"Квартиры: OK={k_ok}, расхождения текста={k_bad}, ошибка загрузки TG={k_ff}, нет файла={k_mf}")
    lines_out.append("")

    lines_out.append("=== ОТЕЛИ ===")
    for r in sorted(hotels, key=lambda x: (x.status != "OK", x.slug)):
        if r.status == "FETCH_FAIL":
            lines_out.append(
                f"- {r.slug} (@{r.channel}/{r.message_id}): {r.status} ({r.error})"
            )
            continue
        if r.status == "MISSING_FILE":
            lines_out.append(f"- {r.slug}: файл страницы не найден ({r.error})")
            continue
        lines_out.append(
            f"- {r.slug} (@{r.channel}/{r.message_id}): {r.status}, "
            f"нет на сайте строк {r.missing}/{r.total_lines} из текста поста"
        )
        lines_out.append(f"  {r.media_note}")
        for s in r.samples:
            lines_out.append(f"    * {s[:220]}{'…' if len(s) > 220 else ''}")

    lines_out.append("")
    lines_out.append("=== КВАРТИРЫ ===")
    for r in sorted(kv, key=lambda x: (x.status != "OK", x.slug)):
        if r.status == "FETCH_FAIL":
            lines_out.append(
                f"- {r.slug} (@{r.channel}/{r.message_id}): {r.status} ({r.error})"
            )
            continue
        if r.status == "MISSING_FILE":
            lines_out.append(f"- {r.slug}: файл страницы не найден ({r.error})")
            continue
        lines_out.append(
            f"- {r.slug} (@{r.channel}/{r.message_id}): {r.status}, "
            f"нет на сайте строк {r.missing}/{r.total_lines} из текста поста"
        )
        lines_out.append(f"  {r.media_note}")
        for s in r.samples:
            lines_out.append(f"    * {s[:220]}{'…' if len(s) > 220 else ''}")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines_out) + "\n", encoding="utf-8")


def main() -> int:
    rows: list[Row] = []
    audit_hotels(rows)
    audit_kvartira(rows)
    write_report(rows, OUT_REPORT)
    print(f"Отчёт записан: {OUT_REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
