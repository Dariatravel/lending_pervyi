"""Скан комментариев Telegram на ссылки виртуальных 3D-туров.

Запускать на раннере GitHub (нужен TG_STRING_SESSION) — с RU-хостингов MTProto
заблокирован. Проходит по активным объектам снапшота, читает комментарии к их
постам и ищет ссылки на туры: явные домены туров (b2brec, kuula, matterport,
panotour, roundme, .../3d/..., 360/pano) либо любую ссылку рядом с упоминанием
«3D / 360 / виртуальн / панорам».

Результат печатается в лог (секция «РЕЗУЛЬТАТ»). Ничего не коммитит.
"""
from __future__ import annotations

import asyncio
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from apply_telegram_supplemental_comments import (  # noqa: E402
    DEFAULT_API_HASH,
    DEFAULT_API_ID,
    fetch_comment_messages,
    load_env_files,
    load_targets_from_snapshot,
)
from telegram_runtime import connected_telegram_client, run_async_entrypoint  # noqa: E402

URL_RE = re.compile(r"https?://[^\s)>\]\"'»]+", re.I)
TOUR_DOMAIN_RE = re.compile(r"b2brec|kuula\.co|matterport|panotour|roundme|/3d/|\b3d\b|360|pano", re.I)
HINT_RE = re.compile(r"3\s?d|360|виртуал|панорам|pano|тур", re.I)


def message_text(message) -> str:
    return getattr(message, "message", None) or getattr(message, "text", None) or ""


def message_urls(message) -> set[str]:
    urls: set[str] = set()
    for m in URL_RE.finditer(message_text(message)):
        urls.add(m.group(0).rstrip(".,;)"))
    for ent in getattr(message, "entities", None) or []:
        u = getattr(ent, "url", None)  # скрытые ссылки (MessageEntityTextUrl)
        if u:
            urls.add(str(u))
    return urls


def is_tour_url(url: str) -> bool:
    return bool(TOUR_DOMAIN_RE.search(url))


async def scan(client, targets) -> tuple[list[dict], int, int]:
    hits: list[dict] = []
    errors = 0
    no_thread = 0
    for i, t in enumerate(targets, 1):
        try:
            msgs = await fetch_comment_messages(client, t)
        except Exception as error:  # noqa: BLE001
            text = str(error).lower()
            if "message id used in the peer was invalid" in text or "msg_id_invalid" in text:
                no_thread += 1
                continue
            errors += 1
            print(f"[ERR] {t.slug}: {error}", flush=True)
            continue
        for mid, m in msgs.items():
            text = message_text(m)
            urls = message_urls(m)
            if not urls:
                continue
            tour_urls = [u for u in urls if is_tour_url(u)]
            picked = tour_urls or ([u for u in urls if HINT_RE.search(text)])
            for u in picked:
                hits.append({
                    "slug": t.slug, "title": t.title, "channel": t.channel,
                    "mid": mid, "url": u, "explicit": is_tour_url(u),
                    "preview": " ".join(text.split())[:140],
                })
        if i % 25 == 0:
            print(f"...просмотрено {i}/{len(targets)}", flush=True)
        await asyncio.sleep(0.15)
    return hits, errors, no_thread


async def main_async() -> int:
    load_env_files()
    targets = load_targets_from_snapshot()
    api_id = int(os.getenv("TELEGRAM_API_ID", str(DEFAULT_API_ID)))
    api_hash = os.getenv("TELEGRAM_API_HASH", DEFAULT_API_HASH)
    session = os.getenv("TG_SESSION", str(ROOT / "tg_session"))
    print(f"Объектов для скана: {len(targets)}", flush=True)

    async with connected_telegram_client(session, api_id, api_hash, receive_updates=False) as client:
        if not await client.is_user_authorized():
            raise RuntimeError("Telegram session is not authorized")
        hits, errors, no_thread = await scan(client, targets)

    print("\n===== РЕЗУЛЬТАТ: ссылки на 3D-туры в комментариях =====", flush=True)
    explicit = [h for h in hits if h["explicit"]]
    maybe = [h for h in hits if not h["explicit"]]
    if explicit:
        print(f"\nЯВНЫЕ ссылки на туры ({len(explicit)}):")
        for h in explicit:
            print(f"- {h['title']} [{h['slug']}] {h['channel']}#{h['mid']}: {h['url']}")
    if maybe:
        print(f"\nВОЗМОЖНО туры (ссылка рядом с 3D/360/панорама) ({len(maybe)}):")
        for h in maybe:
            print(f"- {h['title']} [{h['slug']}] {h['channel']}#{h['mid']}: {h['url']}  | «{h['preview']}»")
    if not hits:
        print("Ничего похожего на 3D-туры в комментариях не найдено.")
    print(f"\nИтого: явных {len(explicit)}, возможных {len(maybe)} | без треда комментариев: {no_thread} | ошибок: {errors}", flush=True)
    return 0


def main() -> int:
    return run_async_entrypoint(main_async(), name="scan_comments_for_tours", default_timeout=3000)


if __name__ == "__main__":
    raise SystemExit(main())
