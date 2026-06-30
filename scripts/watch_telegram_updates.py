#!/usr/bin/env python3
"""Watch Telegram for edited existing posts and new object candidates."""
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
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from telethon.tl.functions import messages as message_functions

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from sync_abhazbooking_2026 import clean_line, parse_post  # noqa: E402
from telegram_runtime import connected_telegram_client, run_async_entrypoint  # noqa: E402

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
DEFAULT_NEW_OBJECTS_LIMIT = 120
DEFAULT_NEW_OBJECTS_DAYS = 45


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


@dataclass
class NewObject:
    kind: str
    title: str
    channel: str
    message_id: int
    topic_id: int | None
    telegram_url: str
    published_at: str
    reason: str


@dataclass
class KnownSources:
    source_pairs: set[tuple[str, int]]
    hotel_message_ids: set[int]
    kvartira_message_ids: set[int]
    kvartira_topic_ids: set[int]


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


def env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value >= 0 else default


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


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


def is_service_text(text: str) -> bool:
    sample = clean_line(text).lower()
    markers = (
        "кто я и почему выгодно бронировать",
        "отзывы гостей",
        "друзья, в этой группе собраны варианты",
        "здесь вы найдёте квартиры",
        "здесь вы найдете квартиры",
        "общение в группе",
    )
    return any(marker in sample for marker in markers)


def is_hotel_object_message(text: str) -> bool:
    if not text:
        return False
    cleaned = clean_line(text)
    if is_service_text(cleaned):
        return False
    if "📍" not in cleaned or "👥" not in cleaned:
        return False
    head = " ".join(clean_line(line) for line in cleaned.splitlines()[:18])
    return any(marker in head for marker in ("✔", "✔️", "цены", "стоимость", "🏖", "🏝"))


def is_kvartira_object_message(text: str) -> bool:
    if not text:
        return False
    cleaned = clean_line(text)
    if is_service_text(cleaned):
        return False
    if "📍" not in cleaned:
        return False
    return any(marker in cleaned for marker in ("👥", "🏖", "🏝", "✔", "✔️", "цены", "стоимость"))


def topic_message_score(text: str) -> float:
    if not text:
        return -1.0
    cleaned = clean_line(text)
    if is_service_text(cleaned):
        return -100.0
    score = 0.0
    if "📍" in cleaned:
        score += 3
    if "🏖" in cleaned or "🏝" in cleaned:
        score += 3
    if "👥" in cleaned:
        score += 2
    if "✔" in cleaned:
        score += 2
    if "ЦЕН" in cleaned.upper() or "СТОИМОСТ" in cleaned.upper():
        score += 1
    score += min(len(cleaned) / 120.0, 8)
    return score


def object_title(text: str, fallback: str = "новый объект") -> str:
    try:
        parsed = parse_post(text)
    except Exception:  # noqa: BLE001 - keep watcher tolerant of unusual posts
        parsed = {}
    title = str(parsed.get("title") or "").strip() if isinstance(parsed, dict) else ""
    if title:
        return clean_line(title)
    for line in (text or "").splitlines():
        cleaned = clean_line(line).strip(" -—")
        if cleaned:
            return cleaned[:120]
    return fallback


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


def load_catalog_payload() -> dict[str, Any]:
    payload = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def load_watch_items(limit: int | None = None) -> list[WatchItem]:
    payload = load_catalog_payload()
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


