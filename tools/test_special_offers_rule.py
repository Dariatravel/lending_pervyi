#!/usr/bin/env python3
"""Правило Дарьи 17.10.2026: новый пост заменяет объект, только если старый пост удалён.

Проверяем scripts/sync_catalog_from_telegram.replaces_existing_hotel на подставном
клиенте Telegram: старый пост на месте → новый размещается дополнительно;
старый удалён → замена (полная перевыкладка); сбой проверки → не заменяем.
Запуск: python3 tools/test_special_offers_rule.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import sync_catalog_from_telegram as sync  # noqa: E402


class FakeClient:
    def __init__(self, alive: set[int], broken: bool = False):
        self.alive = alive
        self.broken = broken
        self.calls = 0

    async def get_entity(self, name):
        return name

    async def get_messages(self, entity, ids):
        self.calls += 1
        if self.broken:
            raise ConnectionError("нет сети")
        return object() if ids in self.alive else None


def run(coro):
    return asyncio.run(coro)


def main() -> int:
    failures: list[str] = []

    def check(cond: bool, message: str) -> None:
        if not cond:
            failures.append(message)

    main_151 = {"slug": "plyazhnyy-kompleks-151-na-beregu-4620", "source_message_id": 4620}

    # Спецпредложение 5403 при живом основном посте 4620 — не заменяет.
    sync._HOTEL_POST_EXISTS.clear()
    client = FakeClient(alive={4620, 5403})
    check(run(sync.replaces_existing_hotel(client, main_151, 5403)) is False, "спецпредложение заменило живой основной пост")

    # Полная перевыкладка: старый пост удалён — замена разрешена.
    sync._HOTEL_POST_EXISTS.clear()
    client = FakeClient(alive={5403})
    check(run(sync.replaces_existing_hotel(client, main_151, 5403)) is True, "перевыкладка (старый удалён) не заменила объект")

    # Тот же пост — это тот же объект.
    sync._HOTEL_POST_EXISTS.clear()
    client = FakeClient(alive=set())
    check(run(sync.replaces_existing_hotel(client, main_151, 4620)) is True, "тот же пост не узнан")
    check(client.calls == 0, "для того же поста не нужно спрашивать Telegram")

    # Сбой проверки — безопаснее не заменять.
    sync._HOTEL_POST_EXISTS.clear()
    client = FakeClient(alive=set(), broken=True)
    check(run(sync.replaces_existing_hotel(client, main_151, 5403)) is False, "при сбое проверки объект заменён")

    # Ответ запоминается: второй вопрос про тот же пост не идёт в Telegram.
    sync._HOTEL_POST_EXISTS.clear()
    client = FakeClient(alive={4620})
    run(sync.hotel_post_still_exists(client, 4620))
    run(sync.hotel_post_still_exists(client, 4620))
    check(client.calls == 1, f"повторный запрос в Telegram: {client.calls}")

    # Пустой номер — поста нет.
    check(run(sync.hotel_post_still_exists(FakeClient(alive=set()), 0)) is False, "номер 0 считается живым постом")

    if failures:
        print("ОШИБКИ:")
        for failure in failures:
            print(" -", failure)
        return 1
    print("OK: спецпредложения размещаются дополнительно, замена — только при полной перевыкладке")
    return 0


if __name__ == "__main__":
    sys.exit(main())
