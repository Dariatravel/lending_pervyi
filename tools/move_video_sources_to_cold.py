#!/usr/bin/env python3
"""Перевести видео-исходники бакета в холодное хранение (COLD).

Только media/videos/**/video-XX-source.mp4, и только те, у кого есть
web-пара И на которые не ссылается ни одна страница сайта (двойная
защита: замороженный в COLD объект отдаётся дороже/медленнее — он не
должен раздаваться посетителям).

Запуск: python3 tools/move_video_sources_to_cold.py [--apply]
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from yandex_storage import _s3_client  # noqa: E402

BUCKET = "abhazbereg-media"


def main() -> int:
    apply = "--apply" in sys.argv
    client = _s3_client()

    keys: dict[str, dict] = {}
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=BUCKET, Prefix="media/videos/"):
        for obj in page.get("Contents", []):
            keys[obj["Key"]] = obj

    referenced: set[str] = set()
    for page_path in list(ROOT.glob("hotels/*/index.html")) + list(ROOT.glob("kvartira/*/index.html")):
        html = page_path.read_text(encoding="utf-8")
        for key in keys:
            if key.endswith("-source.mp4") and key in html:
                referenced.add(key)

    moved = skipped_ref = skipped_noweb = already = 0
    total_bytes = 0
    for key, obj in sorted(keys.items()):
        if not key.endswith("-source.mp4"):
            continue
        if str(obj.get("StorageClass") or "STANDARD").upper() == "COLD":
            already += 1
            continue
        if key in referenced:
            skipped_ref += 1
            print("пропуск (страница ссылается):", key)
            continue
        if key.replace("-source.mp4", ".mp4") not in keys:
            skipped_noweb += 1
            print("пропуск (нет web-пары):", key)
            continue
        if apply:
            client.copy_object(
                Bucket=BUCKET,
                Key=key,
                CopySource={"Bucket": BUCKET, "Key": key},
                StorageClass="COLD",
                MetadataDirective="COPY",
            )
        moved += 1
        total_bytes += obj["Size"]

    print(f'{"ПЕРЕВЕДЕНО" if apply else "DRY-RUN, будет переведено"}: {moved} '
          f"({total_bytes / 1024 / 1024 / 1024:.2f} ГБ) | уже COLD: {already} | "
          f"пропущено со ссылками: {skipped_ref} | без web-пары: {skipped_noweb}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
