#!/usr/bin/env python3
"""«Быстрый старт» для видео в бакете: служебный блок (moov) — в начало файла.

Видео из комментариев к постам («Дополнительные обзоры») и часть роликов
экскурсий заливались как есть, без faststart: блок moov с описанием ролика
лежит в конце файла. Телефону приходится сначала докачать хвост 20–30 МБ
через Range-запросы (CDN такие хвосты не кэширует, первый байт через 4–7 с),
и до этого <video> показывает чёрный квадрат и 00:00. Гости решают, что
видео не работает (жалоба Дарьи 25.09.2026).

Инструмент проходит по видео бакета, находит файлы с moov в конце и
пересобирает их ffmpeg'ом БЕЗ перекодирования (-c copy -movflags +faststart):
картинка и звук не меняются, меняется только порядок блоков. Файл заливается
под тем же ключом; список путей пишется в output/faststart-fixed.txt — по нему
нужно сбросить кэш CDN (yc cdn cache purge).

    python3 tools/faststart_videos.py --dry-run          # только найти
    python3 tools/faststart_videos.py --limit 80          # починить
Требует ffmpeg (есть на раннерах GitHub Actions; workflow faststart-videos).
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from yandex_storage import _s3_client, load_yandex_env, upload_file  # noqa: E402

PREFIXES = ("media/hotels/", "media/kvartira/", "media/vezu/", "media/videos/", "media/blog/")
PROBE_BYTES = 262144  # moov в первых 256 КБ = быстрый старт
OUT_PATH = ROOT / "output" / "faststart-fixed.txt"


def list_videos(s3, bucket: str) -> list[dict]:
    keys: list[dict] = []
    for prefix in PREFIXES:
        token = None
        while True:
            kwargs = {"Bucket": bucket, "Prefix": prefix}
            if token:
                kwargs["ContinuationToken"] = token
            page = s3.list_objects_v2(**kwargs)
            for obj in page.get("Contents") or []:
                key = obj["Key"]
                # -source.mp4 — исходники в холодном хранилище, страницы на них
                # не ссылаются; -web.mp4 и обычные video-XX.mp4 проверяем.
                if key.lower().endswith(".mp4") and not key.endswith("-source.mp4"):
                    keys.append({"key": key, "size": int(obj.get("Size") or 0)})
            if not page.get("IsTruncated"):
                break
            token = page.get("NextContinuationToken")
    return keys


def has_faststart(s3, bucket: str, key: str) -> bool:
    resp = s3.get_object(Bucket=bucket, Key=key, Range=f"bytes=0-{PROBE_BYTES - 1}")
    head = resp["Body"].read()
    return b"moov" in head


def remux(src: Path, dst: Path, *, transcode: bool = False) -> bool:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        print("ffmpeg не найден — пересборка невозможна", file=sys.stderr)
        return False
    if transcode:
        # Тяжёлый исходник (например, 60 МБ из Telegram) — сжимаем в web-вариант
        # теми же параметрами, что штатный синк (960px, H.264 1200k).
        codec = ["-vf", "scale='min(960,iw)':-2", "-c:v", "libx264", "-preset", "medium",
                 "-b:v", "1200k", "-maxrate", "1500k", "-bufsize", "3000k",
                 "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k"]
    else:
        codec = ["-c", "copy"]
    proc = subprocess.run(
        [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(src),
         *codec, "-movflags", "+faststart", str(dst)],
        capture_output=True, text=True, timeout=3600, check=False,
    )
    if proc.returncode != 0 or not dst.is_file() or dst.stat().st_size == 0:
        print(f"  ffmpeg не справился: {proc.stderr.strip()[:200]}", file=sys.stderr)
        return False
    with dst.open("rb") as fh:
        if b"moov" not in fh.read(PROBE_BYTES):
            print("  после пересборки moov всё ещё не в начале — пропускаю", file=sys.stderr)
            return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Faststart для видео бакета без перекодирования.")
    parser.add_argument("--limit", type=int, default=80, help="Сколько видео починить за прогон.")
    parser.add_argument("--dry-run", action="store_true", help="Только найти, ничего не менять.")
    parser.add_argument(
        "--transcode-over-mb", type=int, default=0,
        help="Файлы крупнее N МБ не просто пересобрать, а сжать в web-вариант (0 — не сжимать).",
    )
    args = parser.parse_args()

    load_yandex_env()
    bucket = os.environ.get("YANDEX_S3_BUCKET", "abhazbereg-media")
    s3 = _s3_client()

    videos = list_videos(s3, bucket)
    print(f"Видео в бакете (без исходников): {len(videos)}")
    slow: list[dict] = []
    for item in videos:
        try:
            if not has_faststart(s3, bucket, item["key"]):
                slow.append(item)
        except Exception as error:  # noqa: BLE001
            print(f"  не удалось проверить {item['key']}: {error}", file=sys.stderr)
    print(f"С moov в конце (медленный старт): {len(slow)}")
    for item in slow:
        print(f"  {item['key']} ({item['size'] // 1024} КБ)")
    if args.dry_run or not slow:
        return 0

    fixed: list[str] = []
    failed = 0
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        for item in slow[: args.limit]:
            key = item["key"]
            src = tmp / "in.mp4"
            dst = tmp / "out.mp4"
            try:
                s3.download_file(bucket, key, str(src))
                heavy = bool(args.transcode_over_mb) and item["size"] > args.transcode_over_mb * 1024 * 1024
                if not remux(src, dst, transcode=heavy):
                    failed += 1
                    print(f"[fail] {key}: файл не пересобрать (см. ошибку выше)", file=sys.stderr)
                    continue
                upload_file(dst, key, "video/mp4", force=True)
                fixed.append("/" + key)
                print(f"[ok] {key}: {src.stat().st_size // 1024} → {dst.stat().st_size // 1024} КБ")
            except Exception as error:  # noqa: BLE001
                failed += 1
                print(f"[fail] {key}: {error}", file=sys.stderr)
            finally:
                src.unlink(missing_ok=True)
                dst.unlink(missing_ok=True)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(fixed) + ("\n" if fixed else ""), encoding="utf-8")
    print(f"\nПочинено: {len(fixed)}, не удалось: {failed}, осталось: {max(0, len(slow) - args.limit)}")
    print(f"Список для сброса кэша CDN: {OUT_PATH}")
    return 1 if failed and not fixed else 0


if __name__ == "__main__":
    sys.exit(main())
