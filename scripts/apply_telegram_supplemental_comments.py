#!/usr/bin/env python3
"""Apply Telegram supplemental comment media (with captions) to object pages."""
from __future__ import annotations

import argparse
import asyncio
import html
import json
import os
import re
import subprocess
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup
from telethon.tl.functions.messages import GetRepliesRequest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from media_urls import yandex_photo_url, yandex_video_url  # noqa: E402
from telegram_runtime import connected_telegram_client, run_async_entrypoint  # noqa: E402
from supplemental_store import save_section as save_supplemental_section  # noqa: E402

AUDIT_PATH = ROOT / "output" / "telegram_supplemental_comments_audit.json"
REPORT_PATH = ROOT / "output" / "telegram_supplemental_apply_report.txt"

DEFAULT_API_ID = 32916166
DEFAULT_API_HASH = "eefdec49605521b061de4bdf62ef784e"

REVIEW_RE = re.compile(
    r"(?:^|\b)(?:отзыв(?:ы|а|ов|ами)?|фото\s*отзыв|guest\s*review|reviews?)(?:\b|$)",
    re.I,
)
ROOM_RE = re.compile(
    r"номер|люкс|стандарт|делюкс|полулюкс|домик|коттедж|апарт|комнат|комфорт",
    re.I,
)


@dataclass
class MediaFile:
    rel_path: str
    kind: str  # photo | video


@dataclass
class SupplementalBlock:
    caption: str
    message_ids: list[int]
    media: list[MediaFile] = field(default_factory=list)


@dataclass
class Target:
    kind: str
    slug: str
    title: str
    channel: str
    message_id: int
    topic_id: int | None
    blocks: list[SupplementalBlock]


