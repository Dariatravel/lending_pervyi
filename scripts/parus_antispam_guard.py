#!/usr/bin/env python3
"""Small Telegram guard for the Parus discussion chat.

MissRose currently refuses moderation commands in this chat until the group is
verified through Rose's miniapp. This guard is intentionally narrow: it removes
the recurring "paid work / write to DM" spam that keeps appearing in Parus.
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from telethon import TelegramClient
from telethon.tl.functions.channels import DeleteMessagesRequest, EditBannedRequest
from telethon.tl.types import ChatBannedRights

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import telegram_runtime as rt  # noqa: E402
import watch_telegram_updates as w  # noqa: E402

CHAT_ID = -1002342429519
SESSION = ROOT / "tg_session"
STATE_PATH = ROOT / "output" / "parus-antispam-guard-state.json"
LOG_PATH = ROOT / "output" / "parus-antispam-guard.log"

SPAM_PATTERNS = [
    r"\bподработк[аиуеой]*\b",
    r"писат[ьи]\s+в\s+лс",
    r"нужн[аы]?\s+(?:человек|люд[ие]й?|несколько)",
    r"срочн[оа]?\s+нужн",
    r"есть\s+работа",
    r"ежедневн\w*\s+зарплат",
    r"платим\s+ежедневн",
    r"заплачу\s+\d",
    r"оплат[ауы]\s+(?:в\s+день|ежедневн)",
    r"на\s+пару\s+(?:часов|дней)",
    r"\b[45]\s*(?:тысяч|тыс|к)\b",
]

SAFE_CONTEXT = [
    "отель",
    "гост",
    "номер",
    "засел",
    "брон",
    "абхаз",
    "гагра",
    "море",
]


def log(line: str) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).isoformat()
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(f"{stamp} {line}\n")


def load_seen() -> set[int]:
    if not STATE_PATH.exists():
        return set()
    try:
        raw = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return set()
    return {int(value) for value in raw.get("seen_message_ids", [])}


def save_seen(seen: set[int]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {"seen_message_ids": sorted(seen)[-500:]}
    STATE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def normalize(text: str) -> str:
    value = (text or "").casefold().replace("ё", "е")
    value = re.sub(r"[\u200b\u200c\u200d\xa0]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def looks_like_work_spam(text: str) -> bool:
    text = normalize(text)
    if not text:
        return False
    matches = sum(1 for pattern in SPAM_PATTERNS if re.search(pattern, text))
    if matches >= 2:
        return True
    if matches >= 1 and "лс" in text and not any(word in text for word in SAFE_CONTEXT):
        return True
    return False


async def main() -> int:
    seen = load_seen()
    async with rt.connected_telegram_client(
        SESSION,
        w.DEFAULT_API_ID,
        w.DEFAULT_API_HASH,
        receive_updates=False,
        lock_timeout=20,
    ) as client:
        chat = await client.get_entity(CHAT_ID)
        delete_ids: list[int] = []
        sender_ids: set[int] = set()
        async for message in client.iter_messages(chat, limit=30):
            seen.add(message.id)
            text = message.message or ""
            if looks_like_work_spam(text):
                delete_ids.append(message.id)
                if message.sender_id:
                    sender_ids.add(int(message.sender_id))
                log(f"matched id={message.id} sender={message.sender_id} text={text!r}")
        if delete_ids:
            await client(DeleteMessagesRequest(channel=chat, id=delete_ids))
            log(f"deleted ids={delete_ids}")
        banned_rights = ChatBannedRights(until_date=None, view_messages=True)
        for sender_id in sender_ids:
            try:
                await client(EditBannedRequest(chat, sender_id, banned_rights))
                log(f"banned sender={sender_id}")
            except Exception as error:  # noqa: BLE001
                log(f"ban_failed sender={sender_id} error={type(error).__name__}: {error}")
    save_seen(seen)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
