#!/usr/bin/env python3
"""Перевыпуск доступа автосинка к Telegram — одной командой, на Mac.

Автосинк читает каналы под аккаунтом владелицы. Доступ хранится в GitHub
Secrets (TG_STRING_SESSION) и иногда перестаёт действовать: Telegram сбрасывает
старые входы, или сеансы завершают вручную в приложении. Тогда watch-telegram
падает с «Telegram session is not authorized», и новые посты не попадают на сайт.

Этот скрипт делает всё подряд: чинит вход, проверяет каналы и, если под рукой
есть gh, сам обновляет секрет в GitHub.

    python3 tools/relogin_telegram.py

Запускать только на Mac: из GitHub Actions и из песочниц агента сеть до
Telegram закрыта, а сам файл сессии — полный доступ к аккаунту, его нельзя
класть ни в git, ни в артефакты.
"""
from __future__ import annotations

import asyncio
import getpass
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SESSION = os.getenv("TG_SESSION", str(ROOT / "tg_session"))
CHANNELS = ("abhazbooking", "abhkvartira")
SECRET_NAME = "TG_STRING_SESSION"

try:
    from telethon import TelegramClient
    from telethon.errors import SessionPasswordNeededError
    from telethon.sessions import StringSession
except ImportError:  # noqa: BLE001
    raise SystemExit(
        "Не установлена библиотека telethon. Установите её и повторите:\n"
        "    python3 -m pip install telethon"
    )


def credentials() -> tuple[int, str]:
    """Те же API-ключи, что использует сам автосинк."""
    text = (ROOT / "scripts" / "watch_telegram_updates.py").read_text(encoding="utf-8")
    api_id = re.search(r"DEFAULT_API_ID\s*=\s*(\d+)", text)
    api_hash = re.search(r'DEFAULT_API_HASH\s*=\s*"([0-9a-f]+)"', text)
    if not api_id or not api_hash:
        raise SystemExit("Не нашёл DEFAULT_API_ID/DEFAULT_API_HASH в scripts/watch_telegram_updates.py")
    return int(api_id.group(1)), api_hash.group(1)


async def ensure_login(client: TelegramClient) -> None:
    """Войти, если вход слетел. Код и пароль вводит владелица здесь же."""
    if await client.is_user_authorized():
        print("Вход в Telegram действует — заново входить не нужно.")
        return

    print("Вход слетел, нужно войти заново.")
    phone = input("Номер телефона (в формате +79991234567): ").strip()
    await client.send_code_request(phone)
    print("Код Telegram присылает В САМО ПРИЛОЖЕНИЕ — в чат «Telegram», не в SMS.")
    code = input("Код из приложения: ").strip()
    try:
        await client.sign_in(phone, code)
    except SessionPasswordNeededError:
        # Двухэтапная проверка: пароль не показываем на экране.
        password = getpass.getpass("Пароль двухэтапной проверки (не отображается): ")
        await client.sign_in(password=password)
    print("Вход выполнен.")


async def check_channels(client: TelegramClient) -> bool:
    """Убедиться, что аккаунт видит оба канала — иначе синку нечего читать."""
    everything_visible = True
    for channel in CHANNELS:
        try:
            entity = await client.get_entity(channel)
            print(f"  @{channel} — виден: {getattr(entity, 'title', '?')}")
        except Exception as error:  # noqa: BLE001
            print(f"  @{channel} — НЕ виден: {error}")
            everything_visible = False
    return everything_visible


def push_secret(value: str) -> bool:
    """Обновить секрет через gh, если он установлен и авторизован."""
    if not shutil.which("gh"):
        return False
    print(f"Нашёлся gh — обновляю секрет {SECRET_NAME} в GitHub...")
    try:
        subprocess.run(
            ["gh", "secret", "set", SECRET_NAME, "--body", value],
            cwd=ROOT, check=True, capture_output=True, text=True,
        )
    except subprocess.CalledProcessError as error:
        print(f"gh не смог обновить секрет: {error.stderr.strip() or error}")
        return False
    print(f"Секрет {SECRET_NAME} обновлён.")
    return True


async def run() -> int:
    api_id, api_hash = credentials()
    client = TelegramClient(SESSION, api_id, api_hash, receive_updates=False)
    await client.connect()
    try:
        await ensure_login(client)
        me = await client.get_me()
        print(f"Аккаунт: {getattr(me, 'first_name', '')} (@{getattr(me, 'username', '') or '—'})")
        print("Проверяю каналы:")
        visible = await check_channels(client)
        string = StringSession.save(client.session)
    finally:
        await client.disconnect()

    if not visible:
        print("\nВНИМАНИЕ: часть каналов не видна. Синк будет работать наполовину.")

    if push_secret(string):
        print("\nГотово. Осталось запустить Actions → Watch Telegram → Run workflow.")
        return 0

    print("\nСтрока ниже — это доступ к аккаунту. Не пересылайте её никуда, кроме GitHub.")
    print("GitHub → Settings → Secrets and variables → Actions → "
          f"{SECRET_NAME} → Update → вставить → Update secret.\n")
    print(string)
    return 0


def main() -> int:
    return asyncio.run(run())


if __name__ == "__main__":
    raise SystemExit(main())
