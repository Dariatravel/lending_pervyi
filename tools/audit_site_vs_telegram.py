#!/usr/bin/env python3
"""Ежедневная сверка сайта с Telegram-каналами (только чтение).

Часовой автосинк (watch-telegram) сообщает о том, что он сделал; о том, что
пропустил, он молчит — так «Феникс» и «Римма» месяц жили старыми данными
(06.10.2026). Эта сверка честная: для КАЖДОГО активного объекта берём пост
из канала и сравниваем с сайтом.

Что считается расхождением:
  * исходный пост удалён, а в теме квартиры есть новый — сайт отстал;
  * исходный пост удалён и замены нет — объект на сайте «висит»;
  * локация / пляж / вместимость / краткое описание / цены на сайте не
    совпадают с постом (та же логика, что у сторожа: site_mismatch_parts).

Пишет output/site-vs-telegram-report.txt и число находок в
output/site-vs-telegram-findings.txt (для шага уведомления в workflow).
Ничего на сайте не меняет; код возврата 0 даже при находках — это отчёт.

    python3 tools/audit_site_vs_telegram.py [--limit N]
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from telegram_runtime import connected_telegram_client  # noqa: E402
from watch_telegram_updates import (  # noqa: E402
    DEFAULT_API_HASH,
    DEFAULT_API_ID,
    find_topic_replacement,
    load_catalog_payload,
    load_env_files,
    load_watch_items,
    site_mismatch_parts,
)

GRACE_SECONDS = 2 * 3600  # автосинк ходит раз в час; дважды по часу — с запасом
REPORT_PATH = ROOT / "output" / "site-vs-telegram-report.txt"
FINDINGS_PATH = ROOT / "output" / "site-vs-telegram-findings.txt"


async def run(limit: int) -> int:
    load_env_files()
    api_id = int(os.getenv("TELEGRAM_API_ID", str(DEFAULT_API_ID)))
    api_hash = os.getenv("TELEGRAM_API_HASH", DEFAULT_API_HASH)
    session = os.getenv("TG_SESSION", str(ROOT / "tg_session"))

    items = load_watch_items(limit=limit or None)
    rows = {
        f"{row.get('source_kind')}:{row.get('slug')}": row
        for row in (load_catalog_payload().get("listings") or [])
        if row.get("is_active") is not False
    }

    replaced: list[str] = []   # пост удалён, в теме есть новый
    orphaned: list[str] = []   # пост удалён, замены нет
    mismatched: list[str] = [] # пост жив, но сайт с ним расходится
    pending: list[str] = []    # пост правлен меньше двух часов назад — автосинк ещё впереди
    errors: list[str] = []

    async with connected_telegram_client(session, api_id, api_hash, receive_updates=False) as client:
        if not await client.is_user_authorized():
            raise RuntimeError(f"Telegram session is not authorized: {session}")
        entities = {}
        by_channel: dict[str, list] = {}
        for item in items:
            by_channel.setdefault(item.channel, []).append(item)
        for channel, channel_items in by_channel.items():
            entity = entities.get(channel) or await client.get_entity(channel)
            entities[channel] = entity
            # Посты берём пачками по 100 — это одна-две команды на канал, а не сотни.
            messages: dict[int, object] = {}
            ids = sorted({item.message_id for item in channel_items})
            for start in range(0, len(ids), 100):
                chunk = ids[start:start + 100]
                try:
                    fetched = await client.get_messages(entity, ids=chunk)
                except Exception as error:  # noqa: BLE001
                    errors.append(f"{channel}: не удалось получить посты {chunk[0]}–{chunk[-1]}: {error}")
                    continue
                for message in fetched or []:
                    if message is not None:
                        messages[int(message.id)] = message
            for item in channel_items:
                message = messages.get(item.message_id)
                label = f"{item.title} — {item.telegram_url}"
                try:
                    if message is None:
                        replacement = None
                        if item.kind == "kvartira" and item.topic_id:
                            replacement = await find_topic_replacement(client, entity, int(item.topic_id), item.message_id)
                        if replacement is not None:
                            replaced.append(
                                f"{item.title} — старый пост удалён, в теме новый "
                                f"https://t.me/{item.channel}/{int(replacement.id)} (сайт отстал)"
                            )
                        else:
                            orphaned.append(f"{label} — пост удалён, замены нет (объект на сайте висит)")
                        continue
                    parts = site_mismatch_parts(rows.get(item.key), message.message or "")
                    if parts:
                        # Пост правили только что — часовой автосинк ещё не успел.
                        # Такое не расхождение, а очередь: иначе утренний отчёт
                        # шумел бы о том, что само исправится к следующему часу.
                        edited_at = getattr(message, "edit_date", None) or getattr(message, "date", None)
                        if edited_at is not None and (datetime.now(timezone.utc) - edited_at).total_seconds() < GRACE_SECONDS:
                            pending.append(f"{item.title} — пост правлен {edited_at.astimezone().strftime('%H:%M')}, ждёт автосинка — {item.telegram_url}")
                        else:
                            mismatched.append(f"{item.title} — не совпадает: {', '.join(parts)} — {item.telegram_url}")
                except Exception as error:  # noqa: BLE001
                    errors.append(f"{item.slug}: {error}")

    now = datetime.now(timezone.utc).astimezone().strftime("%d.%m.%Y %H:%M")
    lines = [f"Сверка сайта с Telegram — {now}", f"Объектов проверено: {len(items)}", ""]
    for title, bucket in (
        ("Сайт отстал (пост заменён в теме):", replaced),
        ("Пост удалён, объект на сайте остаётся:", orphaned),
        ("Сайт расходится с постом:", mismatched),
        ("Свежие правки, ждут автосинка (не расхождение):", pending),
        ("Не удалось проверить:", errors),
    ):
        if bucket:
            lines.append(f"{title} {len(bucket)}")
            lines.extend(f"- {entry}" for entry in bucket)
            lines.append("")
    findings = len(replaced) + len(orphaned) + len(mismatched)
    if not findings and not errors:
        lines.append("Расхождений нет: сайт совпадает с каналами.")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    FINDINGS_PATH.write_text(str(findings + len(errors)) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Сверка сайта с Telegram.")
    parser.add_argument("--limit", type=int, default=0, help="Проверить только первые N объектов.")
    args = parser.parse_args()
    return asyncio.run(run(args.limit))


if __name__ == "__main__":
    sys.exit(main())
