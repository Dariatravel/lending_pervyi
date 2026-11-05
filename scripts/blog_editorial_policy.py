"""Защита вручную обновлённых статей от повторного переноса Telegram."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def manual_articles():
    # Ошибка чтения должна остановить перенос, а не разрешить перезапись.
    state = json.loads((ROOT / "data/blog-sources.json").read_text(encoding="utf-8"))
    return {slug: entry for slug, entry in state["articles"].items()
            if entry.get("mode") == "manual"}


def protected_article(slug):
    return slug in manual_articles()


def protected_source(channel, message_id):
    return any(entry.get("channel") == channel and entry.get("message_id") == message_id
               for entry in manual_articles().values())
