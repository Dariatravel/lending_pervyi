from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import requests
from google.oauth2 import service_account
from googleapiclient.discovery import build


ROOT = Path("/Users/darya_botova/Documents/New project")
ENV_PATH = ROOT / ".env.supabase.local"
REPORT_PATH = ROOT / "output" / "relink_source_ids_report.txt"

SPREADSHEET_ID = "135fxeZX5OE30rH3Sg5KWpTR4VuhBntCzGrTk0WcdTBY"
SHEET_NAME = "СОЦСЕТИ"
RANGE = f"{SHEET_NAME}!A2:I"
COL_TITLE = 0
COL_TG_LINK = 8

ALLOWED_CHANNELS = {"abhazbooking", "abhkvartira"}
REMOVE_HOTEL_TITLES = ("коста де ора", "асман", "лаванда")


def load_env(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
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
    cleaned = str(value or "").lower().replace("ё", "е")
    cleaned = re.sub(r"[\"“”«»]", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def extract_core_name(value: str) -> str:
    text = str(value or "")
    quoted = re.search(r'[\"«](.+?)[\"»]', text)
    core = quoted.group(1) if quoted else text
    return title_key(core)


def should_skip_by_title(title: str, source_kind: str) -> bool:
    if source_kind != "hotel":
        return False
    key = title_key(title)
    return any(token in key for token in REMOVE_HOTEL_TITLES)


def patch_listing(base: str, key: str, listing_id: int, payload: dict[str, Any]) -> None:
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }
    response = requests.patch(
        f"{base}/rest/v1/listings",
        headers=headers,
        params={"id": f"eq.{listing_id}"},
        json=payload,
        timeout=120,
    )
    response.raise_for_status()


def main() -> None:
    env = load_env(ENV_PATH)
    base = env["SUPABASE_URL"].rstrip("/")
    key = env["SUPABASE_SERVICE_ROLE_KEY"]
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}

    credentials_path = pick_google_credentials_path()
    sheet_rows = fetch_sheet_rows(credentials_path)

    rows = requests.get(
        f"{base}/rest/v1/listings",
        headers=headers,
        params={
            "select": "id,source_kind,source_channel,source_message_id,source_topic_id,title,slug,is_active",
            "is_active": "eq.true",
            "limit": "5000",
        },
        timeout=120,
    ).json()

    by_key = {
        (str(row.get("source_channel") or "").lower().strip(), int(row.get("source_message_id") or 0)): row
        for row in rows
        if row.get("source_channel") and row.get("source_message_id")
    }
    by_topic = {
        int(row.get("source_topic_id")): row
        for row in rows
        if row.get("source_kind") == "kvartira" and row.get("source_topic_id")
    }
    by_title: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        source_kind = str(row.get("source_kind") or "")
        tk = title_key(str(row.get("title") or ""))
        if source_kind and tk:
            by_title.setdefault((source_kind, tk), []).append(row)

    relinked: list[str] = []
    unresolved: list[str] = []
    unparsed: list[str] = []

    for i, sheet_row in enumerate(sheet_rows, start=2):
        raw_link = get_cell(sheet_row, COL_TG_LINK)
        if not raw_link:
            continue
        parsed = parse_telegram_link(raw_link)
        if not parsed:
            unparsed.append(f"row {i}: {raw_link}")
            continue
        channel, message_id, topic_id = parsed
        if channel not in ALLOWED_CHANNELS:
            continue
        source_kind = "kvartira" if channel == "abhkvartira" else "hotel"
        title = get_cell(sheet_row, COL_TITLE)
        if should_skip_by_title(title, source_kind):
            continue
        if (channel, message_id) in by_key:
            continue

        candidate = None
        if source_kind == "kvartira" and topic_id and topic_id in by_topic:
            candidate = by_topic[topic_id]
        if candidate is None:
            matches = by_title.get((source_kind, title_key(title)), [])
            if len(matches) == 1:
                candidate = matches[0]
        if candidate is None:
            core = extract_core_name(title)
            if core:
                fuzzy = [
                    row for row in rows
                    if str(row.get("source_kind") or "") == source_kind
                    and core
                    and core in title_key(str(row.get("title") or ""))
                    and abs(int(row.get("source_message_id") or 0) - message_id) <= 30
                ]
                if len(fuzzy) == 1:
                    candidate = fuzzy[0]

        if candidate is None:
            unresolved.append(f"row {i}: {title} | {raw_link}")
            continue

        payload = {
            "source_channel": channel,
            "source_message_id": message_id,
            "telegram_url": f"https://t.me/{channel}/{message_id}",
        }
        if source_kind == "kvartira" and topic_id:
            payload["source_topic_id"] = topic_id
        patch_listing(base, key, int(candidate["id"]), payload)
        relinked.append(
            f'row {i}: {candidate.get("slug")} | {candidate.get("title")} | {candidate.get("source_channel")}/{candidate.get("source_message_id")} -> {channel}/{message_id}'
        )

        by_key[(channel, message_id)] = candidate

    lines: list[str] = []
    lines.append("Relink source_message_id по ссылкам Telegram-каталог")
    lines.append("")
    lines.append(f"Всего строк таблицы: {len(sheet_rows)}")
    lines.append(f"Перепривязано карточек: {len(relinked)}")
    lines.append(f"Не удалось распознать ссылку: {len(unparsed)}")
    lines.append(f"Не удалось сопоставить карточку: {len(unresolved)}")
    if relinked:
        lines.append("")
        lines.append("Перепривязанные карточки:")
        for line in relinked:
            lines.append(f"- {line}")
    if unresolved:
        lines.append("")
        lines.append("Не сопоставлены:")
        for line in unresolved:
            lines.append(f"- {line}")
    if unparsed:
        lines.append("")
        lines.append("Нераспознанные ссылки:")
        for line in unparsed:
            lines.append(f"- {line}")

    text = "\n".join(lines)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
