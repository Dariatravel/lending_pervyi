from __future__ import annotations

import argparse
import asyncio
import os
import re
from pathlib import Path
from typing import Any

from google.oauth2 import service_account
from googleapiclient.discovery import build
from telethon import TelegramClient

from sync_catalog_from_telegram import (
    API_HASH,
    API_ID,
    CUTOFF_DATE,
    ENV_FILE,
    SESSION,
    SupabaseClient,
    cleanup_removed_listing,
    materialize_object,
    normalize_title,
    parse_post,
)


ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "output" / "backfill_missing_report.txt"
SPREADSHEET_ID = "135fxeZX5OE30rH3Sg5KWpTR4VuhBntCzGrTk0WcdTBY"
SHEET_NAME = "СОЦСЕТИ"
RANGE = f"{SHEET_NAME}!A2:I"

COL_TITLE = 0  # A
COL_TG_LINK = 8  # I

ALLOWED_CHANNELS = {"abhazbooking", "abhkvartira"}
REMOVE_HOTEL_TITLES = ("коста де ора", "асман", "лаванда")


def load_env(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.exists():
        return data
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip()
    return data


def pick_google_credentials_path() -> Path:
    candidates = [
        os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip(),
        str(ROOT / "google-service-account.json"),
        "/Users/darya_botova/Downloads/sonorous-bounty-488706-q9-32a19387de8d.json",
        "/Users/darya_botova/Documents/ПОДБОРКИ/telegram_export/credentials.json",
    ]
    for value in candidates:
        if not value:
            continue
        path = Path(value)
        if path.exists():
            return path
    raise FileNotFoundError("Не найден JSON service account для Google Sheets.")


def fetch_sheet_rows(credentials_path: Path) -> list[list[str]]:
    scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
    creds = service_account.Credentials.from_service_account_file(str(credentials_path), scopes=scopes)
    service = build("sheets", "v4", credentials=creds, cache_discovery=False)
    response = service.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range=RANGE).execute()
    return response.get("values", [])


def get_cell(row: list[str], idx: int) -> str:
    if idx < len(row):
        return str(row[idx] or "").strip()
    return ""


def parse_telegram_link(link: str) -> tuple[str, int, int | None] | None:
    value = str(link or "").strip()
    if not value:
        return None
    match = re.search(r"(?:https?://)?t\.me/(?:s/)?([A-Za-z0-9_]+)/(?:(\d+)/)?(\d+)", value)
    if not match:
        return None
    channel = match.group(1).lower()
    topic_id = int(match.group(2)) if match.group(2) else None
    message_id = int(match.group(3))
    return channel, message_id, topic_id


def title_key(value: str) -> str:
    return normalize_title(value).strip().lower()


def normalize_tg_link(raw: str) -> str:
    s = raw.strip().lower()
    for prefix in ("https://", "http://"):
        if s.startswith(prefix):
            s = s[len(prefix) :]
    s = s.replace("telegram.me/", "t.me/")
    if "t.me/" in s and not s.startswith("t.me/"):
        idx = s.index("t.me/")
        s = s[idx:]
    s = s.split("?")[0].split("#")[0].strip()
    return s


