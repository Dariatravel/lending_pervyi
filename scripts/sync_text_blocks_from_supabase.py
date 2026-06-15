from __future__ import annotations

import html
import re
import sys
from pathlib import Path
from typing import Any

import requests

ROOT = Path.cwd()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from rebuild_from_supabase import ENV_PATH, FILTER_GROUPS, load_env
from sync_abhazbooking_2026 import clean_line, render_paragraph_lines_html, should_drop_line
from tools.apply_new_site_design import format_price_line_to_html, format_price_season_li_html


def _dedupe_preserve_order(lines: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for raw in lines:
        line = clean_line(str(raw))
        if not line:
            continue
        key = re.sub(r"\s+", " ", line).strip().lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(line)
    return result


def compose_top_meta_text(row: dict[str, Any]) -> str:
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
    return " · ".join(_dedupe_preserve_order(lines))


def normalize_section_label(label: str) -> str:
    cleaned = clean_line(label)
    cleaned = re.sub(r"^[^\wА-Яа-яЁё]*[✔✅☑]+\s*", "", cleaned)
    cleaned = re.sub(r"^[^\wА-Яа-яЁё]+", "", cleaned)
    cleaned = cleaned.strip()
    if cleaned and not cleaned.endswith(":"):
        cleaned = f"{cleaned}:"
    return cleaned


def collect_description_lines(details: dict[str, Any]) -> list[str]:
    sections = details.get("sections") or []
    merged: list[str] = []
    for section in sections:
        label = normalize_section_label(str(section.get("label") or ""))
        if label and label.lower() not in {"обзор", "обзор:"}:
            merged.append(label)
        for line in section.get("lines") or []:
            cleaned = clean_line(str(line))
            if cleaned and not should_drop_line(cleaned):
                merged.append(cleaned)
    return _dedupe_preserve_order(merged)


def collect_price_lines(details: dict[str, Any]) -> list[str]:
    prices = details.get("prices") or []
    visible = [clean_line(str(line)) for line in prices if line and not should_drop_line(str(line))]
    return _dedupe_preserve_order(visible)


def render_description_inner_html(details: dict[str, Any]) -> str:
    lines = collect_description_lines(details)
    if not lines:
        return ""
    return render_paragraph_lines_html(lines, indent="            ")


def render_prices_section_html(details: dict[str, Any]) -> str:
    lines = collect_price_lines(details)
    if not lines:
        return ""
    items = "\n".join(f"            {format_price_season_li_html(line)}" for line in lines)
    return (
        '      <section class="section hotel-price-section hotel-site-concept__detail-section">\n'
        '        <article class="card price-card">\n'
        "          <h2>Цены</h2>\n"
        "          <ul>\n"
        f"{items}\n"
        "          </ul>\n"
        "        </article>\n"
        "      </section>"
    )


def update_page_text_blocks(row: dict[str, Any]) -> bool:
    details = row.get("details") or {}
    page_path = details.get("page_path")
    if not page_path:
        return False
    path = Path(page_path)
    if not path.exists():
        return False

    text = path.read_text(encoding="utf-8")
    original = text

    top_meta = compose_top_meta_text(row)
    if top_meta:
        text = re.sub(
            r'<p class="location">.*?</p>',
            f'<p class="location">{html.escape(top_meta)}</p>',
            text,
            count=1,
            flags=re.S,
        )

    description_inner = render_description_inner_html(details)
    if description_inner:
        text = re.sub(
            r'(<h2>Описание</h2>\s*<div class="paragraph-blocks">\s*)(.*?)(\s*</div>\s*</article>\s*</section>)',
            rf"\1{description_inner}\3",
            text,
            count=1,
            flags=re.S,
        )

    prices_section = render_prices_section_html(details)
    if prices_section:
        text = re.sub(
            r'<section class="section hotel-price-section hotel-site-concept__detail-section">.*?</section>',
            prices_section,
            text,
            count=1,
            flags=re.S,
        )

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
            "select": "id,source_kind,location_text,beach_text,capacity_text,details,is_active",
            "is_active": "eq.true",
            "order": "id.asc",
            "limit": "3000",
        },
        timeout=120,
    )
    response.raise_for_status()
    rows = response.json()

    updated = 0
    skipped = 0
    for row in rows:
        details = row.get("details") or {}
        if not isinstance(details, dict) or not details.get("page_path"):
            skipped += 1
            continue
        if update_page_text_blocks(row):
            updated += 1

    print(f"Обновлено страниц: {updated}")
    print(f"Пропущено (без page_path): {skipped}")


if __name__ == "__main__":
    main()
