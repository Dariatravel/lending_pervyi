#!/usr/bin/env python3
"""Принять применённые изменения в watch-state.

watch_telegram_updates.py пишет сигнатуры обнаруженных изменений в
output/telegram-watch-pending-state.json. Этот скрипт вызывается в
автосинке ПОСЛЕ успешного применения изменений: переносит сигнатуры в
output/telegram-watch-state.json, чтобы то же изменение не попадало в
отчёты и не пересинкивалось повторно каждый час. Если синк упал —
скрипт не вызывается, и изменение честно всплывёт в следующем прогоне.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "output" / "telegram-watch-state.json"
PENDING_PATH = ROOT / "output" / "telegram-watch-pending-state.json"


def main() -> int:
    if not PENDING_PATH.exists():
        print("pending-файла нет — принимать нечего.")
        return 0
    pending = json.loads(PENDING_PATH.read_text(encoding="utf-8")).get("items") or {}
    if not pending:
        print("pending пуст — принимать нечего.")
        return 0
    if not STATE_PATH.exists():
        print("watch-state не найден — пропускаю (базовая линия ещё не создана).", file=sys.stderr)
        return 0

    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    items = state.setdefault("items", {})
    for key, payload in pending.items():
        items[key] = payload
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    PENDING_PATH.unlink(missing_ok=True)
    print(f"Принято изменений в watch-state: {len(pending)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
