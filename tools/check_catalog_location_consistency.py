#!/usr/bin/env python3
"""Focused consistency check for catalog card city vs object page location."""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from rebuild_from_supabase import (  # noqa: E402
    CITY_MAP_LABELS,
    city_key_from_text,
    filter_city_values,
    listing_city_key,
)

SNAPSHOT_PATH = ROOT / "data" / "catalog-snapshot.json"
INDEX_PATH = ROOT / "index.html"


def parse_csv_ints(raw: str) -> set[int]:
    values: set[int] = set()
    for part in (raw or "").split(","):
        part = part.strip()
        if not part:
            continue
        values.add(int(part))
    return values


def parse_csv_strings(raw: str) -> set[str]:
    return {part.strip() for part in (raw or "").split(",") if part.strip()}


def strip_tags(value: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", value, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text)


def load_rows() -> list[dict[str, Any]]:
    payload = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    return list(payload.get("listings") or [])


def select_rows(args: argparse.Namespace) -> list[dict[str, Any]]:
    slugs = parse_csv_strings(args.slug)
    hotel_ids = parse_csv_ints(args.hotel_source_ids)
    kv_topic_ids = parse_csv_ints(args.kv_topic_ids)
    rows = [row for row in load_rows() if row.get("is_active", True)]
    if not (slugs or hotel_ids or kv_topic_ids or args.all):
        raise SystemExit("Укажите --slug, --hotel-source-ids, --kv-topic-ids или --all.")

    selected: list[dict[str, Any]] = []
    for row in rows:
        slug = str(row.get("slug") or "")
        kind = str(row.get("source_kind") or "")
        if slugs and slug in slugs:
            selected.append(row)
            continue
        if hotel_ids and kind == "hotel" and int(row.get("source_message_id") or 0) in hotel_ids:
            selected.append(row)
            continue
        if kv_topic_ids and kind == "kvartira" and int(row.get("source_topic_id") or 0) in kv_topic_ids:
            selected.append(row)
            continue
        if args.all:
            selected.append(row)
    return selected


def page_path(row: dict[str, Any]) -> Path:
    folder = "hotels" if row.get("source_kind") == "hotel" else "kvartira"
    return ROOT / folder / str(row.get("slug") or "") / "index.html"


def page_city_key(row: dict[str, Any]) -> str:
    path = page_path(row)
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8")
    location_match = re.search(r'<p class="location">([\s\S]*?)</p>', text)
    if location_match:
        first_line = strip_tags(location_match.group(1)).splitlines()[0]
        key = city_key_from_text(first_line)
        if key:
            return key
    rating_match = re.search(r'<strong class="hotel-card__rating-summary">([\s\S]*?)</strong>', text)
    if rating_match:
        return city_key_from_text(strip_tags(rating_match.group(1)))
    return ""


def index_card_html(slug: str) -> str:
    text = INDEX_PATH.read_text(encoding="utf-8")
    for match in re.finditer(r'<a class="catalog-card"(?P<attrs>[^>]*)>[\s\S]*?</a>', text):
        href_match = re.search(r'href="([^"]+)"', match.group("attrs"))
        if not href_match:
            continue
        path = urlparse(html.unescape(href_match.group(1))).path.strip("/")
        parts = path.split("/")
        if len(parts) >= 2 and parts[-1] == slug and parts[-2] in {"hotels", "kvartira"}:
            return match.group(0)
    return ""


def index_map_city_key(row: dict[str, Any]) -> str:
    card = index_card_html(str(row.get("slug") or ""))
    if not card:
        return ""
    match = re.search(r'data-map-city="([^"]*)"', card)
    return html.unescape(match.group(1)).strip() if match else ""


def check_row(row: dict[str, Any]) -> tuple[list[str], list[str]]:
    slug = str(row.get("slug") or "")
    expected = listing_city_key(row)
    page_key = page_city_key(row)
    card_key = index_map_city_key(row)
    filters = (row.get("details") or {}).get("filters") or {}
    filter_cities = filter_city_values(filters)
    errors: list[str] = []
    warnings: list[str] = []

    if not expected:
        warnings.append(
            f"{slug}: не удалось однозначно определить город из snapshot city/location_text"
        )
    if expected and page_key and page_key != expected:
        errors.append(
            f"{slug}: страница показывает {CITY_MAP_LABELS.get(page_key, page_key)}, "
            f"snapshot ожидает {CITY_MAP_LABELS.get(expected, expected)}"
        )
    if expected and card_key and card_key != expected:
        errors.append(
            f"{slug}: карточка каталога показывает {CITY_MAP_LABELS.get(card_key, card_key)}, "
            f"snapshot ожидает {CITY_MAP_LABELS.get(expected, expected)}"
        )
    if page_key and card_key and page_key != card_key:
        errors.append(
            f"{slug}: страница и карточка каталога показывают разные города "
            f"({CITY_MAP_LABELS.get(page_key, page_key)} / {CITY_MAP_LABELS.get(card_key, card_key)})"
        )
    if expected and filter_cities and expected not in filter_cities:
        errors.append(
            f"{slug}: data-filter-city из Google Sheet не содержит фактический город "
            f"{expected} (сейчас: {'|'.join(filter_cities)})"
        )
    if not page_key:
        warnings.append(f"{slug}: не удалось прочитать город на странице объекта")
    if not card_key:
        warnings.append(f"{slug}: не удалось прочитать data-map-city в карточке каталога")
    return errors, warnings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slug", default="", help="Slug через запятую.")
    parser.add_argument("--hotel-source-ids", default="", help="source_message_id отелей через запятую.")
    parser.add_argument("--kv-topic-ids", default="", help="source_topic_id квартир через запятую.")
    parser.add_argument("--all", action="store_true", help="Проверить все активные объекты.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    rows = select_rows(args)
    if not rows:
        print("catalog_location_consistency: нет подходящих объектов")
        return 1

    errors: list[str] = []
    warnings: list[str] = []
    for row in rows:
        row_errors, row_warnings = check_row(row)
        errors.extend(row_errors)
        warnings.extend(row_warnings)

    if errors:
        print("catalog_location_consistency: FAIL")
        for issue in errors:
            print(f"- ОШИБКА: {issue}")
        for issue in warnings:
            print(f"- ПРЕДУПРЕЖДЕНИЕ: {issue}")
        return 1

    if warnings:
        print(f"catalog_location_consistency: OK_WITH_WARNINGS ({len(rows)} объект(ов))")
        for issue in warnings:
            print(f"- ПРЕДУПРЕЖДЕНИЕ: {issue}")
        return 0

    print(f"catalog_location_consistency: OK ({len(rows)} объект(ов))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
