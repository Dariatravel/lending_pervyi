#!/usr/bin/env python3
"""Сверка блока ЦЕНЫ на страницах объектов с постами Telegram (Telethon + parse_post)."""
from __future__ import annotations

import asyncio
import html as html_module
import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup
from telethon import TelegramClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from sync_abhazbooking_2026 import parse_post  # noqa: E402
from sync_catalog_from_telegram import API_HASH, API_ID, SESSION  # noqa: E402


async def collect_group_media(client: TelegramClient, entity: Any, canonical: Any) -> list[Any]:
    if getattr(canonical, "grouped_id", None):
        grouped_id = canonical.grouped_id
        left = max(1, int(canonical.id) - 80)
        right = int(canonical.id) + 80
        nearby = await client.get_messages(entity, ids=list(range(left, right + 1)))
        media = [
            item
            for item in (nearby or [])
            if item and getattr(item, "grouped_id", None) == grouped_id and getattr(item, "media", None)
        ]
        media.sort(key=lambda item: item.id)
        if media:
            return media
    if getattr(canonical, "media", None):
        return [canonical]
    return []

CURRENT_PAGES = ROOT / "output" / "current_pages.json"
KV_CARDS = ROOT / "kvartira_cards.json"
HOTELS_DIR = ROOT / "hotels"
KVARTIRA_DIR = ROOT / "kvartira"
ENV_FILE = ROOT / ".env.supabase.local"
OUT_REPORT = ROOT / "output" / "telegram_prices_audit.txt"
KV_PRICES_AUDIT = ROOT / "output" / "telegram_kv_prices_audit.txt"


