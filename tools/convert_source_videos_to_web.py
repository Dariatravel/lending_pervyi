#!/usr/bin/env python3
"""Web-варианты для видео-исходников в бакете (экономия исходящего трафика).

Для каждого media/videos/**/video-XX-source.mp4 без пары video-XX.mp4:
скачать → ffmpeg (960px, H.264 1200k, faststart — параметры штатного
transcode_video из синка) → залить web-вариант рядом.

Исходники НЕ удаляются и ссылки на страницах НЕ меняются — это отдельные
шаги (см. tools/switch_video_links_to_web.py).

Запуск: python3 tools/convert_source_videos_to_web.py --limit 60
Требует ffmpeg (есть на раннерах GitHub Actions; workflow convert-videos-web).
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from yandex_storage import _s3_client  # noqa: E402

BUCKET = "abhazbereg-media"
MAX_WIDTH = 960
BITRATE = "1200k"


def transcode(src: Path, dst: Path) -> bool:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        print("ffmpeg не найден", file=sys.stderr)
        return False
    cmd = [
        ffmpeg, "-y", "-i", str(src),
        "-vf", f"scale='min({MAX_WIDTH},iw)':-2",
        "-c:v", "libx264", "-preset", "veryfast",
        "-b:v", BITRATE, "-maxrate", BITRATE, "-bufsize", "2400k",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        "-c:a", "aac", "-b:a", "96k",
        str(dst),
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return proc.returncode == 0 and dst.exists() and dst.stat().st_size > 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=60, help="Сколько видео обработать за прогон.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    client = _s3_client()
    keys: dict[str, int] = {}
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=BUCKET, Prefix="media/videos/"):
        for obj in page.get("Contents", []):
            keys[obj["Key"]] = obj["Size"]

    todo = sorted(
        key for key in keys
        if key.endswith("-source.mp4") and key.replace("-source.mp4", ".mp4") not in keys
    )
    print(f"исходников без web-пары: {len(todo)}; обрабатываем: {min(len(todo), args.limit)}")
    if args.dry_run:
        for key in todo[: args.limit]:
            print("  ", key)
        return 0

    done = failed = 0
    saved_bytes = 0
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        for key in todo[: args.limit]:
            web_key = key.replace("-source.mp4", ".mp4")
            src = tmp_dir / "src.mp4"
            dst = tmp_dir / "web.mp4"
            for p in (src, dst):
                p.unlink(missing_ok=True)
            try:
                client.download_file(BUCKET, key, str(src))
            except Exception as error:  # noqa: BLE001
                print(f"FAIL download {key}: {error}", file=sys.stderr)
                failed += 1
                continue
            if not transcode(src, dst):
                print(f"FAIL transcode {key}", file=sys.stderr)
                failed += 1
                continue
            try:
                client.upload_file(str(dst), BUCKET, web_key, ExtraArgs={"ContentType": "video/mp4"})
            except Exception as error:  # noqa: BLE001
                print(f"FAIL upload {web_key}: {error}", file=sys.stderr)
                failed += 1
                continue
            done += 1
            saved_bytes += max(0, src.stat().st_size - dst.stat().st_size)
            print(f"OK {web_key} ({src.stat().st_size // 1048576} → {dst.stat().st_size // 1048576} МБ)")

    print(f"готово: {done}, ошибок: {failed}, потенциальная экономия на просмотр: {saved_bytes // 1048576} МБ")
    return 1 if failed and not done else 0


if __name__ == "__main__":
    raise SystemExit(main())