def load_env_files() -> None:
    for path in (
        ROOT / ".env.site-update-bot",
        ROOT / ".env.supabase.local",
        ROOT / ".env.yandex.local",
    ):
        if not path.exists():
            continue
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def normalize_text(value: str) -> str:
    value = html.unescape(value or "")
    value = unicodedata.normalize("NFKC", value)
    value = value.replace("\xa0", " ")
    value = re.sub(r"[ \t\r\f\v]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def slugify(value: str, *, max_len: int = 48) -> str:
    value = normalize_text(value).lower()
    value = value.translate(str.maketrans("абвгдеёжзийклмнопрстуфхцчшщъыьэюя", "abvgdeejziyklmnoprstufhcchshshchyyeyu"))
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return (value or "block")[:max_len]


def has_meaningful_caption(caption: str) -> bool:
    cap = normalize_text(caption)
    return bool(cap) and cap != "(без подписи)" and len(cap) >= 3 and not REVIEW_RE.search(cap)


def card_title(caption: str, object_title: str) -> str:
    text = normalize_text(caption)
    raw_object_title = normalize_text(object_title)
    object_title_clean = raw_object_title.strip('"«»')
    candidates = [raw_object_title, object_title_clean]
    brand_match = re.search(r'["«]([^"»]+)["»]', raw_object_title)
    if brand_match:
        brand = brand_match.group(1).strip()
        candidates.extend([brand, f'"{brand}"', f"«{brand}»"])
    for candidate in sorted({item for item in candidates if len(item) > 2}, key=len, reverse=True):
        text = re.sub(re.escape(candidate), "", text, flags=re.I)
    text = re.sub(r'["«»]', "", text).strip(" .,-—")
    if len(text) <= 80:
        return text or normalize_text(caption)
    parts = re.split(r"[.:;]\s+", text, maxsplit=1)
    return parts[0][:80]


def card_label(caption: str) -> str:
    if re.search(r"домик|коттедж", caption, re.I):
        return "Обзор домика"
    if ROOM_RE.search(caption):
        return "Обзор номера"
    return "Дополнительно"


def section_title(blocks: list[SupplementalBlock]) -> str:
    roomish = sum(1 for block in blocks if ROOM_RE.search(block.caption))
    if roomish >= max(1, len(blocks) // 2):
        return "Дополнительные обзоры номеров и домиков"
    return "Дополнительные материалы"


def page_path(target: Target) -> Path:
    if target.kind == "kvartira":
        return ROOT / "kvartira" / target.slug / "index.html"
    return ROOT / "hotels" / target.slug / "index.html"


def media_root(target: Target) -> Path:
    if target.kind == "kvartira":
        return ROOT / "media" / "kvartira" / target.slug / "supplemental"
    return ROOT / "media" / "hotels" / target.slug / "supplemental"


def load_targets(limit: int | None = None, only_slugs: set[str] | None = None) -> list[Target]:
    payload = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    targets: list[Target] = []
    for row in payload.get("results") or []:
        slug = str(row.get("slug") or "").strip()
        if only_slugs and slug not in only_slugs:
            continue
        blocks = []
        for block in row.get("supplemental_blocks") or []:
            caption = normalize_text(str(block.get("caption") or ""))
            if not has_meaningful_caption(caption):
                continue
            message_ids = [int(x) for x in block.get("message_ids") or []]
            if not message_ids:
                continue
            blocks.append(SupplementalBlock(caption=caption, message_ids=message_ids))
        if not blocks:
            continue
        targets.append(
            Target(
                kind=str(row.get("kind") or ""),
                slug=slug,
                title=str(row.get("title") or slug),
                channel=str(row.get("channel") or ""),
                message_id=int(row.get("message_id") or 0),
                topic_id=int(row["topic_id"]) if row.get("topic_id") else None,
                blocks=blocks,
            )
        )
    targets.sort(key=lambda item: item.slug)
    return targets[:limit] if limit else targets


def media_kind(message: Any) -> str:
    file_obj = getattr(message, "file", None)
    mime = str(getattr(file_obj, "mime_type", "") or "")
    if mime.startswith("video/"):
        return "video"
    if mime.startswith("image/") or "Photo" in type(getattr(message, "media", None)).__name__:
        return "photo"
    if getattr(message, "media", None) is not None:
        return "photo"
    return "other"


async def expand_group(client: Any, entity: Any, message: Any) -> list[Any]:
    grouped_id = getattr(message, "grouped_id", None)
    if not grouped_id:
        return [message] if getattr(message, "media", None) else []
    window = 80
    min_id = max(1, int(message.id) - window)
    max_id = int(message.id) + window
    found: list[Any] = []
    async for item in client.iter_messages(entity, min_id=min_id, max_id=max_id):
        if getattr(item, "grouped_id", None) == grouped_id and getattr(item, "media", None):
            found.append(item)
    if not found and getattr(message, "media", None):
        return [message]
    return sorted(found, key=lambda row: int(row.id))


async def fetch_comment_messages(client: Any, target: Target) -> dict[int, Any]:
    entity = await client.get_entity(target.channel)
    messages: dict[int, Any] = {}
    if target.kind == "hotel":
        offset_id = 0
        seen_page_ids: set[int] = set()
        while True:
            result = await client(
                GetRepliesRequest(
                    peer=entity,
                    msg_id=target.message_id,
                    offset_id=offset_id,
                    offset_date=None,
                    add_offset=0,
                    limit=100,
                    max_id=0,
                    min_id=0,
                    hash=0,
                )
            )
            batch = list(getattr(result, "messages", []) or [])
            if not batch:
                break
            batch_ids = {int(message.id) for message in batch if int(getattr(message, "id", 0) or 0)}
            if batch_ids and batch_ids.issubset(seen_page_ids):
                break
            seen_page_ids.update(batch_ids)
            for message in batch:
                messages[int(message.id)] = message
            if len(batch) < 100:
                break
            offset_id = min(batch_ids) if batch_ids else int(batch[-1].id)
            await asyncio.sleep(0.1)
    else:
        topic_id = target.topic_id or target.message_id
        async for message in client.iter_messages(entity, reply_to=topic_id):
            if int(message.id) != target.message_id:
                messages[int(message.id)] = message
    return messages


async def download_block_media(
    client: Any,
    entity: Any,
    target: Target,
    block: SupplementalBlock,
    block_index: int,
    messages_by_id: dict[int, Any],
) -> None:
    out_dir = media_root(target) / f"block-{block_index:02d}"
    out_dir.mkdir(parents=True, exist_ok=True)
    photo_idx = 0
    video_idx = 0
    seen_ids: set[int] = set()
    for message_id in block.message_ids:
        seed = messages_by_id.get(message_id)
        if not seed:
            continue
        grouped_id = getattr(seed, "grouped_id", None)
        if grouped_id:
            group_messages = sorted(
                [
                    message
                    for message in messages_by_id.values()
                    if getattr(message, "grouped_id", None) == grouped_id and getattr(message, "media", None)
                ],
                key=lambda row: int(row.id),
            )
        else:
            group_messages = []
        for message in group_messages or await expand_group(client, entity, seed):
            mid = int(message.id)
            if mid in seen_ids:
                continue
            seen_ids.add(mid)
            kind = media_kind(message)
            if kind not in {"photo", "video"}:
                continue
            if kind == "photo":
                photo_idx += 1
                filename = f"photo-{photo_idx:02d}.jpg"
            else:
                video_idx += 1
                filename = f"video-{video_idx:02d}.mp4"
            dest = out_dir / filename
            if not dest.exists():
                await client.download_media(message, file=str(dest))
            rel = dest.relative_to(ROOT / "media").as_posix()
            block.media.append(MediaFile(rel_path=rel, kind=kind))


def upload_media_dirs(dirs: list[Path], *, dry_run: bool) -> None:
    existing = [str(path) for path in dirs if path.exists()]
    if not existing or dry_run:
        return
    cmd = [
        sys.executable,
        str(ROOT / "tools" / "upload_yandex_media.py"),
        "--workers",
        "48",
        *existing,
    ]
    subprocess.run(cmd, cwd=ROOT, check=True)


def render_media_html(block: SupplementalBlock, target: Target, card_heading: str) -> str:
    lines: list[str] = ['<div class="comment-media-grid">']
    object_label = normalize_text(target.title).strip('"')
    for item in block.media:
        url = yandex_photo_url(f"media/{item.rel_path}") if item.kind == "photo" else yandex_video_url(f"media/{item.rel_path}")
        if item.kind == "photo":
            alt = html.escape(f"{object_label} — {card_heading}")
            lines.append(f'                  <img src="{html.escape(url)}" alt="{alt}" loading="lazy" />')
        else:
            lines.append("                  <video class=\"local-video\" controls preload=\"metadata\" playsinline>")
            lines.append(f'                    <source src="{html.escape(url)}" type="video/mp4" />')
            lines.append("                  </video>")
    lines.append("                </div>")
    return "\n".join(lines)


def render_section_html(target: Target, blocks: list[SupplementalBlock]) -> str:
    cards: list[str] = []
    for block in blocks:
        if not block.media:
            continue
        heading = card_title(block.caption, target.title)
        label = card_label(block.caption)
        caption_html = html.escape(normalize_text(block.caption))
        cards.append(
            "\n".join(
                [
                    "              <article class=\"room-overview-card\">",
                    "                <div class=\"room-overview-card__text\">",
                    f"                  <span class=\"room-overview-card__label\">{html.escape(label)}</span>",
                    f"                  <h3>{html.escape(heading)}</h3>",
                    f"                  <p>{caption_html}</p>",
                    "                </div>",
                    render_media_html(block, target, heading),
                    "              </article>",
                ]
            )
        )
    if not cards:
        return ""
    section_h2 = section_title(blocks)
    return "\n".join(
        [
            "          <section class=\"section hotel-room-overviews hotel-site-concept__detail-section\" id=\"supplemental-comments\">",
            "            <article class=\"card\">",
            f"              <h2>{html.escape(section_h2)}</h2>",
            "              <div class=\"room-overview-list\">",
            *cards,
            "              </div>",
            "            </article>",
            "          </section>",
        ]
    )


def insert_section(page_html: str, section_html: str) -> str:
    soup = BeautifulSoup(page_html, "html.parser")
    existing = soup.select_one("#supplemental-comments, #room-overviews")
    if existing:
        existing.replace_with(BeautifulSoup(section_html, "html.parser"))
        return str(soup)
    media_section = soup.select_one("section.hotel-media-section")
    if media_section:
        media_section.insert_after(BeautifulSoup(section_html, "html.parser"))
        return str(soup)
    detail_main = soup.select_one(".hotel-site-concept__detail-main")
    if detail_main:
        detail_main.insert(0, BeautifulSoup(section_html, "html.parser"))
        return str(soup)
    raise RuntimeError("could not find insertion point")


async def apply_target(
    client: Any,
    target: Target,
    *,
    dry_run: bool,
    force: bool,
) -> tuple[bool, str]:
    path = page_path(target)
    if not path.exists():
        return False, f"missing page {path.relative_to(ROOT)}"
    page_html = path.read_text(encoding="utf-8")
    if not force and ("id=\"room-overviews\"" in page_html or "id=\"supplemental-comments\"" in page_html):
        return False, "section already exists (use --force to replace)"

    entity = await client.get_entity(target.channel)
    messages_by_id = await fetch_comment_messages(client, target)
    for index, block in enumerate(target.blocks, 1):
        await download_block_media(client, entity, target, block, index, messages_by_id)
        if not block.media:
            return False, f"no media downloaded for block: {block.caption[:60]}"

    section_html = render_section_html(target, target.blocks)
    if not section_html:
        return False, "empty section after download"
    if dry_run:
        return True, f"dry-run ok ({len(target.blocks)} blocks)"
    upload_media_dirs([media_root(target)], dry_run=dry_run)
    updated = insert_section(page_html, section_html)
    path.write_text(updated, encoding="utf-8")
    # Секция сохраняется в data/supplemental-blocks.json, чтобы переживать
    # любые пересборки страниц (генераторы вставляют её обратно).
    save_supplemental_section(target.slug, target.kind, section_html)
    return True, f"updated ({len(target.blocks)} blocks, {sum(len(b.media) for b in target.blocks)} files)"


async def run(args: argparse.Namespace) -> int:
    load_env_files()
    only_slugs = {part.strip() for part in args.slug.split(",") if part.strip()} if args.slug else None
    targets = load_targets(limit=args.limit, only_slugs=only_slugs)
    if not targets:
        print("No targets found.")
        return 1

    api_id = int(os.getenv("TELEGRAM_API_ID", str(DEFAULT_API_ID)))
    api_hash = os.getenv("TELEGRAM_API_HASH", DEFAULT_API_HASH)
    session = os.getenv("TG_SESSION", str(ROOT / "tg_session"))

    results: list[str] = []
    ok = 0
    async with connected_telegram_client(session, api_id, api_hash, receive_updates=False) as client:
        if not await client.is_user_authorized():
            raise RuntimeError(f"Telegram session is not authorized: {session}")
        for index, target in enumerate(targets, 1):
            try:
                success, message = await apply_target(
                    client,
                    target,
                    dry_run=args.dry_run,
                    force=args.force,
                )
                line = f"[{'OK' if success else 'SKIP' if 'already exists' in message else 'ERR'}] {target.slug}: {message}"
                results.append(line)
                print(f"{index}/{len(targets)} {line}", flush=True)
                if success:
                    ok += 1
                await asyncio.sleep(0.3)
            except Exception as error:  # noqa: BLE001
                line = f"[ERR] {target.slug}: {error}"
                results.append(line)
                print(line, flush=True)
    report = "\n".join(
        [
            "Apply Telegram supplemental comments",
            f"targets={len(targets)} ok={ok}",
            "",
            *results,
            "",
        ]
    )
    REPORT_PATH.write_text(report + "\n", encoding="utf-8")
    print(report)
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true", help="Replace existing supplemental section.")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--slug", default="", help="Comma-separated slugs")
    args = parser.parse_args()
    if args.limit:
        args.limit = args.limit
    else:
        args.limit = None
    return run_async_entrypoint(run(args), name="apply_telegram_supplemental_comments", default_timeout=1800)


if __name__ == "__main__":
    raise SystemExit(main())
