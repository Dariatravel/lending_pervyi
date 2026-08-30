#!/usr/bin/env python3
"""Показать тексты постов канала @abhazbereg — подготовка метаданных статьи.

Новая статья блога начинается с чтения поста: по тексту заполняются slug,
заголовок, лид и теги в POST_META (sync_blog_from_abhazbereg.py). Сам синк
без метаданных падает, поэтому тексты достаёт этот отдельный скрипт.

    TARGET_BLOG_POST_IDS=2460,2461 python3 scripts/dump_blog_post_texts.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from sync_blog_from_abhazbereg import (  # noqa: E402
    API_HASH,
    API_ID,
    CHANNEL,
    SESSION,
    resolve_album_message,
)
from telegram_runtime import connected_telegram_client, run_async_entrypoint  # noqa: E402


async def main_async() -> int:
    raw_ids = os.getenv("TARGET_BLOG_POST_IDS", "").strip()
    if not raw_ids:
        print(
            "Задайте TARGET_BLOG_POST_IDS, например 2460,2461 "
            "(пост другого канала — как abhazbooking:5252)",
            file=sys.stderr,
        )
        return 2
    targets: list[tuple[str, int]] = []
    for part in raw_ids.split(","):
        part = part.strip()
        if not part:
            continue
        channel, _, number = part.rpartition(":")
        targets.append((channel or CHANNEL, int(number)))

    by_channel: dict[str, list[int]] = {}
    for channel, post_id in targets:
        by_channel.setdefault(channel, []).append(post_id)

    missing = 0
    async with connected_telegram_client(SESSION, API_ID, API_HASH, receive_updates=False) as client:
        for channel, post_ids in by_channel.items():
            entity = await client.get_entity(channel)
            messages = await client.get_messages(entity, ids=post_ids)
            by_id = {m.id: m for m in messages if m}
            for post_id in post_ids:
                msg = by_id.get(post_id)
                print(f"\n===== пост @{channel}/{post_id} =====")
                if not msg:
                    print("(пост не найден)")
                    missing += 1
                    continue
                raw_text, date_msg = await resolve_album_message(client, entity, post_id, msg)
                when = date_msg.date.strftime("%Y-%m-%d") if date_msg and date_msg.date else "?"
                print(f"дата: {when}, фото: {'да' if msg.photo or msg.grouped_id else 'нет'}")
                print("--- текст ---")
                print(raw_text or "(без текста)")
    return 1 if missing else 0


def main() -> int:
    return run_async_entrypoint(main_async(), name="dump_blog_post_texts", default_timeout=600)


if __name__ == "__main__":
    raise SystemExit(main())
