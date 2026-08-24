#!/usr/bin/env python3
"""Ежедневные снимки с веб-камер для страницы /veb-kamery-abhazii/.

Разрешение владельцев камер (ООО «Система» / APSNY.CAMERA и A-MOBILE.CAMERA)
на публикацию одного кадра в сутки с указанием источника получено Дарьей
в августе 2026.

Для каждой камеры из data/webcams.json:
- A-MOBILE: скачивается их готовое превью preview/<channel>.jpeg;
- APSNY: у их API спрашивается адрес потока (POST cams.stream, как делает
  их собственный сайт), затем ffmpeg забирает один кадр.

Кадр проверяется (JPEG-магия, ненулевой размер), масштабируется до 960px
и заливается в бакет под постоянным именем media/webcams/<id>.jpg с коротким
кэшем (1 час), затем чистится CDN-кэш этих путей. Если камера не ответила —
на сайте остаётся вчерашний снимок, а карточка без снимка прячет картинку сама.

Обложки камер — служебные снимки без srcset, поэтому WebP-варианты им
не нужны (правило о вариантах касается объектных фото, на которые страницы
ссылаются по всем ширинам).

Запуск: GitHub Actions webcams-snapshots.yml (ежедневно 15:00 МСК).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from yandex_storage import _s3_client, load_yandex_env  # noqa: E402

REGISTRY = ROOT / "data" / "webcams.json"
BUCKET = "abhazbereg-media"
CDN_DOMAIN = "media.xn--80aacbklan7f0b.xn--p1ai"
APSNY_STREAM_API = "https://proxy-api.cyxym.net/bigbrother/v2?cams.stream"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36 abhazbereg-webcams"
TIMEOUT = 30

CDN_URL = "https://cdn.api.cloud.yandex.net/cdn/v1"
RM_URL = "https://resource-manager.api.cloud.yandex.net/resource-manager/v1"
IAM_URL = "https://iam.api.cloud.yandex.net/iam/v1/tokens"


def fetch_bytes(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return response.read(20_000_000)


def post_form(url: str, fields: dict[str, str]) -> str:
    boundary = uuid.uuid4().hex
    body = "".join(
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n"
        for k, v in fields.items()
    ) + f"--{boundary}--\r\n"
    request = urllib.request.Request(
        url,
        data=body.encode(),
        headers={
            "User-Agent": UA,
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Origin": "https://apsny.camera",
            "Referer": "https://apsny.camera/",
        },
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return response.read(200_000).decode("utf-8", errors="replace")


def apsny_preview_url(channel: str) -> str:
    """Готовый снимок камеры APSNY.

    Их API cams.stream в ответе называет и адрес превью — постоянный путь
    apsny.camera/img/camera/<канал>/preview.jpg (проверено первым прогоном
    24.08.2026), поэтому кадр не нужно вырезать из потока.
    """
    return f"https://apsny.camera/img/camera/{channel}/preview.jpg"


def grab_frame(stream_url: str, out_path: Path) -> bool:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        print("    ffmpeg не найден")
        return False
    cmd = [
        ffmpeg, "-hide_banner", "-loglevel", "error",
        "-user_agent", UA,
        "-i", stream_url,
        "-frames:v", "1", "-q:v", "3",
        "-vf", "scale='min(960,iw)':-2",
        "-y", str(out_path),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=60)
    except subprocess.TimeoutExpired:
        print("    ffmpeg: таймаут")
        return False
    if proc.returncode != 0:
        print(f"    ffmpeg: {proc.stderr.decode(errors='replace')[:200]}")
        return False
    return out_path.is_file() and out_path.stat().st_size > 0


def looks_like_jpeg(path: Path) -> bool:
    try:
        return path.read_bytes()[:3] == b"\xff\xd8\xff" and path.stat().st_size > 5_000
    except OSError:
        return False


def rescale_jpeg(path: Path) -> None:
    """Превью A-MOBILE бывают большими — ужимаем до 960px тем же ffmpeg."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return
    tmp = path.with_suffix(".scaled.jpg")
    proc = subprocess.run(
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-i", str(path),
         "-vf", "scale='min(960,iw)':-2", "-q:v", "3", "-y", str(tmp)],
        capture_output=True, timeout=60,
    )
    if proc.returncode == 0 and tmp.is_file() and tmp.stat().st_size > 0:
        tmp.replace(path)
    else:
        tmp.unlink(missing_ok=True)


