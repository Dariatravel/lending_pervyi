"""Read/write data/catalog-snapshot.json — site catalog without Postgres."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_PATH = ROOT / "data" / "catalog-snapshot.json"
SCHEMA_VERSION = 1
STORAGE_BUCKET = "abhazbereg-media"


def load_payload() -> dict[str, Any]:
    if not SNAPSHOT_PATH.exists():
        return {
            "generated_at": "",
            "schema_version": SCHEMA_VERSION,
            "source": "local",
            "listings_total": 0,
            "listings_hotels": 0,
            "listings_kvartira": 0,
            "listings": [],
        }
    return json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))


def load_listings() -> list[dict[str, Any]]:
    return list(load_payload().get("listings") or [])


def save_listings(listings: list[dict[str, Any]], *, source: str = "local-sync") -> None:
    hotels = sum(1 for row in listings if row.get("source_kind") == "hotel" and row.get("is_active", True))
    kv = sum(1 for row in listings if row.get("source_kind") == "kvartira" and row.get("is_active", True))
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "schema_version": SCHEMA_VERSION,
        "source": source,
        "listings_total": sum(1 for row in listings if row.get("is_active", True)),
        "listings_hotels": hotels,
        "listings_kvartira": kv,
        "listings": listings,
    }
    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def next_listing_id(listings: list[dict[str, Any]]) -> int:
    ids = [int(row.get("id") or 0) for row in listings]
    return max(ids, default=0) + 1


def _media_for_snapshot(media_rows: list[dict[str, Any]], listing_id: int) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for index, row in enumerate(media_rows, start=1):
        result.append(
            {
                "id": row.get("id") or (listing_id * 1000 + index),
                "media_role": row.get("media_role"),
                "sort_order": row.get("sort_order"),
                "mime_type": row.get("mime_type"),
                "source_url": row.get("source_url"),
                "storage_bucket": row.get("storage_bucket") or STORAGE_BUCKET,
                "storage_path": row.get("storage_path"),
                "public_url": row.get("public_url") or row.get("source_url"),
                "details": row.get("details") or {},
            }
        )
    return result


def build_listing_record(
    payload: dict[str, Any],
    media_rows: list[dict[str, Any]],
    listing_id: int,
) -> dict[str, Any]:
    listing = {k: v for k, v in payload.items() if k != "id"}
    listing["id"] = listing_id
    listing["is_active"] = True
    listing["media"] = _media_for_snapshot(media_rows, listing_id)
    return listing


def upsert_listing(listing: dict[str, Any]) -> dict[str, Any]:
    listings = load_listings()
    slug = str(listing.get("slug") or "").strip()
    listing_id = int(listing.get("id") or 0)
    replaced = False
    for index, row in enumerate(listings):
        if slug and row.get("slug") == slug:
            listings[index] = listing
            replaced = True
            break
        if listing_id and int(row.get("id") or 0) == listing_id:
            listings[index] = listing
            replaced = True
            break
    if not replaced:
        if not listing_id:
            listing["id"] = next_listing_id(listings)
        listings.append(listing)
    save_listings(listings)
    return listing


def patch_details(slug: str, details: dict[str, Any]) -> bool:
    listings = load_listings()
    changed = False
    for index, row in enumerate(listings):
        if row.get("slug") != slug:
            continue
        current = row.get("details") if isinstance(row.get("details"), dict) else {}
        merged = dict(current)
        merged.update(details)
        row["details"] = merged
        listings[index] = row
        changed = True
        break
    if changed:
        save_listings(listings)
    return changed


def update_filters(slug: str, filters: dict[str, list[str]]) -> bool:
    listings = load_listings()
    for index, row in enumerate(listings):
        if row.get("slug") != slug:
            continue
        details = row.get("details") if isinstance(row.get("details"), dict) else {}
        details["filters"] = filters
        row["details"] = details
        listings[index] = row
        save_listings(listings)
        return True
    return False


def deactivate_listing(slug: str) -> bool:
    listings = load_listings()
    for index, row in enumerate(listings):
        if row.get("slug") != slug:
            continue
        row["is_active"] = False
        listings[index] = row
        save_listings(listings)
        return True
    return False


def find_by_slug(slug: str) -> dict[str, Any] | None:
    for row in load_listings():
        if row.get("slug") == slug:
            return row
    return None


def listing_map_by_source() -> dict[tuple[str, int], dict[str, Any]]:
    result: dict[tuple[str, int], dict[str, Any]] = {}
    for row in load_listings():
        if row.get("is_active") is False:
            continue
        channel = str(row.get("source_channel") or "").lower().strip()
        message_id = int(row.get("source_message_id") or 0)
        topic_id = int(row.get("source_topic_id") or 0)
        if channel and message_id:
            result[(channel, message_id)] = row
        if channel == "abhkvartira" and topic_id:
            result[(channel, topic_id)] = row
    return result


def listings_by_kind(source_kind: str) -> list[dict[str, Any]]:
    return [
        row
        for row in load_listings()
        if row.get("source_kind") == source_kind and row.get("is_active", True)
    ]
