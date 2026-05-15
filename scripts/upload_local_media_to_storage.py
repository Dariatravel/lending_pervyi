#!/usr/bin/env python3
"""
Залить в Supabase Storage файлы медиа, которые уже есть в репозитории под media/…,
и прописать в listing_media (и listings.cover_url для карточки) публичный URL вида:
  https://<project>.supabase.co/storage/v1/object/public/site-media/...

Нужно, когда в БД указаны только относительные пути `/media/cards/foo.jpg`,
а объектов физически нет в bucket — главная сайта их не находит после деплоя.

Если локального файла нет → строка попадает в отчёт `need_telegram` (нужен sync из Telegram).

  python3 scripts/upload_local_media_to_storage.py --dry-run
  python3 scripts/upload_local_media_to_storage.py

После успешного прогона: `python3 scripts/rebuild_from_supabase.py`, затем commit/push `index.html` и страниц объектов при необходимости.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import time
from pathlib import Path
from urllib.parse import quote

import requests

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env.supabase.local"
DEFAULT_BUCKET = "site-media"


def load_env(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.is_file():
        return data
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        data[k.strip()] = v.strip()
    return data


def public_url(sb_url: str, bucket: str, storage_path: str) -> str:
    encoded = "/".join(quote(part, safe="") for part in storage_path.split("/"))
    return f"{sb_url.rstrip('/')}/storage/v1/object/public/{bucket}/{encoded}"


def exists_on_cdn(sb_url: str, bucket: str, storage_path: str) -> bool:
    url = public_url(sb_url, bucket, storage_path)
    try:
        r = requests.head(url, timeout=25, allow_redirects=True)
        return r.status_code == 200
    except requests.RequestException:
        return False


def upload_local(
    session: requests.Session, sb_url: str, bucket: str, storage_path: str, local_file: Path, mime: str
) -> str:
    encoded = "/".join(quote(part, safe="") for part in storage_path.split("/"))
    post_url = f"{sb_url.rstrip('/')}/storage/v1/object/{bucket}/{encoded}"
    data = local_file.read_bytes()
    headers = {"Content-Type": mime, "x-upsert": "true"}
    last: Exception | None = None
    for attempt in range(5):
        try:
            r = session.post(post_url, headers=headers, data=data, timeout=600)
            r.raise_for_status()
            return public_url(sb_url, bucket, storage_path)
        except Exception as err:  # noqa: BLE001
            last = err
            time.sleep(1 + attempt)
    raise RuntimeError(f"Не удалось загрузить {storage_path}: {last}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="Только счётчики и need_telegram, без записи.")
    ap.add_argument(
        "--verbose",
        action="store_true",
        help="При --dry-run печатать каждый файл; иначе только итоговый JSON.",
    )
    args = ap.parse_args()

    env = load_env(ENV_PATH)
    sb_url = env.get("SUPABASE_URL", "").rstrip("/")
    key = env.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not sb_url or not key:
        print("Нужны SUPABASE_URL и SUPABASE_SERVICE_ROLE_KEY в .env.supabase.local", file=sys.stderr)
        return 1

    headers = {"apikey": key, "Authorization": f"Bearer {key}", "Prefer": "return=representation"}
    sess = requests.Session()
    sess.headers.update(headers)

    all_rows: list[dict] = []
    offset = 0
    page = 800
    while True:
        r = sess.get(
            f"{sb_url}/rest/v1/listing_media",
            params={
                "select": "id,listing_id,media_role,mime_type,public_url,storage_path,storage_bucket",
                "limit": str(page),
                "offset": str(offset),
                "order": "id.asc",
            },
            timeout=120,
        )
        r.raise_for_status()
        chunk = r.json()
        if not chunk:
            break
        all_rows.extend(chunk)
        if len(chunk) < page:
            break
        offset += page

    candidates = []
    for row in all_rows:
        pu = (row.get("public_url") or "").strip()
        if not pu.startswith("/media/"):
            continue
        rel = pu.lstrip("/")
        lp = ROOT / Path(rel.replace("\\", "/"))
        sp = str(row.get("storage_path") or "").strip().replace("\\", "/")
        if not sp:
            sp = rel.replace("media/", "", 1) if rel.startswith("media/") else rel
        bucket = str(row.get("storage_bucket") or DEFAULT_BUCKET).strip() or DEFAULT_BUCKET
        candidates.append((row, lp, sp, bucket))

    uploaded = 0
    patched_db = 0
    skipped_already = 0
    need_telegram: list[tuple[int, str, str]] = []

    cover_by_listing: dict[int, str] = {}

    for row, local_path, storage_path, bucket in candidates:
        mid = int(row["id"])
        lid = int(row["listing_id"])
        role = (row.get("media_role") or "").strip()

        mime = (
            row.get("mime_type")
            or (
                mimetypes.guess_type(local_path.name)[0]
                if local_path.is_file()
                else mimetypes.guess_type(storage_path.split("/")[-1])[0]
            )
            or "image/jpeg"
        )
        new_pub = public_url(sb_url, bucket, storage_path)
        on_cdn = False if args.dry_run else exists_on_cdn(sb_url, bucket, storage_path)

        if local_path.is_file():
            if not on_cdn and not args.dry_run:
                new_pub = upload_local(sess, sb_url, bucket, storage_path, local_path, str(mime))
                uploaded += 1
            elif on_cdn and not args.dry_run:
                skipped_already += 1
            elif args.dry_run and args.verbose:
                action = "на CDN уже" if on_cdn else "загрузить"
                print(f"[dry-run] {storage_path}: локальный файл есть ({action})", flush=True)
        else:
            if on_cdn and not args.dry_run:
                skipped_already += 1
                new_pub = public_url(sb_url, bucket, storage_path)
            elif on_cdn and args.dry_run and args.verbose:
                print(f"[dry-run] {storage_path}: только CDN", flush=True)
            else:
                need_telegram.append((lid, storage_path or "", str(local_path)))
                continue

        if args.dry_run:
            continue

        rp = sess.patch(
            f"{sb_url}/rest/v1/listing_media",
            params={"id": f"eq.{mid}"},
            json={"public_url": new_pub, "source_url": new_pub},
            headers={**sess.headers, "Prefer": "return=minimal"},
            timeout=120,
        )
        rp.raise_for_status()
        patched_db += 1

        if role == "card" and lid not in cover_by_listing:
            cover_by_listing[lid] = new_pub

    # listings.cover_url
    if not args.dry_run:
        for lid, cover_pub in sorted(cover_by_listing.items()):
            rp = sess.patch(
                f"{sb_url}/rest/v1/listings",
                params={"id": f"eq.{lid}"},
                json={"cover_url": cover_pub},
                headers={**sess.headers, "Prefer": "return=minimal"},
                timeout=120,
            )
            rp.raise_for_status()

    print(
        json_summary(
            {
                "candidates_relative_media": len(candidates),
                "uploaded_to_storage": uploaded,
                "db_rows_updated": patched_db,
                "cdn_already_had_object": skipped_already,
                "need_local_or_telegram": len(set(x[0] for x in need_telegram)),
            }
        )
    )
    if need_telegram:
        print("\nНет локального файла — скачайте из канала точечным sync (пример):", flush=True)
        listing_ids = sorted({x[0] for x in need_telegram})
        if listing_ids:
            in_list = "(" + ",".join(str(i) for i in listing_ids[:200]) + ")"
            msg = sess.get(
                f"{sb_url}/rest/v1/listings",
                params={
                    "select": "source_message_id,slug,source_kind",
                    "id": f"in.{in_list}",
                    "limit": str(min(200, len(listing_ids))),
                },
                timeout=120,
            )
            if msg.status_code == 200:
                hotels: list[int] = []
                for L in msg.json():
                    if L.get("source_kind") != "hotel":
                        continue
                    mid_v = int(L.get("source_message_id") or 0)
                    if mid_v:
                        hotels.append(mid_v)
                hotels = sorted(set(hotels))
                if hotels:
                    print(f"TARGET_HOTEL_SOURCE_IDS={','.join(str(x) for x in hotels[:60])} \\")
                    print("  FORCE_MEDIA_REFRESH=1 python3 scripts/sync_catalog_from_telegram.py", flush=True)
        print("(пакеты из 35 id см. scripts/backfill_listing_media_from_telegram.py --chunk)", flush=True)

    return 0


def json_summary(d: dict[str, object]) -> str:
    return json.dumps(d, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    raise SystemExit(main())