def load_known_sources() -> KnownSources:
    payload = load_catalog_payload()
    source_pairs: set[tuple[str, int]] = set()
    hotel_message_ids: set[int] = set()
    kvartira_message_ids: set[int] = set()
    kvartira_topic_ids: set[int] = set()
    for row in payload.get("listings") or []:
        if row.get("is_active") is False:
            continue
        kind = str(row.get("source_kind") or "").strip()
        channel = str(row.get("source_channel") or "").strip().lower()
        message_id = int(row.get("source_message_id") or 0)
        topic_id = int(row.get("source_topic_id") or 0)
        if channel and message_id:
            source_pairs.add((channel, message_id))
        if kind == "hotel" and channel == "abhazbooking" and message_id:
            hotel_message_ids.add(message_id)
        if kind == "kvartira" and channel == "abhkvartira":
            if message_id:
                kvartira_message_ids.add(message_id)
            if topic_id:
                kvartira_topic_ids.add(topic_id)
    return KnownSources(
        source_pairs=source_pairs,
        hotel_message_ids=hotel_message_ids,
        kvartira_message_ids=kvartira_message_ids,
        kvartira_topic_ids=kvartira_topic_ids,
    )


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


async def album_media_messages(client: Any, entity: Any, canonical: Any) -> list[Any]:
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


def is_recent_enough(message: Any, days: int) -> bool:
    if days <= 0:
        return True
    date = getattr(message, "date", None)
    if not date:
        return True
    if date.tzinfo is None:
        date = date.replace(tzinfo=timezone.utc)
    return date >= datetime.now(timezone.utc) - timedelta(days=days)


def message_date_iso(message: Any) -> str:
    date = getattr(message, "date", None)
    if not date:
        return ""
    return date.date().isoformat()


async def scan_new_hotel_objects(
    client: Any,
    known: KnownSources,
    *,
    limit: int,
    days: int,
    after_known: bool,
) -> list[NewObject]:
    entity = await client.get_entity("abhazbooking")
    min_id = max(known.hotel_message_ids or {0}) if after_known else 0
    found: list[NewObject] = []
    async for message in client.iter_messages(entity, limit=limit, min_id=min_id):
        message_id = int(getattr(message, "id", 0) or 0)
        if not message_id:
            continue
        if not is_recent_enough(message, days):
            break
        if ("abhazbooking", message_id) in known.source_pairs:
            continue
        text = str(getattr(message, "message", "") or "")
        if not is_hotel_object_message(text):
            continue
        found.append(
            NewObject(
                kind="hotel",
                title=object_title(text),
                channel="abhazbooking",
                message_id=message_id,
                topic_id=None,
                telegram_url=f"https://t.me/abhazbooking/{message_id}",
                published_at=message_date_iso(message),
                reason="пост похож на карточку отеля и его нет в catalog snapshot",
            )
        )
    found.sort(key=lambda item: item.message_id)
    return found


async def recent_forum_topics(client: Any, entity: Any, *, limit: int) -> list[Any]:
    topics: list[Any] = []
    offset_date = None
    offset_id = 0
    offset_topic = 0
    while len(topics) < limit:
        batch_limit = min(100, limit - len(topics))
        response = await client(
            message_functions.GetForumTopicsRequest(
                peer=entity,
                offset_date=offset_date,
                offset_id=offset_id,
                offset_topic=offset_topic,
                limit=batch_limit,
                q=None,
            )
        )
        batch = list(getattr(response, "topics", []) or [])
        if not batch:
            break
        topics.extend(batch)
        if len(batch) < batch_limit:
            break
        last = batch[-1]
        offset_date = getattr(last, "date", None)
        offset_id = int(getattr(last, "id", 0) or 0)
        offset_topic = int(getattr(last, "id", 0) or 0)
    return topics[:limit]


async def fetch_topic_messages_limited(client: Any, entity: Any, topic_id: int, *, limit: int = 80) -> list[Any]:
    result: list[Any] = []
    async for message in client.iter_messages(entity, reply_to=topic_id, limit=limit):
        result.append(message)
    result.sort(key=lambda item: int(getattr(item, "id", 0) or 0))
    return result


