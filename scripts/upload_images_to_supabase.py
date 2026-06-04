#!/usr/bin/env python3
"""Upload raster site images to Supabase Storage and relink pages/data.

This script is intentionally narrow: it changes only image URLs in HTML/JSON
files. It does not touch layout, CSS classes, text blocks, filters, or card
structure.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import quote, unquote, urlparse

import requests

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env.supabase.local"
BUCKET_DEFAULT = "site-media"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
IMAGE_ROOTS = (
    ROOT / "media" / "hotels",
    ROOT / "media" / "kvartira",
    ROOT / "media" / "cards",
    ROOT / "media" / "kvartira-cards",
    ROOT / "media" / "branding",
)
REWRITE_GLOBS = (
    "index.html",
    "hotels/*/index.html",
    "kvartira/*/index.html",
    "kvartira/index.html",
    "*.json",
    "output/*.json",
)
LOCAL_IMAGE_URL_RE = re.compile(
    r'(?P<prefix>["\'(=:\s])'
    r'(?P<url>(?:(?:https?://(?:абхазберег\.рф|xn--80aacbklan7f0b\.xn--p1ai))?/media/|media/)'
    r'[^"\'\s<>)]+?\.(?:jpg|jpeg|png|webp))',
    re.I,
)


def load_env_file(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.is_file():
        return data
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def ensure_env() -> tuple[str, str, str]:
    for k, v in load_env_file(ENV_FILE).items():
        os.environ.setdefault(k, v)
    base = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or ""
    bucket = os.environ.get("SUPABASE_STORAGE_BUCKET") or BUCKET_DEFAULT
    if not base or not key:
        raise RuntimeError(f"Нужны SUPABASE_URL и SUPABASE_SERVICE_ROLE_KEY в {ENV_FILE}")
    return base, key, bucket


def public_url(base: str, bucket: str, storage_path: str) -> str:
    encoded = "/".join(quote(part) for part in storage_path.split("/"))
    return f"{base}/storage/v1/object/public/{bucket}/{encoded}"


def storage_path_for_local(local_path: Path) -> str:
    rel = local_path.relative_to(ROOT).as_posix()
    if not rel.startswith("media/"):
        raise ValueError(f"Image is outside media/: {local_path}")
    return rel.removeprefix("media/")


def storage_path_for_url(url: str) -> str | None:
    parsed = urlparse(url)
    path = unquote(parsed.path if parsed.scheme else url)
    path = path.lstrip("/")
    if not path.startswith("media/"):
        return None
    suffix = Path(path).suffix.lower()
    if suffix not in IMAGE_EXTENSIONS:
        return None
    return path.removeprefix("media/")


def local_path_for_url(url: str) -> Path | None:
    storage_path = storage_path_for_url(url)
    if not storage_path:
        return None
    return ROOT / "media" / storage_path


def iter_images() -> Iterable[Path]:
    seen: set[Path] = set()
    for root in IMAGE_ROOTS:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS and path not in seen:
                seen.add(path)
                yield path


def iter_rewrite_files() -> Iterable[Path]:
    seen: set[Path] = set()
    for pattern in REWRITE_GLOBS:
        for path in sorted(ROOT.glob(pattern)):
            if path.is_file() and path not in seen:
                seen.add(path)
                yield path


@dataclass
class UploadRow:
    local_path: str
    storage_path: str
    public_url: str
    status: str
    size_kb: int
    note: str = ""


def upload_one(base: str, key: str, bucket: str, local_path: Path, retries: int = 4) -> UploadRow:
    storage_path = storage_path_for_local(local_path)
    encoded = "/".join(quote(part) for part in storage_path.split("/"))
    url = f"{base}/storage/v1/object/{bucket}/{encoded}"
    mime_type = mimetypes.guess_type(local_path.name)[0] or "application/octet-stream"
    headers = {
        "Authorization": f"Bearer {key}",
        "apikey": key,
        "Content-Type": mime_type,
        "Cache-Control": "public, max-age=31536000, immutable",
        "x-upsert": "true",
    }
    last_error = ""
    for attempt in range(retries):
        try:
            with local_path.open("rb") as f:
                response = requests.post(url, data=f, headers=headers, timeout=(30, 900))
            if response.status_code in {200, 201}:
                return UploadRow(
                    local_path=local_path.relative_to(ROOT).as_posix(),
                    storage_path=storage_path,
                    public_url=public_url(base, bucket, storage_path),
                    status="uploaded",
                    size_kb=round(local_path.stat().st_size / 1024),
                )
            last_error = f"{response.status_code}: {response.text[:300]}"
        except Exception as error:  # noqa: BLE001
            last_error = str(error)
        time.sleep(1 + attempt)
    return UploadRow(
        local_path=local_path.relative_to(ROOT).as_posix(),
        storage_path=storage_path,
        public_url=public_url(base, bucket, storage_path),
        status="error",
        size_kb=round(local_path.stat().st_size / 1024),
        note=last_error,
    )


def rewrite_text(text: str, base: str, bucket: str) -> tuple[str, int, int]:
    changed = 0
    missing = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal changed, missing
        prefix = match.group("prefix")
        old_url = match.group("url")
        local_path = local_path_for_url(old_url)
        if not local_path:
            return match.group(0)
        if not local_path.exists():
            missing += 1
            return match.group(0)
        new_url = public_url(base, bucket, storage_path_for_local(local_path))
        if old_url == new_url:
            return match.group(0)
        changed += 1
        return prefix + new_url

    return LOCAL_IMAGE_URL_RE.sub(repl, text), changed, missing


def rewrite_files(base: str, bucket: str, dry_run: bool) -> dict[str, object]:
    files_changed = 0
    urls_changed = 0
    missing_refs = 0
    changed_files: list[str] = []
    for path in iter_rewrite_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        new_text, changed, missing = rewrite_text(text, base, bucket)
        missing_refs += missing
        if changed:
            files_changed += 1
            urls_changed += changed
            changed_files.append(path.relative_to(ROOT).as_posix())
            if not dry_run:
                path.write_text(new_text, encoding="utf-8")
    return {
        "files_changed": files_changed,
        "urls_changed": urls_changed,
        "missing_refs": missing_refs,
        "changed_files": changed_files[:200],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-upload", action="store_true")
    parser.add_argument("--skip-rewrite", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()

    base, key, bucket = ensure_env()
    images = list(iter_images())
    if args.limit:
        images = images[: args.limit]

    rows: list[UploadRow] = []
    if not args.skip_upload:
        if args.dry_run:
            rows = [
                UploadRow(
                    local_path=p.relative_to(ROOT).as_posix(),
                    storage_path=storage_path_for_local(p),
                    public_url=public_url(base, bucket, storage_path_for_local(p)),
                    status="dry-run",
                    size_kb=round(p.stat().st_size / 1024),
                )
                for p in images
            ]
        else:
            with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
                futures = {pool.submit(upload_one, base, key, bucket, p): p for p in images}
                done = 0
                for future in as_completed(futures):
                    rows.append(future.result())
                    done += 1
                    if done % 100 == 0:
                        print(f"Загружено/обработано фото: {done}/{len(images)}", flush=True)

    rewrite_report = {}
    if not args.skip_rewrite:
        rewrite_report = rewrite_files(base, bucket, args.dry_run)

    out = {
        "images_total": len(images),
        "upload": {
            "uploaded": sum(1 for row in rows if row.status == "uploaded"),
            "errors": sum(1 for row in rows if row.status == "error"),
            "dry_run": sum(1 for row in rows if row.status == "dry-run"),
        },
        "rewrite": rewrite_report,
        "errors": [asdict(row) for row in rows if row.status == "error"][:200],
    }
    (ROOT / "output").mkdir(exist_ok=True)
    (ROOT / "output" / "image_storage_report.json").write_text(
        json.dumps({**out, "rows": [asdict(row) for row in rows]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 1 if out["upload"]["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
