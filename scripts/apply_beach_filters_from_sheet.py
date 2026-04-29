from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import requests
from google.oauth2 import service_account
from googleapiclient.discovery import build


ROOT = Path("/Users/darya_botova/Documents/New project")
ENV_PATH = ROOT / ".env.supabase.local"
SPREADSHEET_ID = "135fxeZX5OE30rH3Sg5KWpTR4VuhBntCzGrTk0WcdTBY"
SHEET_NAME = "СОЦСЕТИ"
RANGE = f"{SHEET_NAME}!A2:BK"

# Индексы колонок (0-based) из вкладки СОЦСЕТИ:
# AD=29, AE=30, AF=31, I=8
COL_TG_LINK = 8
COL_BEACH_AD = 29
COL_BEACH_AE = 30
COL_BEACH_AF = 31

PINE = "pine-pebble-ldzaa-pitsunda"
SAND_LDZAA = "sand-ldzaa"
SAND_SUKHUM = "sand-sukhum"
PITSUNDA_BAY = "pitsunda-bay-mixed"
PEBBLE = "pebble"


def load_env(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    if not path.exists():
        return result
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip()
    return result


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


def parse_telegram_link(link: str) -> tuple[str, int] | None:
    if not link:
        return None
    link = link.strip()
    # Поддержка двух форматов:
    # 1) t.me/channel/1234
    # 2) t.me/channel/topic_id/1234  (форумные темы, где нужен последний id)
    match = re.search(r"(?:https?://)?t\.me/(?:s/)?([A-Za-z0-9_]+)/(?:[0-9]+/)?([0-9]+)", link)
    if not match:
        return None
    channel = match.group(1).lower()
    message_id = int(match.group(2))
    return channel, message_id


def has_value(value: str) -> bool:
    return bool(str(value or "").strip())


def infer_beach_filters(ad: str, ae: str, af: str) -> list[str]:
    values: list[str] = []
    ad_v = str(ad or "").strip()
    ae_v = str(ae or "").strip()
    af_v = str(af or "").strip()

    has_any_source = any([has_value(ad_v), has_value(ae_v), has_value(af_v)])

    if has_value(ad_v):
        values.append(PINE)

    if has_value(ae_v):
        low = ae_v.lower()
        if "песок/мелкая галька" in low or "мелкая галька/песок" in low:
            values.append(PITSUNDA_BAY)
        elif "песок" in low and "мелк" not in low:
            values.append(SAND_LDZAA)

    if has_value(af_v):
        values.append(SAND_SUKHUM)

    if not has_any_source:
        values.append(PEBBLE)

    # Уникальные, в исходном порядке
    return list(dict.fromkeys(values))


def fetch_sheet_rows(credentials_path: Path) -> list[list[str]]:
    scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
    creds = service_account.Credentials.from_service_account_file(str(credentials_path), scopes=scopes)
    service = build("sheets", "v4", credentials=creds, cache_discovery=False)
    response = service.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range=RANGE).execute()
    return response.get("values", [])


def get_cell(row: list[str], index: int) -> str:
    if index < len(row):
        return row[index]
    return ""


def fetch_listings(supabase_url: str, service_role: str) -> list[dict[str, Any]]:
    headers = {
        "apikey": service_role,
        "Authorization": f"Bearer {service_role}",
    }
    params = {
        "select": "id,source_channel,source_message_id,details",
        "limit": "5000",
    }
    response = requests.get(f"{supabase_url}/rest/v1/listings", headers=headers, params=params, timeout=120)
    response.raise_for_status()
    return response.json()


def patch_listing_details(supabase_url: str, service_role: str, listing_id: int, details: dict[str, Any]) -> None:
    headers = {
        "apikey": service_role,
        "Authorization": f"Bearer {service_role}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }
    params = {"id": f"eq.{listing_id}"}
    response = requests.patch(
        f"{supabase_url}/rest/v1/listings",
        headers=headers,
        params=params,
        data=json.dumps({"details": details}, ensure_ascii=False).encode("utf-8"),
        timeout=120,
    )
    response.raise_for_status()


def main() -> None:
    env = load_env(ENV_PATH)
    supabase_url = env.get("SUPABASE_URL", "").rstrip("/")
    service_role = env.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not supabase_url or not service_role:
        raise RuntimeError("В .env.supabase.local должны быть SUPABASE_URL и SUPABASE_SERVICE_ROLE_KEY.")

    credentials_path = pick_google_credentials_path()
    sheet_rows = fetch_sheet_rows(credentials_path)

    # Ключ: (channel, message_id) -> beach filters
    sheet_filters: dict[tuple[str, int], list[str]] = {}
    rows_without_link = 0
    rows_unparsed_link = 0
    for row in sheet_rows:
        tg_link = get_cell(row, COL_TG_LINK)
        parsed = parse_telegram_link(tg_link)
        if not has_value(tg_link):
            rows_without_link += 1
            continue
        if not parsed:
            rows_unparsed_link += 1
            continue
        ad = get_cell(row, COL_BEACH_AD)
        ae = get_cell(row, COL_BEACH_AE)
        af = get_cell(row, COL_BEACH_AF)
        sheet_filters[parsed] = infer_beach_filters(ad, ae, af)

    listings = fetch_listings(supabase_url, service_role)
    listing_map: dict[tuple[str, int], dict[str, Any]] = {}
    for row in listings:
        channel = str(row.get("source_channel") or "").lower()
        message_id = int(row.get("source_message_id") or 0)
        if channel and message_id:
            listing_map[(channel, message_id)] = row

    updated = 0
    unchanged = 0
    not_found = 0

    for key, new_beach_filters in sheet_filters.items():
        listing = listing_map.get(key)
        if not listing:
            not_found += 1
            continue
        details = listing.get("details") or {}
        if not isinstance(details, dict):
            details = {}
        filters = details.get("filters") or {}
        if not isinstance(filters, dict):
            filters = {}

        old_values = filters.get("beach") or []
        if isinstance(old_values, str):
            old_values = [v.strip() for v in old_values.split("|") if v.strip()]
        if not isinstance(old_values, list):
            old_values = []

        if old_values == new_beach_filters:
            unchanged += 1
            continue

        filters["beach"] = new_beach_filters
        details["filters"] = filters
        patch_listing_details(supabase_url, service_role, int(listing["id"]), details)
        updated += 1

    print("Готово.")
    print(f"Строк в СОЦСЕТИ: {len(sheet_rows)}")
    print(f"Разобрано ссылок Telegram: {len(sheet_filters)}")
    print(f"Без ссылки Telegram: {rows_without_link}")
    print(f"Ссылка не распознана: {rows_unparsed_link}")
    print(f"Обновлено объектов в Supabase: {updated}")
    print(f"Без изменений: {unchanged}")
    print(f"Не найдено в Supabase по channel+message_id: {not_found}")


if __name__ == "__main__":
    main()
