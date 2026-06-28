import asyncio
import json
import os
import sys
from pathlib import Path

from telethon import functions

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))

from telegram_runtime import connected_telegram_client, run_async_entrypoint  # noqa: E402

api_id = int(os.getenv("TG_API_ID", "0"))
api_hash = os.getenv("TG_API_HASH", "")
chat = "abhkvartira"

async def main():
    if not api_id or not api_hash:
        raise RuntimeError("Set TG_API_ID and TG_API_HASH in environment before running.")
    async with connected_telegram_client(ROOT / "tg_session", api_id, api_hash, receive_updates=False) as client:
        entity = await client.get_entity(chat)

        res = await client(functions.messages.GetForumTopicsRequest(
            peer=entity,
            offset_date=None,
            offset_id=0,
            offset_topic=0,
            limit=100,
            q=""
        ))

        data = []
        for t in res.topics:
            data.append({
                "topic_id": t.id,
                "title": getattr(t, "title", ""),
                "top_message_id": getattr(t, "top_message", None)
            })

    with open("topics.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Готово: {len(data)} тем -> topics.json")

if __name__ == "__main__":
    raise SystemExit(run_async_entrypoint(main(), name="tg_export_topics", default_timeout=900))
