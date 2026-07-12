#!/usr/bin/env python3
"""Собрать аргументы точечного синка из output/telegram-watch-changed-targets.json.

Печатает либо '--mode targeted --target-hotel-source-ids ... --target-kv-topic-ids ...',
либо пустую строку — тогда вызывающая сторона запускает полный синк (--mode full).
Полный синк на чистом CI-раннере занимает ~2.5 часа (медиа скачиваются заново),
поэтому точечный режим — основной для GitHub Actions.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

TARGETS_PATH = Path(__file__).resolve().parents[1] / "output" / "telegram-watch-changed-targets.json"


def main() -> int:
    try:
        data = json.loads(TARGETS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        print("")
        return 0

    hotels = {str(x) for x in (data.get("hotel_source_ids") or [])}
    topics = {str(x) for x in (data.get("kv_topic_ids") or [])}
    loose_kv = list(data.get("kv_message_ids_without_topic") or [])

    for item in data.get("new_objects") or []:
        if not isinstance(item, dict):
            continue
        if item.get("kind") == "hotel" and item.get("message_id"):
            hotels.add(str(item["message_id"]))
        elif item.get("kind") == "kvartira":
            if item.get("topic_id"):
                topics.add(str(item["topic_id"]))
            else:
                loose_kv.append(item.get("message_id"))

    if loose_kv or not (hotels or topics):
        print("")  # точных целей нет — пусть будет полный синк
        return 0

    args = ["--mode", "targeted"]
    if hotels:
        args += ["--target-hotel-source-ids", ",".join(sorted(hotels, key=int))]
    if topics:
        args += ["--target-kv-topic-ids", ",".join(sorted(topics, key=int))]
    print(" ".join(args))
    return 0


if __name__ == "__main__":
    sys.exit(main())
