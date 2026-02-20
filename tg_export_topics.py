import asyncio
import json
import os
from telethon import TelegramClient, functions

api_id = int(os.getenv("TG_API_ID", "0"))
api_hash = os.getenv("TG_API_HASH", "")
chat = "abhkvartira"

async def main():
    if not api_id or not api_hash:
        raise RuntimeError("Set TG_API_ID and TG_API_HASH in environment before running.")
    client = TelegramClient("tg_session", api_id, api_hash)
    await client.start()
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
    await client.disconnect()

asyncio.run(main())