def load_only_links_file(path: Path) -> set[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    out: set[str] = set()
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        out.add(normalize_tg_link(line))
    return out


def should_remove_hotel(title: str, source_kind: str) -> bool:
    if source_kind != "hotel":
        return False
    lowered = title_key(title)
    return any(keyword in lowered for keyword in REMOVE_HOTEL_TITLES)


def extract_topic_id_from_message(message: Any) -> int | None:
    reply_to = getattr(message, "reply_to", None)
    if reply_to is None:
        return None
    return (
        getattr(reply_to, "reply_to_top_id", None)
        or getattr(reply_to, "top_msg_id", None)
        or None
    )


async def collect_group_media(client: TelegramClient, entity: Any, canonical: Any) -> list[Any]:
    if getattr(canonical, "grouped_id", None):
        grouped_id = canonical.grouped_id
        left = max(1, int(canonical.id) - 80)
        right = int(canonical.id) + 80
        nearby_ids = list(range(left, right + 1))
        nearby = await client.get_messages(entity, ids=nearby_ids)
        media = [item for item in (nearby or []) if item and getattr(item, "grouped_id", None) == grouped_id and getattr(item, "media", None)]
        media.sort(key=lambda item: item.id)
        if media:
            return media
    if getattr(canonical, "media", None):
        return [canonical]
    return []


async def resolve_object_from_link(
    client: TelegramClient,
    channel: str,
    message_id: int,
    topic_id_from_link: int | None,
    sheet_title: str,
    *,
    ignore_cutoff_date: bool = False,
) -> dict[str, Any] | None:
    entity = await client.get_entity(channel)
    message = await client.get_messages(entity, ids=message_id)
    if not message:
        return None
    if not message.date:
        return None
    if not ignore_cutoff_date and message.date.date().isoformat() < CUTOFF_DATE:
        return None

    media_messages = await collect_group_media(client, entity, message)
    canonical = message
    if not (canonical.message or "").strip():
        for item in media_messages:
            if (item.message or "").strip():
                canonical = item
                break

    parsed = parse_post(canonical.message or "")
    if not parsed.get("title"):
        parsed["title"] = sheet_title.strip()

    source_kind = "kvartira" if channel == "abhkvartira" else "hotel"
    topic_id = topic_id_from_link or (extract_topic_id_from_message(message) if source_kind == "kvartira" else None)

    return {
        "source_kind": source_kind,
        "canonical": canonical,
        "media_messages": media_messages,
        "published_at": canonical.date.date().isoformat(),
        "telegram_url": f"https://t.me/{channel}/{canonical.id}",
        "parsed": parsed,
        "topic_id": topic_id,
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="Дозагрузка объектов по ссылкам из «СОЦСЕТИ».")
    parser.add_argument(
        "--ignore-cutoff-date",
        action="store_true",
        help="Не отбрасывать посты с датой раньше CUTOFF_DATE (точечное восстановление по списку).",
    )
    parser.add_argument(
        "--only-links-file",
        type=Path,
        default=None,
        help="Обрабатывать только строки таблицы, чья ссылка совпадает с URL из файла (по одному на строку).",
    )
    args = parser.parse_args()
    only_set: set[str] | None = None
    if args.only_links_file:
        if not args.only_links_file.is_file():
            raise FileNotFoundError(f"Файл не найден: {args.only_links_file}")
        only_set = load_only_links_file(args.only_links_file)
        if not only_set:
            raise ValueError("В --only-links-file нет ни одной ссылки (пустой или только комментарии).")

    env = load_env(ENV_FILE)
    supabase_url = env.get("SUPABASE_URL", "").rstrip("/")
    service_role = env.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not supabase_url or not service_role:
        raise RuntimeError("В .env.supabase.local должны быть SUPABASE_URL и SUPABASE_SERVICE_ROLE_KEY")

    credentials_path = pick_google_credentials_path()
    sheet_rows = fetch_sheet_rows(credentials_path)

    supa = SupabaseClient(url=supabase_url, service_key=service_role)
    existing = supa.fetch_listings()

    slug_pool = {str(row.get("slug") or "").strip() for row in existing if row.get("slug")}
    existing_by_key = {
        (str(row.get("source_channel") or "").lower().strip(), int(row.get("source_message_id") or 0)): row
        for row in existing
        if row.get("source_channel") and row.get("source_message_id")
    }
    existing_kv_by_topic = {
        int(row.get("source_topic_id")): row
        for row in existing
        if row.get("source_kind") == "kvartira" and row.get("source_topic_id")
    }
    existing_by_title: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in existing:
        source_kind = str(row.get("source_kind") or "")
        key = title_key(str(row.get("title") or ""))
        if source_kind and key:
            existing_by_title.setdefault((source_kind, key), []).append(row)

    removed: list[str] = []
    if only_set is None:
        for row in list(existing):
            if should_remove_hotel(str(row.get("title") or ""), str(row.get("source_kind") or "")):
                cleanup_removed_listing(str(row.get("source_kind") or ""), row, supa)
                removed.append(f'{row.get("slug")} | {row.get("title")}')
                key = (str(row.get("source_channel") or "").lower().strip(), int(row.get("source_message_id") or 0))
                existing_by_key.pop(key, None)

    pending: list[dict[str, Any]] = []
    unparsed_links: list[str] = []
    ignored_channels: list[str] = []

    for idx, row in enumerate(sheet_rows, start=2):
        raw_link = get_cell(row, COL_TG_LINK)
        if not raw_link:
            continue
        if only_set is not None and normalize_tg_link(raw_link) not in only_set:
            continue
        parsed_link = parse_telegram_link(raw_link)
        if not parsed_link:
            unparsed_links.append(f"row {idx}: {raw_link}")
            continue
        channel, message_id, topic_id = parsed_link
        if channel not in ALLOWED_CHANNELS:
            ignored_channels.append(f"row {idx}: {raw_link}")
            continue
        if (channel, message_id) in existing_by_key:
            continue
        title = get_cell(row, COL_TITLE)
        source_kind = "kvartira" if channel == "abhkvartira" else "hotel"
        if should_remove_hotel(title, source_kind):
            continue
        pending.append(
            {
                "row": idx,
                "title": title,
                "channel": channel,
                "message_id": message_id,
                "topic_id": topic_id,
                "raw_link": raw_link,
                "source_kind": source_kind,
            }
        )

    client = TelegramClient(SESSION, API_ID, API_HASH, receive_updates=False)
    await client.connect()

    added: list[str] = []
    updated_existing: list[str] = []
    failed: list[str] = []

    for item in pending:
        object_data = await resolve_object_from_link(
            client,
            item["channel"],
            item["message_id"],
            item["topic_id"],
            item["title"],
            ignore_cutoff_date=args.ignore_cutoff_date,
        )
        if not object_data:
            suffix = ""
            if not args.ignore_cutoff_date:
                suffix = f"/оно старше {CUTOFF_DATE}"
            failed.append(f'row {item["row"]}: {item["raw_link"]} | не удалось получить сообщение{suffix}')
            continue

        existing_listing = None
        canonical_message_id = int(object_data["canonical"].id)

        # Частый кейс Telegram-альбома: ссылка в таблице указывает на сообщение без текста,
        # а подпись и "канонический" текст объекта находятся в соседнем сообщении той же группы.
        # В таком случае materialize_object использует canonical.id, поэтому сначала ищем
        # существующую запись именно по canonical message id.
        existing_listing = existing_by_key.get((item["channel"], canonical_message_id))

        if item["source_kind"] == "kvartira":
            topic_id = object_data.get("topic_id")
            if topic_id:
                existing_listing = existing_listing or existing_kv_by_topic.get(int(topic_id))

        if existing_listing is None:
            key = (item["source_kind"], title_key(item["title"] or object_data["parsed"].get("title", "")))
            candidates = existing_by_title.get(key, [])
            if len(candidates) == 1:
                existing_listing = candidates[0]

        try:
            result = await materialize_object(client, supa, existing_listing, object_data, slug_pool)
        except Exception as error:  # noqa: BLE001
            failed.append(f'row {item["row"]}: {item["raw_link"]} | ошибка materialize: {error}')
            continue

        if existing_listing:
            updated_existing.append(f'{result["slug"]} | {result["title"]} | row {item["row"]}')
        else:
            added.append(f'{result["slug"]} | {result["title"]} | row {item["row"]}')

    await client.disconnect()

    report_lines: list[str] = []
    report_lines.append("Backfill недостающих объектов из СОЦСЕТИ → Supabase/сайт")
    report_lines.append("")
    if args.only_links_file:
        report_lines.append(f"Режим: только ссылки из {args.only_links_file}")
    if args.ignore_cutoff_date:
        report_lines.append(f"Игнор даты поста до CUTOFF_DATE={CUTOFF_DATE}: да")
    report_lines.append("")
    report_lines.append(f"Строк в таблице: {len(sheet_rows)}")
    report_lines.append(f"Удалено по правилу (КОСТА ДЕ ОРА / АСМАН / ЛАВАНДА): {len(removed)}")
    report_lines.append(f"Кандидатов на дозагрузку: {len(pending)}")
    report_lines.append(f"Добавлено новых: {len(added)}")
    report_lines.append(f"Обновлено существующих (по topic/title fallback): {len(updated_existing)}")
    report_lines.append(f"Ошибок: {len(failed)}")
    report_lines.append(f"Нераспознанных ссылок: {len(unparsed_links)}")
    report_lines.append(f"Игнорировано ссылок с чужими каналами: {len(ignored_channels)}")

    if removed:
        report_lines.append("")
        report_lines.append("Удалено с сайта:")
        for line in removed:
            report_lines.append(f"- {line}")

    if added:
        report_lines.append("")
        report_lines.append("Добавлены:")
        for line in added:
            report_lines.append(f"- {line}")

    if updated_existing:
        report_lines.append("")
        report_lines.append("Обновлены существующие:")
        for line in updated_existing:
            report_lines.append(f"- {line}")

    if failed:
        report_lines.append("")
        report_lines.append("Ошибки:")
        for line in failed:
            report_lines.append(f"- {line}")

    if unparsed_links:
        report_lines.append("")
        report_lines.append("Нераспознанные ссылки:")
        for line in unparsed_links:
            report_lines.append(f"- {line}")

    if ignored_channels:
        report_lines.append("")
        report_lines.append("Ссылки с неподдерживаемыми каналами:")
        for line in ignored_channels:
            report_lines.append(f"- {line}")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(report_lines), encoding="utf-8")
    print("\n".join(report_lines))


if __name__ == "__main__":
    asyncio.run(main())
