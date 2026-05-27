#!/usr/bin/env python3
"""Обновить блок ЦЕНЫ на страницах из постов Telegram (Telethon + render_prices_html)."""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup
from telethon import TelegramClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from audit_telegram_site_prices import (  # noqa: E402
    OUT_REPORT,
    Row,
    audit_all,
    compare_lists,
    fetch_post_texts_batch,
    load_hotel_jobs,
    load_kv_jobs,
    resolve_hotel_source_id,
    resolve_kv_source_id,
    site_prices,
    telegram_prices,
    write_report,
)
from sync_catalog_from_telegram import (  # noqa: E402
    API_HASH,
    API_ID,
    ENV_FILE,
    SESSION,
    SupabaseClient,
    render_prices_html,
)

SYNC_REPORT = ROOT / "output" / "telegram_prices_sync_report.txt"


def load_env(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.exists():
        return data
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip()
    return data


def replace_prices_block(html_text: str, prices_html: str) -> str | None:
    if not prices_html.strip():
        return None
    soup = BeautifulSoup(html_text, "html.parser")
    section = soup.select_one("section.hotel-price-section")
    new_soup = BeautifulSoup(prices_html, "html.parser")
    new_section = new_soup.select_one("section.hotel-price-section")
    if not new_section:
        return None
    if section:
        section.replace_with(new_section)
    else:
        main = soup.select_one("main.hotel-site-concept") or soup.select_one("main")
        if not main:
            return None
        main.append(new_section)
    return str(soup)


async def sync_prices(dry_run: bool = False) -> int:
    rows: list[Row] = []
    await audit_all(rows)
    write_report(rows, OUT_REPORT)

    to_fix = [
        r
        for r in rows
        if r.status in {"MISMATCH", "NO_SITE_PRICES"}
        and r.message_id > 0
        and r.channel in {"abhazbooking", "abhkvartira"}
    ]

    env = load_env(ENV_FILE)
    supa = SupabaseClient(
        url=env.get("SUPABASE_URL", "").rstrip("/"),
        service_key=env.get("SUPABASE_SERVICE_ROLE_KEY", ""),
    )
    listings = {f'{r.get("source_kind")}:{r.get("slug")}': r for r in supa.fetch_listings()}

    hotel_map = {
        resolve_hotel_source_id(path.read_text(encoding="utf-8"), sid): (slug, path)
        for slug, path, sid in load_hotel_jobs()
        if path.is_file()
    }
    kv_map = {}
    for slug, path, sid in load_kv_jobs():
        if path.is_file():
            html_text = path.read_text(encoding="utf-8")
            kv_map[resolve_kv_source_id(html_text, sid)] = (slug, path)

    client = TelegramClient(SESSION, API_ID, API_HASH, receive_updates=False)
    await client.connect()

    hotel_ids = sorted({r.message_id for r in to_fix if r.kind == "hotel"})
    kv_ids = sorted({r.message_id for r in to_fix if r.kind == "kvartira"})
    hotel_texts = await fetch_post_texts_batch(client, "abhazbooking", hotel_ids)
    kv_texts = await fetch_post_texts_batch(client, "abhkvartira", kv_ids)
    await client.disconnect()

    updated: list[str] = []
    skipped: list[str] = []
    failed: list[str] = []

    for row in to_fix:
        raw = hotel_texts.get(row.message_id, "") if row.kind == "hotel" else kv_texts.get(row.message_id, "")
        if not raw:
            failed.append(f'{row.slug}: empty telegram text')
            continue
        from sync_abhazbooking_2026 import parse_post  # noqa: WPS433

        parsed = parse_post(raw)
        prices = parsed.get("prices") or []
        prices_html = render_prices_html(prices)
        if not prices_html.strip():
            skipped.append(f"{row.slug}: no prices in post")
            continue

        if row.kind == "hotel":
            job = hotel_map.get(row.message_id)
            kind = "hotel"
        else:
            job = kv_map.get(row.message_id)
            kind = "kvartira"
        if not job:
            failed.append(f"{row.slug}: page not found")
            continue
        slug, path = job
        html_text = path.read_text(encoding="utf-8")
        tg_p, _ = telegram_prices(raw)
        st_p, _, _ = site_prices(html_text)
        missing, extra = compare_lists(tg_p, st_p)
        if not missing and not extra and row.status != "NO_SITE_PRICES":
            skipped.append(f"{row.slug}: already OK after audit")
            continue

        new_html = replace_prices_block(html_text, prices_html)
        if not new_html:
            failed.append(f"{row.slug}: could not patch HTML")
            continue
        if dry_run:
            updated.append(f"{row.slug}: dry-run")
            continue

        path.write_text(new_html, encoding="utf-8")
        listing = listings.get(f"{kind}:{slug}")
        if listing:
            details = dict(listing.get("details") or {})
            details["prices"] = prices
            supa.patch_listing(int(listing["id"]), {"details": details})
        updated.append(row.slug)

    lines = [
        "Синхронизация блока ЦЕНЫ из Telegram",
        "",
        f"Кандидатов: {len(to_fix)}",
        f"Обновлено: {len(updated)}",
        f"Пропущено: {len(skipped)}",
        f"Ошибок: {len(failed)}",
        "",
    ]
    if updated:
        lines.append("Обновлены:")
        lines.extend(f"- {x}" for x in updated)
    if skipped:
        lines.append("")
        lines.append("Пропущены:")
        lines.extend(f"- {x}" for x in skipped[:40])
    if failed:
        lines.append("")
        lines.append("Ошибки:")
        lines.extend(f"- {x}" for x in failed[:40])

    SYNC_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


def main() -> int:
    dry = "--dry-run" in sys.argv
    return asyncio.run(sync_prices(dry_run=dry))


if __name__ == "__main__":
    raise SystemExit(main())
