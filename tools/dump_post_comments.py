#!/usr/bin/env python3
"""Показать комментарии к посту канала: id, тип медиа, альбом, подпись.

Диагностика для блоков «Дополнительные материалы»: перенос берёт только медиа
с подписями, и когда блок не собрался (пример — СиаЛенд #3800, 01.09.2026),
нужно увидеть, что на самом деле лежит в комментариях и где там текст.

    TG_TARGET="abhazbooking:3800" python3 tools/dump_post_comments.py

Запуск — в GitHub Actions (MTProto с RU-адресов фильтруется).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from telethon.tl.functions.messages import GetRepliesRequest  # noqa: E402

from telegram_runtime import connected_telegram_client, run_async_entrypoint  # noqa: E402

DEFAULT_API_ID = 32916166
DEFAULT_API_HASH = "eefdec49605521b061de4bdf62ef784e"


def media_label(message) -> str:
    file_obj = getattr(message, "file", None)
    mime = str(getattr(file_obj, "mime_type", "") or "")
    if getattr(message, "photo", None):
        return "фото"
    if mime.startswith("video/"):
        return "видео"
    if mime:
        return f"файл {mime}"
    return "текст"


async def main_async() -> int:
    target = os.getenv("TG_TARGET", "").strip()
    if ":" not in target:
        print("Задайте TG_TARGET, например abhazbooking:3800", file=sys.stderr)
        return 2
    channel, _, msg_id_s = target.partition(":")
    msg_id = int(msg_id_s)

    api_id = int(os.getenv("TELEGRAM_API_ID", str(DEFAULT_API_ID)))
    api_hash = os.getenv("TELEGRAM_API_HASH", DEFAULT_API_HASH)
    session = os.getenv("TG_SESSION", str(ROOT / "tg_session"))

    async with connected_telegram_client(session, api_id, api_hash, receive_updates=False) as client:
        entity = await client.get_entity(channel)
        rows = []
        offset_id = 0
        while True:
            result = await client(
                GetRepliesRequest(
                    peer=entity, msg_id=msg_id, offset_id=offset_id, offset_date=None,
                    add_offset=0, limit=100, max_id=0, min_id=0, hash=0,
                )
            )
            batch = list(getattr(result, "messages", []) or [])
            if not batch:
                break
            rows.extend(batch)
            offset_id = min(int(m.id) for m in batch)
            if len(batch) < 100:
                break
        rows.sort(key=lambda m: int(m.id))
        print(f"Комментариев к @{channel}/{msg_id}: {len(rows)}\n")
        for m in rows:
            text = " ".join(str(getattr(m, "message", "") or "").split())
            group = getattr(m, "grouped_id", None)
            when = m.date.strftime("%Y-%m-%d") if m.date else "?"
            print(f"  #{m.id} [{when}] {media_label(m):12} альбом={group or '-'} | {text[:90]}")
    return 0


def main() -> int:
    return run_async_entrypoint(main_async(), name="dump_post_comments", default_timeout=600)


if __name__ == "__main__":
    raise SystemExit(main())