def purge_cdn(paths: list[str]) -> None:
    """Чистка CDN-кэша обновлённых снимков; без ключа облака — мягкий пропуск."""
    key_json = os.environ.get("YC_SA_KEY_JSON", "").strip()
    if not key_json:
        print("YC_SA_KEY_JSON не задан — CDN-кэш не чищу (снимки обновятся по TTL).")
        return
    try:
        import jwt  # PyJWT

        key = json.loads(key_json)
        now = int(time.time())
        assertion = jwt.encode(
            {"aud": IAM_URL, "iss": key["service_account_id"], "iat": now, "exp": now + 360},
            key["private_key"], algorithm="PS256", headers={"kid": key["id"]},
        )

        def api(url: str, token: str | None = None, payload: dict | None = None) -> dict:
            data = json.dumps(payload).encode() if payload is not None else None
            request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
            if token:
                request.add_header("Authorization", f"Bearer {token}")
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.loads(response.read().decode() or "{}")

        token = api(IAM_URL, payload={"jwt": assertion})["iamToken"]
        folder = os.environ.get("YC_FOLDER_ID", "").strip()
        if not folder:
            clouds = api(f"{RM_URL}/clouds", token)["clouds"]
            folder = api(f"{RM_URL}/folders?cloudId={clouds[0]['id']}", token)["folders"][0]["id"]
        resources = api(f"{CDN_URL}/resources?folderId={folder}", token).get("resources") or []
        resource = next((r for r in resources if r.get("cname") == CDN_DOMAIN), None)
        if not resource:
            print(f"CDN-ресурс {CDN_DOMAIN} не найден — пропускаю purge.")
            return
        api(f"{CDN_URL}/cache/{resource['id']}:purge", token, payload={"paths": paths})
        print(f"CDN-кэш очищен: {len(paths)} путей.")
    except Exception as error:  # noqa: BLE001
        print(f"Purge не удался (не критично, обновится по TTL): {error}")


def main() -> int:
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    sources = data["sources"]
    load_yandex_env()
    s3 = _s3_client()

    updated: list[str] = []
    failed: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        for block in data["blocks"]:
            for cam in block["cams"]:
                cam_id, channel, source = cam["id"], cam["channel"], cam["source"]
                out = tmp_dir / f"{cam_id}.jpg"
                print(f"[{block['city']}] {cam['title']} ({source}:{channel})")
                ok = False
                if source == "amobile":
                    preview = sources["amobile"]["preview_base"].replace("{channel}", channel)
                else:
                    preview = apsny_preview_url(channel)
                try:
                    out.write_bytes(fetch_bytes(preview))
                    ok = looks_like_jpeg(out)
                    if ok:
                        rescale_jpeg(out)
                except (urllib.error.URLError, OSError, ValueError) as error:
                    print(f"    превью не скачалось: {error}")
                if not ok:
                    failed.append(f"{cam_id} ({source}:{channel})")
                    continue
                key = f"media/webcams/{cam_id}.jpg"
                s3.upload_file(
                    str(out), BUCKET, key,
                    ExtraArgs={"ContentType": "image/jpeg", "CacheControl": "public, max-age=3600"},
                )
                updated.append(cam_id)
                print(f"    OK → {key} ({out.stat().st_size // 1024} КБ)")

    print(f"\nИтог: обновлено {len(updated)}, не получилось {len(failed)}")
    for name in failed:
        print(f"  ! {name}")
    if updated:
        purge_cdn([f"/media/webcams/{cam_id}.jpg" for cam_id in updated])
    # Полный провал — сигнал (сломался формат API или сеть); частичные пропуски штатны.
    return 1 if not updated else 0


if __name__ == "__main__":
    sys.exit(main())
