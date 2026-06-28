from __future__ import annotations

import asyncio
import os
import socket
import sqlite3
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Awaitable

import fcntl
from telethon import TelegramClient


class TelegramRuntimeError(RuntimeError):
    pass


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def telegram_connect_timeout(default: int = 45) -> int:
    return _env_int("TG_CONNECT_TIMEOUT_SECONDS", default)


def telegram_script_timeout(default: int = 900) -> int:
    return _env_int("TG_SCRIPT_TIMEOUT_SECONDS", default)


def telegram_lock_timeout(default: int = 120) -> int:
    return _env_int("TG_SESSION_LOCK_TIMEOUT_SECONDS", default)


def session_lock_path(session: str | os.PathLike[str]) -> Path:
    path = Path(session)
    if path.suffix == ".session":
        return path.with_suffix(".session.lock")
    return Path(str(path) + ".session.lock")


class TelegramSessionLock:
    def __init__(self, session: str | os.PathLike[str], *, timeout: int | None = None) -> None:
        self.timeout = telegram_lock_timeout() if timeout is None else timeout
        self.path = session_lock_path(session)
        self._handle: Any | None = None

    def __enter__(self) -> "TelegramSessionLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.path.open("a+")
        deadline = time.monotonic() + self.timeout
        while True:
            try:
                fcntl.flock(self._handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                self._handle.seek(0)
                self._handle.truncate()
                self._handle.write(f"pid={os.getpid()}\n")
                self._handle.flush()
                return self
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise TelegramRuntimeError(
                        "Telegram-сессия занята другим процессом. "
                        f"Не удалось получить lock за {self.timeout} сек: {self.path}"
                    )
                time.sleep(0.5)

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if not self._handle:
            return
        try:
            fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        finally:
            self._handle.close()
            self._handle = None


def is_network_error(error: BaseException) -> bool:
    if isinstance(error, (socket.gaierror, TimeoutError, ConnectionError, OSError)):
        return True
    cause = getattr(error, "__cause__", None)
    context = getattr(error, "__context__", None)
    return bool(
        (cause and is_network_error(cause))
        or (context and context is not error and is_network_error(context))
    )


def user_friendly_error(error: BaseException) -> str:
    text = str(error)
    lowered = text.lower()
    if isinstance(error, asyncio.TimeoutError) or "timed out" in lowered or "timeout" in lowered:
        return "Техническая проблема проверки: Telegram не ответил вовремя. Повторите позже."
    if isinstance(error, TelegramRuntimeError):
        return f"Техническая проблема проверки: {text}"
    if "database is locked" in lowered:
        return "Техническая проблема проверки: Telegram-сессия занята другим процессом. Повторите позже."
    if "key is not registered" in lowered or "authkeyunregistered" in lowered or "auth key unregistered" in lowered:
        return (
            "Техническая проблема проверки: Telegram-сессия больше не авторизована. "
            "Нужно заново войти в Telegram для tg_session."
        )
    if is_network_error(error) or "nodename nor servname provided" in lowered:
        return "Нет соединения с Telegram / проблема DNS, бот повторит позже."
    return f"Техническая проблема проверки: {text}"


@asynccontextmanager
async def connected_telegram_client(
    session: str | os.PathLike[str],
    api_id: int,
    api_hash: str,
    *,
    receive_updates: bool = False,
    connect_timeout: int | None = None,
    lock_timeout: int | None = None,
):
    with TelegramSessionLock(session, timeout=lock_timeout):
        client = TelegramClient(str(session), api_id, api_hash, receive_updates=receive_updates)
        try:
            await asyncio.wait_for(client.connect(), timeout=connect_timeout or telegram_connect_timeout())
            yield client
        finally:
            try:
                await asyncio.wait_for(client.disconnect(), timeout=15)
            except Exception:
                pass


def run_async_entrypoint(
    awaitable: Awaitable[Any],
    *,
    name: str,
    default_timeout: int = 900,
) -> int:
    timeout = telegram_script_timeout(default_timeout)
    try:
        result = asyncio.run(asyncio.wait_for(awaitable, timeout=timeout))
    except Exception as error:  # noqa: BLE001
        print(user_friendly_error(error), flush=True)
        return 124 if isinstance(error, asyncio.TimeoutError) else 1
    return int(result or 0)
