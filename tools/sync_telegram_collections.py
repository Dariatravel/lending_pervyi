#!/usr/bin/env python3
"""Подборки из постов-списков Telegram («Межсезон», «Новый год 2027»).

Дарья собирает в канале @abhazbooking посты-списки: города заголовками
(«📍ГАГРА», «✔️ЛДЗАА:») и под ними ссылки на посты объектов. Посты время от
времени правятся — состав подборок на сайте должен следовать за ними сам
(просьба Дарьи 13.10.2026).

Что делает:
1. Читает посты из data/telegram-collections-config.json.
2. Каждую ссылку на пост объекта (t.me/abhazbooking/<id>,
   t.me/abhkvartira/<тема>/<id>) сопоставляет со страницей сайта по
   каталогу; снятый объект — по его странице-редиректу (правило «отель
   главнее квартиры»), скрытые объекты пропускает.
3. Пишет состав в data/telegram-collections.json — его читает
   scripts/build_podborki_from_filters.py (группы = города из поста).
4. Объекты, которых ещё нет на сайте, пишет в
   output/telegram-collections-targets.json — автосинк сначала
   синхронизирует их (tools/watch_targets_args.py), потом пересобирает
   подборки.

Печатает «changed=true|false» (для GITHUB_OUTPUT). Файл данных меняется
только при смене состава — без меток времени, чтобы не плодить коммиты.

Запуск: python3 tools/sync_telegram_collections.py [--offline]
  --offline — не ходить в Telegram, пересопоставить сохранённые ссылки
              с каталогом (после синка новых объектов).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

CONFIG = ROOT / "data" / "telegram-collections-config.json"
DATA = ROOT / "data" / "telegram-collections.json"
TARGETS = ROOT / "output" / "telegram-collections-targets.json"
SNAPSHOT = ROOT / "data" / "catalog-snapshot.json"
HIDDEN = ROOT / "tools" / "hidden_listings.json"

LINK_RE = re.compile(r"t\.me/(abhazbooking|abhkvartira)/(\d+)(?:/(\d+))?")
REFRESH_RE = re.compile(r'http-equiv="refresh" content="0;url=(/(?:hotels|kvartira)/[^"]+/)"')
EMOJI_RE = re.compile(r"[^\w\s\-—«»\"'().,]", re.UNICODE)


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def section_label(line: str) -> str:
    """«**📍ГАГРА**», «✔️ПИЦУНДА:» → «ГАГРА», «ПИЦУНДА»."""
    text = line.replace("*", "").replace("✔️", "").replace("📍", "")
    text = EMOJI_RE.sub("", text).strip().rstrip(":").strip()
    return re.sub(r"\s+", " ", text).upper()


def is_section_line(line: str) -> bool:
    plain = line.replace("*", "").strip()
    return plain.startswith(("📍", "✔️", "✔"))


def parse_post(text: str, entity_links: list[tuple[int, str]]) -> list[dict[str, Any]]:
    """Ссылки на посты объектов по порядку, с городом-разделом из поста.

    entity_links — (позиция в тексте, url) для text_url-сущностей и голых ссылок.
    """
    # Позиции сущностей Telegram считает в единицах UTF-16 (эмодзи «📍» —
    # две единицы), поэтому и начала строк меряем так же.
    sections: list[tuple[int, str]] = []
    pos = 0
    for line in text.splitlines(keepends=True):
        if is_section_line(line):
            label = section_label(line)
            if label:
                sections.append((pos, label))
        pos += len(line.encode("utf-16-le")) // 2
    items: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()
    for offset, url in sorted(entity_links):
        m = LINK_RE.search(url)
        if not m:
            continue
        channel, first, second = m.group(1), int(m.group(2)), m.group(3)
        topic = first if second else None
        message_id = int(second) if second else first
        if (channel, message_id) in seen:
            continue
        seen.add((channel, message_id))
        section = ""
        for start, label in sections:
            if start <= offset:
                section = label
        items.append({"section": section, "channel": channel, "topic_id": topic, "message_id": message_id})
    return items


class Resolver:
    def __init__(self) -> None:
        rows = (load_json(SNAPSHOT, {}) or {}).get("listings") or []
        self.hidden = set(load_json(HIDDEN, []))
        self.rows = [r for r in rows if isinstance(r, dict) and r.get("slug")]
        self.by_msg: dict[tuple[str, int], list[dict]] = {}
        for r in self.rows:
            self.by_msg.setdefault((str(r.get("source_channel") or ""), int(r.get("source_message_id") or 0)), []).append(r)

    @staticmethod
    def href(row: dict) -> str:
        kind = "hotels" if row.get("source_kind") == "hotel" else "kvartira"
        return f"/{kind}/{row['slug']}/"

    def follow_redirect(self, href: str) -> str | None:
        page = ROOT / href.strip("/") / "index.html"
        try:
            m = REFRESH_RE.search(page.read_text(encoding="utf-8")[:2000])
        except OSError:
            return None
        return m.group(1) if m else None

    def active_href(self, row: dict) -> str | None:
        if row["slug"] in self.hidden:
            return None
        href = self.href(row)
        if row.get("is_active") is not False:
            return href if (ROOT / href.strip("/") / "index.html").is_file() else None
        # Снятый объект: страница-редирект на актуальную версию
        # (отельный двойник, перевыложенный пост).
        target = self.follow_redirect(href)
        if target and (ROOT / target.strip("/") / "index.html").is_file() and not self.follow_redirect(target):
            slug = target.strip("/").split("/")[-1]
            return None if slug in self.hidden else target
        return None

    def resolve(self, item: dict) -> tuple[str | None, str]:
        """(href, статус): статус ok | hidden | missing."""
        channel, mid, topic = item["channel"], item["message_id"], item.get("topic_id")
        cands = list(self.by_msg.get((channel, mid), []))
        if not cands:
            kind = "hotel" if channel == "abhazbooking" else "kvartira"
            cands = [r for r in self.rows if r.get("source_kind") == kind and r["slug"].endswith(f"-{mid}")]
        if not cands and topic:
            cands = [r for r in self.rows if r.get("source_channel") == channel and int(r.get("source_topic_id") or 0) == topic]
        if not cands:
            return None, "missing"
        cands.sort(key=lambda r: r.get("is_active") is False)
        for row in cands:
            href = self.active_href(row)
            if href:
                return href, "ok"
        return None, "hidden"


async def fetch_posts(config: list[dict]) -> dict[str, dict]:
    from telethon.tl.types import MessageEntityTextUrl, MessageEntityUrl
    from telegram_runtime import connected_telegram_client
    from watch_telegram_updates import DEFAULT_API_HASH, DEFAULT_API_ID, load_env_files

    load_env_files()
    api_id = int(os.getenv("TELEGRAM_API_ID", str(DEFAULT_API_ID)))
    api_hash = os.getenv("TELEGRAM_API_HASH", DEFAULT_API_HASH)
    session = os.getenv("TG_SESSION", str(ROOT / "tg_session"))
    out: dict[str, dict] = {}
    async with connected_telegram_client(session, api_id, api_hash, receive_updates=False) as client:
        for entry in config:
            message = await client.get_messages(entry["channel"], ids=int(entry["message_id"]))
            if message is None:
                out[entry["slug"]] = {"error": "пост не найден (удалён?)"}
                continue
            raw = message.message or ""
            links: list[tuple[int, str]] = []
            for ent in message.entities or []:
                if isinstance(ent, MessageEntityTextUrl):
                    links.append((ent.offset, ent.url))
                elif isinstance(ent, MessageEntityUrl):
                    utf16 = raw.encode("utf-16-le")
                    url = utf16[ent.offset * 2:(ent.offset + ent.length) * 2].decode("utf-16-le", errors="ignore")
                    links.append((ent.offset, url))
            out[entry["slug"]] = {"items": parse_post(raw, links)}
    return out


def build(config: list[dict], posts: dict[str, dict], previous: dict) -> tuple[dict, dict]:
    resolver = Resolver()
    data: dict[str, Any] = {}
    targets = {"hotel_source_ids": [], "kv_topic_ids": [], "kv_message_ids": []}
    for entry in config:
        slug = entry["slug"]
        post = posts.get(slug) or {}
        if "items" not in post:
            # Пост не прочитан — оставляем прошлый состав, а не обнуляем подборку.
            if slug in previous:
                data[slug] = previous[slug]
            print(f"! {slug}: {post.get('error', 'пост не прочитан')} — состав не меняю")
            continue
        groups: list[dict[str, Any]] = []
        skipped: list[str] = []
        for item in post["items"]:
            href, status = resolver.resolve(item)
            link = f"t.me/{item['channel']}/" + (f"{item['topic_id']}/" if item.get("topic_id") else "") + str(item["message_id"])
            if status == "missing":
                skipped.append(f"{link}: нет на сайте — синхронизирую")
                if item["channel"] == "abhazbooking":
                    targets["hotel_source_ids"].append(item["message_id"])
                elif item.get("topic_id"):
                    targets["kv_topic_ids"].append(item["topic_id"])
                else:
                    targets["kv_message_ids"].append(item["message_id"])
                continue
            if status == "hidden":
                skipped.append(f"{link}: объект снят с сайта")
                continue
            # Города — в порядке первого появления в посте; объект — один раз.
            if any(href in g["hrefs"] for g in groups):
                continue
            label = item["section"] or "ДРУГИЕ ЛОКАЦИИ"
            group = next((g for g in groups if g["label"] == label), None)
            if group is None:
                group = {"label": label, "hrefs": []}
                groups.append(group)
            group["hrefs"].append(href)
        data[slug] = {
            "post": f"https://t.me/{entry['channel']}/{entry['message_id']}",
            "groups": [g for g in groups if g["hrefs"]],
            "skipped": skipped,
        }
    for key in targets:
        targets[key] = sorted(set(targets[key]))
    return data, targets


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="не читать Telegram, пересопоставить сохранённые ссылки")
    args = parser.parse_args()

    config = load_json(CONFIG, [])
    previous = load_json(DATA, {})
    if args.offline:
        posts = {slug: {"items": entry.get("items", [])} for slug, entry in (load_json(TARGETS, {}).get("raw") or {}).items()}
    else:
        posts = asyncio.run(fetch_posts(config))
    data, targets = build(config, posts, previous)

    TARGETS.parent.mkdir(parents=True, exist_ok=True)
    TARGETS.write_text(json.dumps({**targets, "raw": posts}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    changed = data != previous
    if changed:
        DATA.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for slug, entry in data.items():
        total = sum(len(g["hrefs"]) for g in entry["groups"])
        print(f"{slug}: объектов {total} в {len(entry['groups'])} городах ({entry['post']})")
        for line in entry.get("skipped", []):
            print(f"  - {line}")
    pending = sum(len(v) for v in targets.values())
    if pending:
        print(f"Нет на сайте, отдаю в синк: {targets}")
    print(f"changed={'true' if changed else 'false'}")
    print(f"pending={pending}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
