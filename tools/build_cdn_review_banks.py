#!/usr/bin/env python3
"""Build and optionally upload split review banks for CDN delivery."""

from __future__ import annotations

import argparse
import json
import re
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from yandex_storage import upload_file, yandex_public_url  # noqa: E402

REVIEWS_DIR = ROOT / "media" / "reviews"
LEGACY_BANK_PATH = REVIEWS_DIR / "review_text_bank.json"
GLOBAL_PATH = REVIEWS_DIR / "global.json"
SOURCE_CANDIDATES = (
    Path("/Users/darya_botova/Documents/GitHub/lending_pervyi/media/reviews"),
    Path("/Users/darya_botova/Documents/New project/media/reviews"),
    Path("/Users/darya_botova/abhazbereg-bot/lending_pervyi/media/reviews"),
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def find_source_dir(explicit: str | None) -> Path | None:
    if explicit:
        path = Path(explicit).expanduser()
        return path if path.exists() else None
    if GLOBAL_PATH.exists() or LEGACY_BANK_PATH.exists():
        return REVIEWS_DIR
    for path in SOURCE_CANDIDATES:
        if (path / "global.json").exists() or (path / "review_text_bank.json").exists():
            return path
    return None


def scrub_payload(node: Any) -> Any:
    """Вычистить телефоны/почту во всех текстовых полях отзыва (рекурсивно).

    Путь копирования готовых нарезок раньше миновал чистку — 18.08.2026 из-за
    этого свежезалитый bank.json вернул в CDN номер телефона гостя, уже
    вычищенный в облаке. Теперь чистятся ОБА пути: генерация и копирование.
    """
    if isinstance(node, dict):
        return {
            key: (scrub_personal_data(value) if isinstance(value, str) and key in ("text", "name", "author", "title") else scrub_payload(value))
            for key, value in node.items()
        }
    if isinstance(node, list):
        return [scrub_payload(item) for item in node]
    return node


def copy_existing_split_banks(source_dir: Path) -> list[Path]:
    def copy_scrubbed(src: Path, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        dump_json(target, scrub_payload(load_json(src)))

    if source_dir.resolve() == REVIEWS_DIR.resolve():
        files = sorted(REVIEWS_DIR.glob("*/bank.json")) + ([GLOBAL_PATH] if GLOBAL_PATH.exists() else [])
        for path in files:
            dump_json(path, scrub_payload(load_json(path)))
        return files
    copied: list[Path] = []
    if (source_dir / "global.json").exists():
        copy_scrubbed(source_dir / "global.json", GLOBAL_PATH)
        copied.append(GLOBAL_PATH)
    for bank in source_dir.glob("*/bank.json"):
        target = REVIEWS_DIR / bank.parent.name / "bank.json"
        copy_scrubbed(bank, target)
        copied.append(target)
    return sorted(copied)


# Телефоны и почта гостей не должны уезжать на CDN (18.08.2026 номер из
# отзыва всплыл на сайте). Та же чистка живёт в scrub_cdn_review_banks.py
# и в scripts.js (stripPersonalData) — три рубежа обороны.
_PII_SEP = r"[\s\-\u2013\u2014.,()]"
_PII_PATTERNS = [
    re.compile(rf"(?:\+?\s*[78]{_PII_SEP}{{0,3}})?9\d{{2}}{_PII_SEP}{{0,3}}\d{{3}}{_PII_SEP}{{0,3}}\d{{2}}{_PII_SEP}{{0,3}}\d{{2}}(?!{_PII_SEP}{{0,3}}\d)"),
    re.compile(rf"(?<!\d)\+?\s*[78]{_PII_SEP}{{0,2}}(?:\d{_PII_SEP}{{0,2}}){{9}}\d(?!{_PII_SEP}{{0,2}}\d)"),
    re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
]


def scrub_personal_data(value: str) -> str:
    text = value
    for pattern in _PII_PATTERNS:
        text = pattern.sub(" ", text)
    return re.sub(r"\s{2,}", " ", text).strip()


def normalize_review(entry: Any) -> dict[str, Any] | None:
    if not isinstance(entry, dict):
        return None
    text = scrub_personal_data(str(entry.get("text") or "").strip())
    if not text:
        return None
    result: dict[str, Any] = {
        "id": str(entry.get("id") or "").strip(),
        "name": scrub_personal_data(str(entry.get("name") or entry.get("head") or "Гость").strip()) or "Гость",
        "gender": str(entry.get("gender") or "").strip(),
        "text": text,
    }
    for key in ("source_image", "object_slug"):
        value = str(entry.get(key) or "").strip()
        if value:
            result[key] = value
    return result


def build_from_legacy_bank(source_dir: Path) -> list[Path]:
    source_path = source_dir / "review_text_bank.json"
    if not source_path.exists():
        return []
    payload = load_json(source_path)
    global_reviews = [
        review
        for review in (normalize_review(item) for item in payload.get("global") or [])
        if review
    ]
    by_object = payload.get("by_object") if isinstance(payload.get("by_object"), dict) else {}
    excluded = payload.get("excluded_fuzzy_slugs")
    global_payload = {
        "version": 1,
        "source": "review_text_bank_split",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stats": {
            "global_total": len(global_reviews),
            "objects_with_source_reviews": sum(
                1 for items in by_object.values() if isinstance(items, list) and items
            ),
        },
        "global": global_reviews,
        "excluded_fuzzy_slugs": excluded if isinstance(excluded, list) else [],
    }
    dump_json(GLOBAL_PATH, global_payload)
    generated = [GLOBAL_PATH]
    for slug, items in sorted(by_object.items()):
        reviews = [
            review
            for review in (normalize_review(item) for item in (items or []))
            if review
        ]
        if not reviews:
            continue
        bank_path = REVIEWS_DIR / str(slug) / "bank.json"
        dump_json(
            bank_path,
            {
                "version": 1,
                "source": "review_text_bank_split",
                "slug": str(slug),
                "source_slug": str(slug),
                "reviews": reviews,
            },
        )
        generated.append(bank_path)
    return generated


def iter_bank_files() -> list[Path]:
    files = [GLOBAL_PATH] if GLOBAL_PATH.exists() else []
    files.extend(sorted(REVIEWS_DIR.glob("*/bank.json")))
    return files


def upload_banks(files: list[Path], *, force: bool, dry_run: bool) -> list[dict[str, str]]:
    uploaded: list[dict[str, str]] = []
    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        if dry_run:
            url = yandex_public_url(rel)
        else:
            url = upload_file(path, rel, "application/json", force=force)
        uploaded.append({"path": rel, "url": url})
    return uploaded


def check_url(url: str, timeout: int) -> tuple[bool, int | None]:
    request = Request(url, method="GET", headers={"Cache-Control": "no-cache"})
    try:
        with urlopen(request, timeout=timeout) as response:
            return 200 <= int(response.status) < 300, int(response.status)
    except Exception:
        return False, None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", help="Папка media/reviews с global.json или review_text_bank.json.")
    parser.add_argument("--upload", action="store_true", help="Выгрузить банки в Yandex Object Storage.")
    parser.add_argument("--force", action="store_true", help="Перезагрузить даже при совпадении размера.")
    parser.add_argument("--check", action="store_true", help="Проверить публичные URL после выгрузки.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    source_dir = find_source_dir(args.source_dir)
    if not source_dir:
        print("Не найден источник банков отзывов: нужен media/reviews/global.json или review_text_bank.json.", file=sys.stderr)
        return 2

    copied = copy_existing_split_banks(source_dir)
    generated = build_from_legacy_bank(source_dir) if not copied else []
    files = iter_bank_files()
    if not files:
        print("Банки отзывов не сформированы.", file=sys.stderr)
        return 2

    uploaded: list[dict[str, str]] = []
    if args.upload:
        uploaded = upload_banks(files, force=args.force, dry_run=args.dry_run)
        if args.check and not args.dry_run:
            failed = []
            for row in uploaded:
                ok, status = check_url(row["url"], timeout=15)
                if not ok:
                    failed.append(f"{row['url']} status={status}")
            if failed:
                print("Не прошла проверка URL:\n" + "\n".join(failed), file=sys.stderr)
                return 1

    print(
        json.dumps(
            {
                "source_dir": str(source_dir),
                "copied": len(copied),
                "generated": len(generated),
                "bank_files": len(files),
                "uploaded": len(uploaded),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