def load_supabase_kv_message_ids() -> dict[str, int]:
    """slug → source_message_id из Supabase для квартир."""
    if not ENV_FILE.is_file():
        return {}
    env: dict[str, str] = {}
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip()
    base = env.get("SUPABASE_URL", "").rstrip("/")
    key = env.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not base or not key:
        return {}
    import urllib.request

    url = base + "/rest/v1/listings?select=slug,source_message_id&source_kind=eq.kvartira&limit=200"
    req = urllib.request.Request(
        url,
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        rows = json.loads(resp.read().decode("utf-8"))
    out: dict[str, int] = {}
    for row in rows:
        slug = str(row.get("slug") or "").strip()
        mid = row.get("source_message_id")
        if slug and mid:
            out[slug] = int(mid)
    return out


def resolve_kv_message_id(html_text: str, slug: str, fallback: int, supabase_ids: dict[str, int]) -> int:
    msg_id = resolve_kv_source_id(html_text, 0)
    if msg_id:
        return msg_id
    if slug in supabase_ids:
        return supabase_ids[slug]
    m = re.search(r"-(\d+)/?$", slug)
    if m:
        return int(m.group(1))
    return fallback


def load_hotel_jobs() -> list[tuple[str, Path, int]]:
    jobs: list[tuple[str, Path, int]] = []
    if HOTELS_DIR.is_dir():
        for path in sorted(HOTELS_DIR.glob("*/index.html")):
            slug = path.parent.name
            sid = 0
            m = re.search(r"-(\d+)/?$", slug)
            if m:
                sid = int(m.group(1))
            jobs.append((slug, path, sid))
        return jobs
    data = json.loads(CURRENT_PAGES.read_text(encoding="utf-8"))
    for item in data:
        slug = item["slug"]
        jobs.append((slug, ROOT / "hotels" / slug / "index.html", int(item["source_id"])))
    return jobs


def load_kv_jobs(*, catalog_only: bool = True) -> list[tuple[str, Path, int]]:
    cards = json.loads(KV_CARDS.read_text(encoding="utf-8")) if KV_CARDS.is_file() else []
    by_slug = {str(c.get("slug") or ""): int(c.get("message_id") or 0) for c in cards}
    supabase_ids = load_supabase_kv_message_ids()
    jobs: list[tuple[str, Path, int]] = []
    for path in sorted(KVARTIRA_DIR.glob("*/index.html")):
        slug = path.parent.name
        if catalog_only and supabase_ids and slug not in supabase_ids:
            continue
        jobs.append((slug, path, by_slug.get(slug, 0)))
    return jobs


def normalize_price_line(text: str) -> str:
    s = html_module.unescape(text or "")
    s = re.sub(r"<[^>]+>", " ", s)
    s = unicodedata.normalize("NFKC", s).replace("\xa0", " ")
    s = re.sub(r"\s+", " ", s).strip().lower()
    s = s.replace("руб./", "₽/").replace("руб.", "₽").replace("руб", "₽")
    s = s.replace("–", "-").replace("—", "-")
    s = re.sub(r"(\d)\s+го\b", r"\1го", s)
    s = re.sub(r"\+ (\d+)", r"+\1", s)
    s = re.sub(r"(\d)\s+р\b", r"\1р", s)
    s = re.sub(r"июль\s*/\s*", "июль/", s)
    s = re.sub(r"\s*,\s*", ", ", s)
    s = re.sub(r",\s*$", "", s)
    s = re.sub(r"(\d)\s+₽", r"\1₽", s)
    s = re.sub(r"(\d)\s+/", r"\1/", s)
    s = re.sub(r"/\s+сутки", "/сутки", s)
    s = re.sub(r"\s+%", "%", s)
    s = re.sub(r"\(\s+", "(", s)
    s = re.sub(r"\s+\)", ")", s)
    s = re.sub(r"\s*-\s*", " - ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def telegram_prices(raw_text: str) -> tuple[list[str], list[str]]:
    parsed = parse_post(raw_text or "")
    prices: list[str] = []
    notes: list[str] = []
    for item in parsed.get("prices") or []:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind") or "price")
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        if kind == "note":
            notes.append(normalize_price_line(text))
        elif kind == "price":
            prices.append(normalize_price_line(text))
    return prices, notes


def site_prices(html_text: str) -> tuple[list[str], list[str], bool]:
    soup = BeautifulSoup(html_text, "html.parser")
    card = soup.select_one(".price-card")
    if not card:
        return [], [], False
    prices = [
        normalize_price_line(li.get_text(" ", strip=True))
        for li in card.select(".price-card__seasons li")
        if li.get_text(strip=True)
    ]
    notes = [
        normalize_price_line(li.get_text(" ", strip=True))
        for li in card.select(".price-card__notes li")
        if li.get_text(strip=True)
    ]
    return prices, notes, True


def resolve_hotel_source_id(html_text: str, fallback: int) -> int:
    for pattern in (
        r'data-telegram-post="abhazbooking/(\d+)"',
        r"<!--\s*source:\s*https://t\.me/abhazbooking/(\d+)\s*-->",
        r"https://t\.me/abhazbooking/(\d+)",
    ):
        m = re.search(pattern, html_text)
        if m:
            return int(m.group(1))
    return fallback


def resolve_kv_source_id(html_text: str, fallback: int) -> int:
    for pattern in (
        r'data-telegram-post="abhkvartira/(\d+)"',
        r"<!--\s*source:\s*https://t\.me/abhkvartira/(\d+)\s*-->",
        r"https://t\.me/abhkvartira/(\d+)",
    ):
        m = re.search(pattern, html_text)
        if m:
            return int(m.group(1))
    return fallback


@dataclass
class Row:
    kind: str
    slug: str
    channel: str
    message_id: int
    status: str
    tg_prices: int
    site_prices: int
    missing_on_site: list[str]
    extra_on_site: list[str]
    note_mismatch: bool
    error: str | None = None


def chunked(items: list[int], size: int) -> list[list[int]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


async def fetch_post_texts_batch(
    client: TelegramClient, channel: str, message_ids: list[int]
) -> dict[int, str]:
    entity = await client.get_entity(channel)
    out: dict[int, str] = {}
    unique = sorted({int(x) for x in message_ids if x})
    for batch in chunked(unique, 100):
        messages = await client.get_messages(entity, ids=batch)
        for message in messages or []:
            if not message:
                continue
            text = message.message or ""
            if not text.strip() and getattr(message, "grouped_id", None):
                media_messages = await collect_group_media(client, entity, message)
                for item in media_messages:
                    if (item.message or "").strip():
                        text = item.message or ""
                        break
            out[int(message.id)] = text
    return out


def compare_lists(tg: list[str], site: list[str]) -> tuple[list[str], list[str]]:
    tg_set = set(tg)
    site_set = set(site)
    missing = [x for x in tg if x not in site_set]
    extra = [x for x in site if x not in tg_set]
    return missing, extra


async def audit_all(rows: list[Row], *, kv_only: bool = False) -> None:
    supabase_kv_ids = load_supabase_kv_message_ids()

    hotel_jobs: list[tuple[str, int, Path]] = []
    if not kv_only:
        for slug, path, sid in load_hotel_jobs():
            if not path.is_file():
                rows.append(Row("hotel", slug, "abhazbooking", sid, "MISSING_FILE", 0, 0, [], [], False, str(path)))
                continue
            html_text = path.read_text(encoding="utf-8")
            msg_id = resolve_hotel_source_id(html_text, sid)
            hotel_jobs.append((slug, msg_id, path))

    kv_jobs: list[tuple[str, int, Path]] = []
    for slug, path, sid in load_kv_jobs():
        if not path.is_file():
            rows.append(Row("kvartira", slug, "abhkvartira", sid, "MISSING_FILE", 0, 0, [], [], False, str(path)))
            continue
        html_text = path.read_text(encoding="utf-8")
        msg_id = resolve_kv_message_id(html_text, slug, sid, supabase_kv_ids)
        kv_jobs.append((slug, msg_id, path))

    client = TelegramClient(SESSION, API_ID, API_HASH, receive_updates=False)
    await client.connect()

    try:
        if not kv_only:
            hotel_texts = await fetch_post_texts_batch(client, "abhazbooking", [j[1] for j in hotel_jobs])
            print(f"Загружено постов отелей: {len(hotel_texts)}", flush=True)
            for slug, msg_id, path in hotel_jobs:
                raw = hotel_texts.get(msg_id, "")
                if not raw:
                    rows.append(
                        Row("hotel", slug, "abhazbooking", msg_id, "FETCH_FAIL", 0, 0, [], [], False, "empty message")
                    )
                    continue
                html_text = path.read_text(encoding="utf-8")
                tg_p, tg_n = telegram_prices(raw)
                st_p, st_n, has_block = site_prices(html_text)
                if not tg_p and not tg_n:
                    rows.append(Row("hotel", slug, "abhazbooking", msg_id, "NO_TG_PRICES", 0, len(st_p), [], [], False))
                    continue
                if not has_block:
                    rows.append(
                        Row(
                            "hotel",
                            slug,
                            "abhazbooking",
                            msg_id,
                            "NO_SITE_PRICES",
                            len(tg_p),
                            0,
                            tg_p[:12],
                            [],
                            bool(tg_n),
                        )
                    )
                    continue
                missing, extra = compare_lists(tg_p, st_p)
                note_mismatch = tg_n != st_n
                status = "OK" if not missing and not extra and not note_mismatch else "MISMATCH"
                rows.append(
                    Row(
                        "hotel",
                        slug,
                        "abhazbooking",
                        msg_id,
                        status,
                        len(tg_p),
                        len(st_p),
                        missing[:12],
                        extra[:12],
                        note_mismatch,
                    )
                )

        kv_texts = await fetch_post_texts_batch(client, "abhkvartira", [j[1] for j in kv_jobs if j[1] > 0])
        print(f"Загружено постов квартир: {len(kv_texts)}", flush=True)
        for slug, msg_id, path in kv_jobs:
            if not msg_id:
                rows.append(
                    Row(
                        "kvartira",
                        slug,
                        "abhkvartira",
                        0,
                        "FETCH_FAIL",
                        0,
                        0,
                        [],
                        [],
                        False,
                        "no message_id",
                    )
                )
                continue
            raw = kv_texts.get(msg_id, "")
            if not raw:
                rows.append(
                    Row("kvartira", slug, "abhkvartira", msg_id, "FETCH_FAIL", 0, 0, [], [], False, "empty message")
                )
                continue
            html_text = path.read_text(encoding="utf-8")
            tg_p, tg_n = telegram_prices(raw)
            st_p, st_n, has_block = site_prices(html_text)
            if not tg_p and not tg_n:
                rows.append(Row("kvartira", slug, "abhkvartira", msg_id, "NO_TG_PRICES", 0, len(st_p), [], [], False))
                continue
            if not has_block:
                rows.append(
                    Row(
                        "kvartira",
                        slug,
                        "abhkvartira",
                        msg_id,
                        "NO_SITE_PRICES",
                        len(tg_p),
                        0,
                        tg_p[:12],
                        [],
                        bool(tg_n),
                    )
                )
                continue
            missing, extra = compare_lists(tg_p, st_p)
            note_mismatch = tg_n != st_n
            status = "OK" if not missing and not extra and not note_mismatch else "MISMATCH"
            rows.append(
                Row(
                    "kvartira",
                    slug,
                    "abhkvartira",
                    msg_id,
                    status,
                    len(tg_p),
                    len(st_p),
                    missing[:12],
                    extra[:12],
                    note_mismatch,
                )
            )
    finally:
        await client.disconnect()


def write_report(rows: list[Row], path: Path, *, kv_only: bool = False) -> None:
    hotels = [r for r in rows if r.kind == "hotel"]
    kv = [r for r in rows if r.kind == "kvartira"]

    def stats(section: list[Row]) -> dict[str, int]:
        out: dict[str, int] = {}
        for r in section:
            out[r.status] = out.get(r.status, 0) + 1
        return out

    lines: list[str] = [
        "Сверка блока ЦЕНЫ: Telegram (parse_post) ↔ HTML (.price-card__seasons / __notes)",
        "",
    ]
    if kv_only:
        lines.append(f"Квартиры: {stats(kv)}")
        lines.append("")
        sections = (("КВАРТИРЫ", kv),)
    else:
        lines.extend([f"Отели: {stats(hotels)}", f"Квартиры: {stats(kv)}", ""])
        sections = (("ОТЕЛИ", hotels), ("КВАРТИРЫ", kv))

    for title, section in sections:
        lines.append(f"=== {title} ===")
        for r in sorted(section, key=lambda x: (x.status != "MISMATCH", x.slug)):
            if r.status in {"FETCH_FAIL", "MISSING_FILE"}:
                lines.append(f"- {r.slug} (@{r.channel}/{r.message_id}): {r.status} ({r.error})")
                continue
            if r.status in {"NO_TG_PRICES", "NO_SITE_PRICES"}:
                lines.append(
                    f"- {r.slug} (@{r.channel}/{r.message_id}): {r.status} "
                    f"(tg={r.tg_prices}, site={r.site_prices})"
                )
                if r.missing_on_site:
                    for s in r.missing_on_site:
                        lines.append(f"    tg: {s}")
                continue
            lines.append(
                f"- {r.slug} (@{r.channel}/{r.message_id}): {r.status} "
                f"(tg={r.tg_prices}, site={r.site_prices}, notes_diff={r.note_mismatch})"
            )
            for s in r.missing_on_site:
                lines.append(f"    нет на сайте: {s}")
            for s in r.extra_on_site:
                lines.append(f"    лишнее на сайте: {s}")
        lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def main_async() -> int:
    kv_only = "--kv-only" in sys.argv
    rows: list[Row] = []
    await audit_all(rows, kv_only=kv_only)
    report_path = KV_PRICES_AUDIT if kv_only else OUT_REPORT
    write_report(rows, report_path, kv_only=kv_only)
    mism = sum(1 for r in rows if r.status == "MISMATCH")
    print(f"Отчёт: {report_path}")
    print(f"MISMATCH: {mism} из {len(rows)}")
    return 0


def main() -> int:
    return asyncio.run(main_async())


if __name__ == "__main__":
    raise SystemExit(main())
