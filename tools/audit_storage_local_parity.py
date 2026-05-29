#!/usr/bin/env python3
"""
Сверка байтов локальных фото media/hotels/<slug>/ с объектами в Supabase Storage.

Перепутанные файлы в bucket (чужие фото под правильным slug) verify_object_media.py
не ловит — только путь. Этот скрипт сравнивает SHA256.

  python3 tools/audit_storage_local_parity.py
  python3 tools/audit_storage_local_parity.py --fix
  python3 tools/audit_storage_local_parity.py --fix --slug staryy-prichal-gostevoy-dom-u-morya-3891
"""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import quote

import requests

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env.supabase.local"
LOCAL_ROOT = ROOT / "media" / "hotels"
REPORT_PATH = ROOT / "output" / "storage_local_parity_audit.json"
DEFAULT_BUCKET = "site-media"
WORKERS = 8


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


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def public_url(sb_url: str, bucket: str, storage_path: str) -> str:
    encoded = "/".join(quote(part, safe="") for part in storage_path.split("/"))
    return f"{sb_url.rstrip('/')}/storage/v1/object/public/{bucket}/{encoded}"


def upload_local(
    session: requests.Session,
    sb_url: str,
    bucket: str,
    storage_path: str,
    local_file: Path,
) -> None:
    encoded = "/".join(quote(part, safe="") for part in storage_path.split("/"))
    post_url = f"{sb_url.rstrip('/')}/storage/v1/object/{bucket}/{encoded}"
    mime = mimetypes.guess_type(local_file.name)[0] or "image/jpeg"
    data = local_file.read_bytes()
    headers = {"Content-Type": mime, "x-upsert": "true"}
    last: Exception | None = None
    for attempt in range(5):
        try:
            r = session.post(post_url, headers=headers, data=data, timeout=600)
            r.raise_for_status()
            return
        except Exception as err:  # noqa: BLE001
            last = err
            time.sleep(1 + attempt)
    raise RuntimeError(f"upload failed {storage_path}: {last}")


def check_file(slug: str, photo: Path, sb_url: str, bucket: str) -> dict[str, object]:
    local_hash = sha256_bytes(photo.read_bytes())
    storage_path = f"hotels/{slug}/{photo.name}"
    url = public_url(sb_url, bucket, storage_path)
    try:
        r = requests.get(url, timeout=30)
    except requests.RequestException as exc:
        return {
            "slug": slug,
            "file": photo.name,
            "status": "fetch_error",
            "error": str(exc)[:200],
            "local_hash": local_hash[:16],
        }
    if r.status_code != 200:
        return {
            "slug": slug,
            "file": photo.name,
            "status": f"http_{r.status_code}",
            "local_hash": local_hash[:16],
        }
    remote_hash = sha256_bytes(r.content)
    if remote_hash == local_hash:
        return {"slug": slug, "file": photo.name, "status": "ok"}
    return {
        "slug": slug,
        "file": photo.name,
        "status": "mismatch",
        "local_hash": local_hash[:16],
        "remote_hash": remote_hash[:16],
        "storage_path": storage_path,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fix", action="store_true", help="Перезалить локальные файлы в Storage (upsert).")
    ap.add_argument("--slug", action="append", default=[], help="Ограничить slug (можно несколько раз).")
    args = ap.parse_args()

    env = load_env(ENV_PATH)
    sb_url = env.get("SUPABASE_URL", "").rstrip("/")
    key = env.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not sb_url or not key:
        print("Нужны SUPABASE_URL и SUPABASE_SERVICE_ROLE_KEY в .env.supabase.local", file=sys.stderr)
        return 1

    slug_filter = set(args.slug)
    slugs = sorted(
        d.name
        for d in LOCAL_ROOT.iterdir()
        if d.is_dir() and (not slug_filter or d.name in slug_filter)
    )
    if slug_filter:
        missing = slug_filter - set(slugs)
        for m in sorted(missing):
            print(f"[warn] slug не найден локально: {m}", file=sys.stderr)

    tasks: list[tuple[str, Path]] = []
    for slug in slugs:
        for photo in sorted((LOCAL_ROOT / slug).glob("photo-*.jpg")):
            tasks.append((slug, photo))

    results: list[dict[str, object]] = []
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = [pool.submit(check_file, slug, photo, sb_url, DEFAULT_BUCKET) for slug, photo in tasks]
        for fut in as_completed(futures):
            results.append(fut.result())

    mismatches = [r for r in results if r.get("status") == "mismatch"]
    missing_remote = [r for r in results if str(r.get("status", "")).startswith("http_404")]

    report = {
        "slugs_scanned": len(slugs),
        "files_checked": len(results),
        "ok": sum(1 for r in results if r.get("status") == "ok"),
        "mismatch": len(mismatches),
        "missing_remote": len(missing_remote),
        "mismatched_slugs": sorted({str(r["slug"]) for r in mismatches}),
        "details": mismatches,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({k: report[k] for k in report if k != "details"}, ensure_ascii=False, indent=2))
    if mismatches:
        print("\nПримеры расхождений:", file=sys.stderr)
        for row in mismatches[:20]:
            print(f"  {row['slug']}/{row['file']}: local {row['local_hash']} remote {row['remote_hash']}", file=sys.stderr)

    if args.fix and mismatches:
        sess = requests.Session()
        sess.headers.update({"apikey": key, "Authorization": f"Bearer {key}"})
        fixed = 0
        for row in mismatches:
            slug = str(row["slug"])
            photo = LOCAL_ROOT / slug / str(row["file"])
            storage_path = str(row["storage_path"])
            upload_local(sess, sb_url, DEFAULT_BUCKET, storage_path, photo)
            fixed += 1
            if fixed % 25 == 0:
                print(f"[fix] uploaded {fixed}/{len(mismatches)}", flush=True)
        print(f"[fix] uploaded {fixed} files", flush=True)

    return 1 if mismatches and not args.fix else 0


if __name__ == "__main__":
    raise SystemExit(main())
