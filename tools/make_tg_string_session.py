#!/usr/bin/env python3
"""Сконвертировать файловую Telethon-сессию (tg_session) в строковую (StringSession).

Строковая сессия нужна, чтобы watch-telegram работал в GitHub Actions
(секрет TG_STRING_SESSION) или на любом сервере без переноса файла tg_session.

Запускать на машине, где файловая сессия уже авторизована (Mac):

    python3 tools/make_tg_string_session.py
    python3 tools/make_tg_string_session.py --session /path/to/tg_session

Вывод — одна длинная строка. Это ПОЛНЫЙ доступ к Telegram-аккаунту:
хранить только в секретах (GitHub Secrets / .env.vps.local), никогда не коммитить.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from telethon import TelegramClient  # noqa: E402
from telethon.sessions import StringSession  # noqa: E402


def _default_api_credentials() -> tuple[int, str]:
    """Достать DEFAULT_API_ID/HASH из watch-скрипта без импорта его тяжёлых зависимостей."""
    text = (ROOT / "scripts" / "watch_telegram_updates.py").read_text(encoding="utf-8")
    api_id = re.search(r'DEFAULT_API_ID\s*=\s*(\d+)', text)
    api_hash = re.search(r'DEFAULT_API_HASH\s*=\s*"([0-9a-f]+)"', text)
    if not api_id or not api_hash:
        raise SystemExit("Не нашёл DEFAULT_API_ID/DEFAULT_API_HASH в scripts/watch_telegram_updates.py")
    return int(api_id.group(1)), api_hash.group(1)


async def run(session_path: str) -> int:
    default_id, default_hash = _default_api_credentials()
    api_id = int(os.getenv("TELEGRAM_API_ID", str(default_id)))
    api_hash = os.getenv("TELEGRAM_API_HASH", default_hash)
    client = TelegramClient(session_path, api_id, api_hash, receive_updates=False)
    await client.connect()
    try:
        if not await client.is_user_authorized():
            print(
                f"Сессия {session_path} не авторизована. Сначала войдите в Telegram "
                "любым существующим скриптом синка на этой машине.",
                file=sys.stderr,
            )
            return 1
        me = await client.get_me()
        string = StringSession.save(client.session)
    finally:
        await client.disconnect()

    print(f"# Аккаунт: {getattr(me, 'first_name', '')} (@{getattr(me, 'username', '') or '—'})", file=sys.stderr)
    print("# Строка ниже — секрет. GitHub → Settings → Secrets → Actions → TG_STRING_SESSION", file=sys.stderr)
    print(string)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--session",
        default=os.getenv("TG_SESSION", str(ROOT / "tg_session")),
        help="Путь к файловой сессии Telethon (по умолчанию TG_SESSION или ./tg_session).",
    )
    args = parser.parse_args()
    return asyncio.run(run(args.session))


if __name__ == "__main__":
    raise SystemExit(main())
