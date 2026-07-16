#!/usr/bin/env python3
"""Переключить ссылки страниц с видео-исходников на web-варианты.

Меняет video-XX-source.mp4 → video-XX.mp4 ТОЛЬКО если web-вариант
реально существует в бакете. Постеры не трогаем (их имена привязаны
к исходнику и продолжают работать).

Запуск: python3 tools/switch_video_links_to_web.py [--apply]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from yandex_storage import _s3_client  # noqa: E402

BUCKET = "abhazbereg-media"


def main() -> int:
    apply = "--apply" in sys.argv
    client = _s3_client()
    keys: set[str] = set()
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=BUCKET, Prefix="media/videos/"):
        for obj in page.get("Contents", []):
            keys.add(obj["Key"])

    src_re = re.compile(r'media/(videos/[^"\']+?)-source\.mp4')
    pages = list(ROOT.glob("hotels/*/index.html")) + list(ROOT.glob("kvartira/*/index.html"))
    switched = skipped = pages_changed = 0
    missing: set[str] = set()
    for page in pages:
        html = page.read_text(encoding="utf-8")

        def repl(match: re.Match) -> str:
            nonlocal switched, skipped
            web_key = f"media/{match.group(1)}.mp4"
            if web_key in keys:
                switched += 1
                return web_key
            skipped += 1
            missing.add(web_key)
            return match.group(0)

        new_html = src_re.sub(repl, html)
        if new_html != html:
            pages_changed += 1
            if apply:
                page.write_text(new_html, encoding="utf-8")

    print(f'{"ЗАПИСАНО" if apply else "DRY-RUN"}: страниц изменено {pages_changed}, '
          f"ссылок переключено {switched}, пропущено (нет web) {skipped}")
    for key in sorted(missing):
        print("  нет web:", key)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
