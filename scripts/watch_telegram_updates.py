#!/usr/bin/env python3
"""Watch existing site listings for edited Telegram post text, prices, and media."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import html
import json
import os
import re
import sys
import unicodedata
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from telethon import TelegramClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from sync_abhazbooking_2026 import parse_post  # noqa: E402

SNAPSHOT_PATH = ROOT / "data" / "catalog-snapshot.json"
STATE_PATH = ROOT / "output" / "telegram-watch-state.json"
REPORT_PATH = ROOT / "output" / "telegram-watch-report.txt"
TARGETS_PATH = ROOT / "output" / "telegram-watch-changed-targets.json"
ENV_PATHS = (
    ROOT / ".env.site-update-bot",
    ROOT / ".env.supabase.local",
    ROOT / ".env.yandex.local",
)

DEFAULT_API_ID = 32916166
DEFAULT_API_HASH = "eefdec49605521b061de4bdf62ef784e"


@dataclass
class WatchItem:
    key: str
    kind: str
    slug: str
    title: str
    channel: str
    message_id: int
    topic_id: int | None
    telegram_url: str


@dataclass
class Signature:
    text_hash: str
    prices_hash: str
    media_hash: str
    full_hash: str
    media_total: int
    media_photo: int
    media_video: int


@dataclass
class Change:
    key: str
    kind: str
    slug: str
    title: str
    channel: str
    message_id: int
    topic_id: int | None
    telegram_url: str
    changed_parts: list[str]


def load_env_files() -> None:
    for path in ENV_PATHS:
        if not path.exists():
            continue
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def sha256_json(payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def normalize_text(value: str) -> str:
    value = html.unescape(value or "")
    value = unicodedata.normalize("NFKC", value)
    value = value.replace("\xa0", " ")
    value = re.sub(r"[ \t\r\f\v]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def prices_payload(text: str) -> list[dict[str, str]]:
    try:
        parsed = parse_post(text)
    except Exception:  # noqa: BLE001 - watcher must not fail on one unusual post
        return []
    prices = parsed.get("prices") if isinstance(parsed, dict) else []
    result: list[dict[str, str]] = []
    for row in prices or []:
        if not isinstance(row, dict):
            continue
        result.append(
            {
                "kind": str(row.get("kind") or "").strip(),
                "text": normalize_text(str(row.get("text") or "")),
            }
        )
    return result


def media_kind(message: Any) -> str:
    file_obj = getattr(message, "file", None)
    mime = str(getattr(file_obj, "mime_type", "") or "")
    if mime.startswith("video/"):
        return "video"
    if mime.startswith("image/"):
        return "photo"
    raw_name = type(getattr(message, "media", None)).__name__.lower()
    if "photo" in raw_name:
        return "photo"
    if "document" in raw_name and "video" in mime:
        return "video"
    return "other"


def media_payload(messages: list[Any]) -> tuple[list[dict[str, Any]], int, int]:
    rows: list[dict[str, Any]] = []
    photos = 0
    videos = 0
    for message in sorted(messages, key=lambda item: int(getattr(item, "id", 0) or 0)):
        file_obj = getattr(message, "file", None)
        kind = media_kind(message)
        if kind == "photo":
            photos += 1
        elif kind == "video":
            videos += 1
        rows.append(
            {
                "id": int(getattr(message, "id", 0) or 0),
                "grouped_id": str(getattr(message, "grouped_id", "") or ""),
                "kind": kind,
                "mime_type": str(getattr(file_obj, "mime_type", "") or ""),
                "size": int(getattr(file_obj, "size", 0) or 0),
                "duration": int(getattr(file_obj, "duration", 0) or 0),
            }
        )
    return rows, photos, videos


def build_signature(text: str, media_messages: list[Any]) -> Signature:
    normalized = normalize_text(text)
    prices = prices_payload(text)
    media_rows, photos, videos = media_payload(media_messages)
    text_hash = sha256_json(normalized)
    prices_hash = sha256_json(prices)
    media_hash = sha256_json(media_rows)
    full_hash = sha256_json(
        {
            "text": text_hash,
            "prices": prices_hash,
            "media": media_hash,
        }
    )
    return Signature(
        text_hash=text_hash,
        prices_hash=prices_hash,
        media_hash=media_hash,
        full_hash=full_hash,
        media_total=len(media_rows),
        media_photo=photos,
        media_video=videos,
    )


def load_watch_items(limit: int | None = None) -> list[WatchItem]:
    payload = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    items: list[WatchItem] = []
    for row in payload.get("listings") or []:
        if row.get("is_active") is False:
            continue
        kind = str(row.get("source_kind") or "").strip()
        channel = str(row.get("source_channel") or "").strip().lower()
        slug = str(row.get("slug") or "").strip()
        message_id = int(row.get("source_message_id") or 0)
        if kind not in {"hotel", "kvartira"} or channel not in {"abhazbooking", "abhkvartira"}:
            continue
        if not slug or not message_id:
            continue
        topic_raw = row.get("source_topic_id")
        topic_id = int(topic_raw) if topic_raw else None
        key = f"{kind}:{slug}"
        items.append(
            WatchItem(
                key=key,
                kind=kind,
                slug=slug,
                title=str(row.get("title") or slug).strip(),
                channel=channel,
                message_id=message_id,
                topic_id=topic_id,
                telegram_url=str(row.get("telegram_url") or f"https://t.me/{channel}/{message_id}"),
            )
        )
    items.sort(key=lambda item: (item.kind, item.slug))
    return items[:limit] if limit else items


def load_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return {"schema_version": 1, "items": {}}
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"schema_version": 1, "items": {}}
    if not isinstance(data.get("items"), dict):
        data["items"] = {}
    data.setdefault("schema_version", 1)
    return data


def save_state(state: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


async def album_media_messages(client: TelegramClient, entity: Any, canonical: Any) -> list[Any]:
    grouped_id = getattr(canonical, "grouped_id", None)
    if not grouped_id:
        return [canonical] if getattr(canonical, "media", None) else []
    window = 80
    min_id = max(1, int(canonical.id) - window)
    max_id = int(canonical.id) + window
    found: list[Any] = []
    async for message in client.iter_messages(entity, min_id=min_id, max_id=max_id):
        if getattr(message, "grouped_id", None) == grouped_id and getattr(message, "media", None):
            found.append(message)
    if not found and getattr(canonical, "media", None):
        return [canonical]
    return sorted(found, key=lambda item: int(getattr(item, "id", 0) or 0))


def changed_parts(previous: dict[str, Any], current: Signature) -> list[str]:
    parts: list[str] = []
    if previous.get("text_hash") != current.text_hash:
        parts.append("текст")
    if previous.get("prices_hash") != current.prices_hash:
        parts.append("цены")
    if previous.get("media_hash") != current.media_hash:
        parts.append("медиа")
    return parts


def render_report(
    *,
    checked: int,
    baseline_added: int,
    changes: list[Change],
    errors: list[str],
    accepted: bool,
) -> str:
    text_count = sum("текст" in item.changed_parts for item in changes)
    price_count = sum("цены" in item.changed_parts for item in changes)
    media_count = sum("медиа" in item.changed_parts for item in changes)
    lines = [
        "Telegram watch: ok",
        f"Проверено объектов: {checked}",
        f"Новых в watch-базе: {baseline_added}",
        f"Изменений: {len(changes)}",
        f"Текст: {text_count}, цены: {price_count}, медиа: {media_count}",
    ]
    if accepted:
        lines.append("Изменения приняты как новое базовое состояние.")
    if changes:
        lines.append("")
        lines.append("Что изменилось:")
        for change in changes[:40]:
            parts = ", ".join(change.changed_parts)
            lines.append(f"- {change.title} ({change.slug}) — {parts}; {change.telegram_url}")
        if len(changes) > 40:
            lines.append(f"... и ещё {len(changes) - 40}")
        lines.append("")
        lines.append("Для точечного обновления: /update_changed")
    if errors:
        lines.append("")
        lines.append(f"Ошибки чтения Telegram: {len(errors)}")
        for error in errors[:20]:
            lines.append(f"- {error}")
        if len(errors) > 20:
            lines.append(f"... и ещё {len(errors) - 20}")
    return "\n".join(lines) + "\n"


def write_targets(changes: list[Change]) -> None:
    hotel_ids = sorted({item.message_id for item in changes if item.kind == "hotel"})
    kv_topic_ids = sorted({int(item.topic_id) for item in changes if item.kind == "kvartira" and item.topic_id})
    kv_message_ids_without_topic = sorted(
        {item.message_id for item in changes if item.kind == "kvartira" and not item.topic_id}
    )
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "changed_total": len(changes),
        "hotel_source_ids": hotel_ids,
        "kv_topic_ids": kv_topic_ids,
        "kv_message_ids_without_topic": kv_message_ids_without_topic,
        "items": [asdict(item) for item in changes],
    }
    TARGETS_PATH.parent.mkdir(parents=True, exist_ok=True)
    TARGETS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


async def run(args: argparse.Namespace) -> int:
    load_env_files()
    api_id = int(os.getenv("TELEGRAM_API_ID", str(DEFAULT_API_ID)))
    api_hash = os.getenv("TELEGRAM_API_HASH", DEFAULT_API_HASH)
    session = os.getenv("TG_SESSION", str(ROOT / "tg_session"))
    items = load_watch_items(limit=args.limit)
    state = load_state()
    state_items: dict[str, Any] = state.setdefault("items", {})
    checked = 0
    baseline_added = 0
    changes: list[Change] = []
    errors: list[str] = []
    seen_keys: set[str] = set()
    entities: dict[str, Any] = {}

    client = TelegramClient(session, api_id, api_hash)
    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise RuntimeError(f"Telegram session is not authorized: {session}")
        for item in items:
            checked += 1
            seen_keys.add(item.key)
            try:
                entity = entities.get(item.channel)
                if entity is None:
                    entity = await client.get_entity(item.channel)
                    entities[item.channel] = entity
                canonical = await client.get_messages(entity, ids=item.message_id)
                if canonical is None:
                    errors.append(f"{item.slug}: message {item.channel}/{item.message_id} not found")
                    continue
                media_messages = await album_media_messages(client, entity, canonical)
                signature = build_signature(canonical.message or "", media_messages)
            except Exception as error:  # noqa: BLE001 - keep checking remaining objects
                errors.append(f"{item.slug}: {error}")
                continue

            current_payload = {
                **asdict(signature),
                "kind": item.kind,
                "slug": item.slug,
                "title": item.title,
                "channel": item.channel,
                "message_id": item.message_id,
                "topic_id": item.topic_id,
                "telegram_url": item.telegram_url,
                "last_seen_at": datetime.now(timezone.utc).isoformat(),
            }
            previous = state_items.get(item.key)
            if not previous:
                baseline_added += 1
                state_items[item.key] = current_payload
                continue
            parts = changed_parts(previous, signature)
            if parts:
                changes.append(
                    Change(
                        key=item.key,
                        kind=item.kind,
                        slug=item.slug,
                        title=item.title,
                        channel=item.channel,
                        message_id=item.message_id,
                        topic_id=item.topic_id,
                        telegram_url=item.telegram_url,
                        changed_parts=parts,
                    )
                )
                if args.accept_changes:
                    state_items[item.key] = current_payload
            else:
                previous["last_seen_at"] = current_payload["last_seen_at"]
                state_items[item.key] = previous
    finally:
        await client.disconnect()

    stale_keys = sorted(set(state_items) - seen_keys)
    if args.accept_changes:
        for key in stale_keys:
            state_items.pop(key, None)

    state["last_checked_at"] = datetime.now(timezone.utc).isoformat()
    state["last_checked_total"] = checked
    state["last_changes_total"] = len(changes)
    if args.write_state:
        save_state(state)

    write_targets(changes)
    report = render_report(
        checked=checked,
        baseline_added=baseline_added,
        changes=changes,
        errors=errors,
        accepted=args.accept_changes,
    )
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(report, end="")
    return 1 if errors and args.strict else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Проверить изменения в Telegram-постах объектов сайта.")
    parser.add_argument("--limit", type=int, default=0, help="Ограничить число объектов для проверки.")
    parser.add_argument(
        "--no-write-state",
        dest="write_state",
        action="store_false",
        help="Не сохранять watch-state после проверки.",
    )
    parser.add_argument(
        "--accept-changes",
        action="store_true",
        help="Записать текущие Telegram-сигнатуры как новое базовое состояние.",
    )
    parser.add_argument("--strict", action="store_true", help="Вернуть код 1, если были ошибки чтения Telegram.")
    parser.set_defaults(write_state=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
