#!/usr/bin/env python3
"""Проверка: правились ли в Telegram посты, из которых сделаны статьи блога.

Просьба Дарьи 18.10.2026: статьи блога должны следовать за правками постов.
Раньше блог собирался только вручную, и правки постов («Памятка туристу»,
детские документы) месяцами не доходили до сайта.

Источник статьи берётся со страницы (строка «Источник: пост Телеграм
@abhazbereg/<id>»). Состояние — data/blog-sources.json: для каждой статьи
хеш текста поста на момент публикации.

Режимы статьи:
- auto   — статья собирается синком блога (пост в POST_IDS
           scripts/sync_blog_from_abhazbereg.py): при правке поста автосинк
           запускает пересборку (blog-sync.yml);
- manual — текст статьи правился вручную или собран другим генератором:
           пересборка затёрла бы правки, поэтому только уведомление Дарье
           (один раз на каждую новую версию поста).

Новая статья без записи получает текущий хеш как исходный (правкой не
считается).

Запуск:
    python3 tools/check_blog_source_edits.py              # проверить
    python3 tools/check_blog_source_edits.py --accept 2256,abhazbooking:4852
        # принять текущий текст постов (после пересборки статей)

Вывод для GitHub Actions: строки auto_ids=…, notify_count=…; текст
уведомления — output/blog-edits-notify.txt.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

STATE_PATH = ROOT / "data" / "blog-sources.json"
NOTIFY_PATH = ROOT / "output" / "blog-edits-notify.txt"
SOURCE_RE = re.compile(r'class="blog-source"[^>]*>.*?t\.me/(abhazbereg|abhazbooking)/(\d+)', re.S)
SITE = "https://абхазберег.рф"


def text_hash(text: str) -> str:
    norm = unicodedata.normalize("NFKC", text or "").replace("\xa0", " ")
    norm = re.sub(r"\s+", " ", norm).strip()
    return hashlib.sha1(norm.encode("utf-8")).hexdigest()[:16]


def load_state() -> dict:
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sync_post_ids() -> set[tuple[str, int]]:
    """Посты, которые умеет пересобирать синк блога (POST_IDS + канал из POST_META)."""
    import sync_blog_from_abhazbereg as sb

    out = set()
    for mid in sb.POST_IDS:
        channel = str((sb.POST_META.get(mid) or {}).get("channel") or sb.CHANNEL)
        out.add((channel, int(mid)))
    return out


def page_sources() -> dict[str, tuple[str, int]]:
    out: dict[str, tuple[str, int]] = {}
    for path in sorted((ROOT / "blog").glob("*/index.html")):
        text = path.read_text(encoding="utf-8", errors="replace")
        if 'http-equiv="refresh"' in text[:800]:
            continue
        m = SOURCE_RE.search(text)
        if m:
            out[path.parent.name] = (m.group(1), int(m.group(2)))
    return out


async def fetch_hashes(keys: list[tuple[str, int]]) -> dict[tuple[str, int], str | None]:
    from telegram_runtime import connected_telegram_client
    from watch_telegram_updates import DEFAULT_API_HASH, DEFAULT_API_ID, load_env_files

    load_env_files()
    api_id = int(os.getenv("TELEGRAM_API_ID", str(DEFAULT_API_ID)))
    api_hash = os.getenv("TELEGRAM_API_HASH", DEFAULT_API_HASH)
    session = os.getenv("TG_SESSION", str(ROOT / "tg_session"))
    result: dict[tuple[str, int], str | None] = {}
    by_channel: dict[str, list[int]] = {}
    for channel, mid in keys:
        by_channel.setdefault(channel, []).append(mid)
    async with connected_telegram_client(session, api_id, api_hash, receive_updates=False) as client:
        for channel, ids in by_channel.items():
            for start in range(0, len(ids), 90):
                chunk = ids[start:start + 90]
                messages = await client.get_messages(channel, ids=chunk)
                for mid, message in zip(chunk, messages):
                    result[(channel, mid)] = None if message is None else text_hash(message.message or "")
    return result


def parse_ids(raw: str) -> set[tuple[str, int]]:
    out = set()
    for part in (raw or "").split(","):
        part = part.strip()
        if not part:
            continue
        channel, _, mid = part.rpartition(":")
        out.add((channel or "abhazbereg", int(mid)))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--accept", default="", help="принять текущий текст постов: 2256,abhazbooking:4852")
    args = parser.parse_args()

    state = load_state()
    articles: dict = state.setdefault("articles", {})
    sources = page_sources()
    syncable = sync_post_ids()
    current = asyncio.run(fetch_hashes(sorted(set(sources.values()))))

    accept = parse_ids(args.accept)
    auto_ids: list[str] = []
    notify: list[str] = []
    changed_state = False
    for slug, (channel, mid) in sorted(sources.items()):
        now = current.get((channel, mid))
        entry = articles.get(slug)
        if entry is None or entry.get("channel") != channel or entry.get("message_id") != mid:
            entry = {"channel": channel, "message_id": mid, "hash": now,
                     "mode": entry.get("mode", "auto") if entry else "auto"}
            articles[slug] = entry
            changed_state = True
            continue
        if (channel, mid) in accept and now:
            if entry.get("hash") != now:
                entry["hash"] = now
                entry.pop("notified_hash", None)
                changed_state = True
            continue
        if now is None:
            if entry.get("notified_hash") != "deleted":
                notify.append(f"• пост удалён из канала: {SITE}/blog/{slug}/ (t.me/{channel}/{mid})")
                entry["notified_hash"] = "deleted"
                changed_state = True
            continue
        if now == entry.get("hash"):
            continue
        mode = entry.get("mode", "auto")
        if mode == "auto" and (channel, mid) in syncable:
            auto_ids.append(f"{channel}:{mid}" if channel != "abhazbereg" else str(mid))
        elif entry.get("notified_hash") != now:
            notify.append(f"• {SITE}/blog/{slug}/ — пост t.me/{channel}/{mid} изменён; "
                          "статью правили вручную, обновить её нужно руками")
            entry["notified_hash"] = now
            changed_state = True

    if changed_state:
        save_state(state)
    NOTIFY_PATH.parent.mkdir(parents=True, exist_ok=True)
    NOTIFY_PATH.write_text("\n".join(notify) + ("\n" if notify else ""), encoding="utf-8")
    print(f"Статей с источником: {len(sources)}; правки → пересборка: {auto_ids or 'нет'}; уведомлений: {len(notify)}")
    for line in notify:
        print(line)
    print(f"auto_ids={','.join(auto_ids)}")
    print(f"notify_count={len(notify)}")
    print(f"state_changed={'true' if changed_state else 'false'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