async def scan_new_kvartira_objects(
    client: Any,
    known: KnownSources,
    *,
    limit: int,
    days: int,
    after_known: bool,
) -> list[NewObject]:
    entity = await client.get_entity("abhkvartira")
    max_known_topic = max(known.kvartira_topic_ids or {0})
    found: list[NewObject] = []
    for topic in await recent_forum_topics(client, entity, limit=limit):
        topic_id = int(getattr(topic, "id", 0) or 0)
        if topic_id <= 1:
            continue
        if after_known and topic_id <= max_known_topic:
            continue
        top_message_id = int(getattr(topic, "top_message", 0) or 0)
        if topic_id in known.kvartira_topic_ids or top_message_id in known.kvartira_message_ids:
            continue
        topic_title = clean_line(str(getattr(topic, "title", "") or ""))
        if topic_title.lower() == "general":
            continue
        thread_messages = await fetch_topic_messages_limited(client, entity, topic_id)
        if not thread_messages:
            continue
        recent_messages = [message for message in thread_messages if is_recent_enough(message, days)]
        if days > 0 and not recent_messages:
            continue
        text_candidates = [
            message
            for message in thread_messages
            if is_kvartira_object_message(str(getattr(message, "message", "") or ""))
        ]
        if not text_candidates:
            text_candidates = [
                message
                for message in thread_messages
                if str(getattr(message, "message", "") or "").strip()
                and not is_service_text(str(getattr(message, "message", "") or ""))
            ]
        if not text_candidates:
            continue
        canonical = max(
            text_candidates,
            key=lambda item: (topic_message_score(str(getattr(item, "message", "") or "")), int(getattr(item, "id", 0) or 0)),
        )
        message_id = int(getattr(canonical, "id", 0) or 0)
        if ("abhkvartira", message_id) in known.source_pairs:
            continue
        text = str(getattr(canonical, "message", "") or "")
        found.append(
            NewObject(
                kind="kvartira",
                title=object_title(text, fallback=topic_title or "новая квартира"),
                channel="abhkvartira",
                message_id=message_id,
                topic_id=topic_id,
                telegram_url=f"https://t.me/abhkvartira/{message_id}",
                published_at=message_date_iso(canonical),
                reason="тема форума похожа на карточку квартиры и её нет в catalog snapshot",
            )
        )
    found.sort(key=lambda item: (item.topic_id or 0, item.message_id))
    return found


async def scan_new_objects(client: Any, known: KnownSources, args: argparse.Namespace) -> list[NewObject]:
    if args.new_objects_limit <= 0:
        return []
    found: list[NewObject] = []
    found.extend(
        await scan_new_hotel_objects(
            client,
            known,
            limit=args.new_objects_limit,
            days=args.new_objects_days,
            after_known=args.new_objects_after_known,
        )
    )
    if args.scan_kvartira:
        found.extend(
            await scan_new_kvartira_objects(
                client,
                known,
                limit=args.new_objects_limit,
                days=args.new_objects_days,
                after_known=args.new_objects_after_known,
            )
        )
    return found


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
    new_objects: list[NewObject],
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
        f"Новых объектов: {len(new_objects)}",
        f"Текст: {text_count}, цены: {price_count}, медиа: {media_count}",
    ]
    if accepted:
        lines.append("Изменения приняты как новое базовое состояние.")
    if new_objects:
        lines.append("")
        lines.append("Новые объекты в Telegram:")
        for item in new_objects[:40]:
            topic_part = f", тема {item.topic_id}" if item.topic_id else ""
            date_part = f", {item.published_at}" if item.published_at else ""
            lines.append(
                f"- {item.title} — {item.channel}/{item.message_id}{topic_part}{date_part}; {item.telegram_url}"
            )
        if len(new_objects) > 40:
            lines.append(f"... и ещё {len(new_objects) - 40}")
        lines.append("")
        lines.append("Рекомендация: запустить обновление новых объектов или полный синк.")
    else:
        lines.append("Новых объектов не найдено.")
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


