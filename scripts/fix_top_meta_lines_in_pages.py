from __future__ import annotations

import html
import re
import sys
from pathlib import Path
from typing import Any

import requests

from rebuild_from_supabase import ENV_PATH, load_env

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from sync_abhazbooking_2026 import clean_line


def normalize_meta_value(value: str) -> str:
    text = clean_line(value)
    text = re.sub(r"^[📍🏖🏝👥]\s*", "", text)
    text = text.replace("🏖️", "").replace("🏝️", "")
    text = re.sub(r"^[–—-]\s*", "", text)
    text = re.sub(r"\s+", " ", text).strip(" .,:;-").lower()
    return text


def build_top_meta_lines(row: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    location = clean_line(str(row.get("location_text") or ""))
    beach = clean_line(str(row.get("beach_text") or ""))
    capacity = clean_line(str(row.get("capacity_text") or ""))
    if location:
        lines.append(f"📍 {location}")
    if beach:
        lines.append(f"🏖️ {beach}")
    if capacity:
        lines.append(f"👥 {capacity}")
    return lines


def remove_meta_lines_from_paragraph_blocks(text: str, top_lines: list[str]) -> str:
    if not top_lines:
        return text
    normalized_targets = {normalize_meta_value(line) for line in top_lines if normalize_meta_value(line)}

    def _block_repl(match: re.Match[str]) -> str:
        block = match.group(0)

        def _p_repl(pm: re.Match[str]) -> str:
            p_html = pm.group(0)
            inner = pm.group(1)
            plain = re.sub(r"<[^>]+>", "", html.unescape(inner))
            normalized = normalize_meta_value(plain)
            if not normalized:
                return p_html
            if plain.strip().startswith(("📍", "🏖", "🏝", "👥")):
                return ""
            if normalized in normalized_targets:
                return ""
            return p_html

        cleaned = re.sub(r"<p[^>]*>(.*?)</p>", _p_repl, block, flags=re.S)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned

    return re.sub(
        r"<div class=\"paragraph-blocks\">.*?</div>",
        _block_repl,
        text,
        flags=re.S,
    )


def update_page(path: Path, top_lines: list[str]) -> bool:
    text = path.read_text(encoding="utf-8")
    original = text

    if top_lines:
        top_html = "<br>".join(html.escape(line) for line in top_lines[:3])
        text = re.sub(
            r"<p class=\"location\">.*?</p>",
            f"<p class=\"location\">{top_html}</p>",
            text,
            count=1,
            flags=re.S,
        )

    text = remove_meta_lines_from_paragraph_blocks(text, top_lines)

    if text != original:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def main() -> None:
    env = load_env(ENV_PATH)
    base = env["SUPABASE_URL"].rstrip("/")
    service_key = env["SUPABASE_SERVICE_ROLE_KEY"]
    headers = {"apikey": service_key, "Authorization": f"Bearer {service_key}"}

    response = requests.get(
        f"{base}/rest/v1/listings",
        headers=headers,
        params={
            "select": "id,slug,source_kind,location_text,beach_text,capacity_text,details,is_active",
            "is_active": "eq.true",
            "order": "id.asc",
            "limit": "5000",
        },
        timeout=120,
    )
    response.raise_for_status()
    rows = response.json()

    updated = 0
    skipped = 0
    missing_path = 0
    for row in rows:
        details = row.get("details") or {}
        page_path = details.get("page_path")
        if not page_path:
            skipped += 1
            continue
        path = Path(page_path)
        if not path.exists():
            missing_path += 1
            continue
        top_lines = build_top_meta_lines(row)
        if update_page(path, top_lines):
            updated += 1

    print(f"updated={updated} skipped_no_path={skipped} missing_path={missing_path} total={len(rows)}")


if __name__ == "__main__":
    main()