def write_targets(changes: list[Change], new_objects: list[NewObject]) -> None:
    hotel_ids = sorted({item.message_id for item in changes if item.kind == "hotel"})
    kv_topic_ids = sorted({int(item.topic_id) for item in changes if item.kind == "kvartira" and item.topic_id})
    kv_message_ids_without_topic = sorted(
        {item.message_id for item in changes if item.kind == "kvartira" and not item.topic_id}
    )
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "changed_total": len(changes),
        "new_objects_total": len(new_objects),
        "hotel_source_ids": hotel_ids,
        "kv_topic_ids": kv_topic_ids,
        "kv_message_ids_without_topic": kv_message_ids_without_topic,
        "items": [asdict(item) for item in changes],
        "new_objects": [asdict(item) for item in new_objects],
    }
    TARGETS_PATH.parent.mkdir(parents=True, exist_ok=True)
    TARGETS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


async def run(args: argparse.Namespace) -> int:
    load_env_files()
    api_id = int(os.getenv("TELEGRAM_API_ID", str(DEFAULT_API_ID)))
    api_hash = os.getenv("TELEGRAM_API_HASH", DEFAULT_API_HASH)
    session = os.getenv("TG_SESSION", str(ROOT / "tg_session"))
    items = load_watch_items(limit=args.limit)
    known_sources = load_known_sources()
    state = load_state()
    state_items: dict[str, Any] = state.setdefault("items", {})
    checked = 0
    baseline_added = 0
    changes: list[Change] = []
    new_objects: list[NewObject] = []
    errors: list[str] = []
    seen_keys: set[str] = set()
    entities: dict[str, Any] = {}

    async with connected_telegram_client(session, api_id, api_hash, receive_updates=False) as client:
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
        try:
            new_objects = await scan_new_objects(client, known_sources, args)
        except Exception as error:  # noqa: BLE001 - existing-post watch must still report
            errors.append(f"new-objects: {error}")
    stale_keys = sorted(set(state_items) - seen_keys)
    if args.accept_changes:
        for key in stale_keys:
            state_items.pop(key, None)

    state["last_checked_at"] = datetime.now(timezone.utc).isoformat()
    state["last_checked_total"] = checked
    state["last_changes_total"] = len(changes)
    state["last_new_objects_total"] = len(new_objects)
    if args.write_state:
        save_state(state)

    write_targets(changes, new_objects)
    report = render_report(
        checked=checked,
        baseline_added=baseline_added,
        changes=changes,
        new_objects=new_objects,
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
        "--new-objects-limit",
        type=int,
        default=env_int("TELEGRAM_NEW_OBJECTS_SCAN_LIMIT", DEFAULT_NEW_OBJECTS_LIMIT),
        help="Сколько последних сообщений/тем просматривать для поиска новых объектов (0 — выключить).",
    )
    parser.add_argument(
        "--new-objects-days",
        type=int,
        default=env_int("TELEGRAM_NEW_OBJECTS_SCAN_DAYS", DEFAULT_NEW_OBJECTS_DAYS),
        help="Считать новыми только сообщения за последние N дней (0 — без ограничения по дате).",
    )
    parser.add_argument(
        "--new-objects-scan-recent-all",
        dest="new_objects_after_known",
        action="store_false",
        help="Сканировать свежий диапазон целиком, а не только id после максимального известного.",
    )
    parser.add_argument(
        "--no-scan-kvartira",
        dest="scan_kvartira",
        action="store_false",
        help="Не проверять новые темы квартир в @abhkvartira.",
    )
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
    parser.set_defaults(
        write_state=True,
        new_objects_after_known=not env_bool("TELEGRAM_NEW_OBJECTS_SCAN_RECENT_ALL", False),
        scan_kvartira=not env_bool("TELEGRAM_NEW_OBJECTS_SKIP_KVARTIRA", False),
    )
    return parser


def main() -> int:
    load_env_files()
    args = build_parser().parse_args()
    return run_async_entrypoint(run(args), name="watch_telegram_updates", default_timeout=900)


if __name__ == "__main__":
    raise SystemExit(main())
