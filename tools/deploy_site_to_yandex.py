#!/usr/bin/env python3
"""Заливка готового сайта в Yandex Object Storage и проверка результата.

Зачем: HTML, CSS и JS сейчас отдаёт GitHub Pages, и у части российских
операторов до него не достучаться — 8 августа 2026 в сети МТС не отдались
styles.min.css и scripts.min.js, тогда как фотография из Object Storage в той
же сети открылась. Медиа уже в Яндексе; переносим туда и саму страницу.

Запускать в GitHub Actions (workflow yandex-site-hosting.yml): в песочнице
агента облако закрыто сетевой политикой, а ключи YANDEX_S3_* лежат в Secrets.

    python3 tools/deploy_site_to_yandex.py --bucket abhazbereg-site
    python3 tools/deploy_site_to_yandex.py --bucket abhazbereg-site --verify-only
    python3 tools/deploy_site_to_yandex.py --bucket abhazbereg-site --dry-run

Домен скрипт не трогает: до переключения DNS сайт продолжает жить на
GitHub Pages, а бакет проверяется по своему адресу.
"""
from __future__ import annotations

import argparse
import mimetypes
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENDPOINT = os.getenv("ENDPOINT", "https://storage.yandexcloud.net")

# Что именно отдаётся гостю. Всё остальное — исходники и обслуживание, им в
# бакете делать нечего.
INCLUDE_DIRS = (
    "hotels", "kvartira", "podborki", "blog", "karta", "answers", "about",
    "data", "vendor", "app-icons",
)

# Из data/ гостю нужны только эти пять. Остальное — рабочие файлы генераторов:
# catalog-snapshot.json весит 3 МБ, кэш геокодинга и списки для синка клиенту
# не нужны вовсе, а в публичном бакете это лишний вес и лишняя видимость.
PUBLIC_DATA_FILES = {
    "catalog-index.json",
    "blog-posts.json",
    "guest-reviews.json",
    "min-prices-today.json",
    "objects-map-points.json",
}
INCLUDE_FILES = (
    "index.html", "404.html", "offline.html",
    "styles.min.css", "scripts.min.js", "pwa.js", "sw.js",
    "app.webmanifest", "sitemap.xml", "robots.txt",
)

# Файлы подтверждения прав в Яндекс.Вебмастере и Google Search Console.
# В DNS-зоне подтверждающих TXT-записей нет — права держатся только на этих
# файлах. Не залить их значит потерять сайт в обеих панелях сразу после
# переключения домена, вместе со статистикой запросов и переобходом страниц.
VERIFICATION_PATTERNS = ("yandex_*.html", "google*.html", "wmail-*.html")

# Внутри разрешённых папок тоже есть лишнее.
SKIP_DIR_NAMES = {".git", "__pycache__", "node_modules", "media", "output"}
# Несжатые исходники: страницы ссылаются на .min-версии, эти двое только
# занимают место и путают.
SKIP_FILES = {"styles.css", "scripts.js"}
SKIP_SUFFIXES = {".md", ".py", ".pyc", ".log", ".bak"}

# Object Storage отдаёт то, что мы указали при заливке. Ошибиться в типе —
# значит получить CSS, который браузер не применит.
EXTRA_TYPES = {
    ".webmanifest": "application/manifest+json",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
    ".xml": "application/xml; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
}
TEXT_TYPES = {".html": "text/html; charset=utf-8",
              ".css": "text/css; charset=utf-8",
              ".js": "text/javascript; charset=utf-8",
              ".txt": "text/plain; charset=utf-8"}


def content_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in TEXT_TYPES:
        return TEXT_TYPES[suffix]
    if suffix in EXTRA_TYPES:
        return EXTRA_TYPES[suffix]
    guessed, _ = mimetypes.guess_type(path.name)
    return guessed or "application/octet-stream"


def cache_control(path: Path) -> str:
    """Сколько браузеру держать файл у себя.

    HTML перепроверяем всегда: иначе после правки поста гость увидит старую
    карточку. Шрифты и иконки не меняются годами. CSS и JS меняются при каждой
    пересборке, но ссылки на них несут ?v=, поэтому пяти минут достаточно.
    """
    suffix = path.suffix.lower()
    if suffix in (".html", ".json", ".xml"):
        return "no-cache, must-revalidate"
    if suffix in (".woff2", ".woff", ".png", ".svg", ".ico", ".webp", ".jpg", ".jpeg"):
        return "public, max-age=31536000, immutable"
    return "public, max-age=300"


def wanted(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    if any(part in SKIP_DIR_NAMES or part.startswith(".") for part in relative.parts[:-1]):
        return False
    if path.name in SKIP_FILES or path.suffix.lower() in SKIP_SUFFIXES:
        return False
    top = relative.parts[0]
    if len(relative.parts) == 1:
        return path.name in INCLUDE_FILES
    if top == "data":
        return path.name in PUBLIC_DATA_FILES
    return top in INCLUDE_DIRS


def collect() -> list[Path]:
    files: list[Path] = []
    for name in INCLUDE_FILES:
        candidate = ROOT / name
        if candidate.is_file():
            files.append(candidate)
    for pattern in VERIFICATION_PATTERNS:
        for candidate in ROOT.glob(pattern):
            if candidate.is_file():
                files.append(candidate)
    for folder in INCLUDE_DIRS:
        base = ROOT / folder
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if path.is_file() and wanted(path):
                files.append(path)
    return sorted(set(files))


def wave(path: Path) -> int:
    """Порядок заливки: сначала оформление, потом страницы, потом sw.js.

    Иначе гость может получить новый HTML вместе со старым CSS, а service
    worker — закэшировать эту смесь.
    """
    if path.name == "sw.js":
        return 2
    if path.suffix.lower() == ".html":
        return 1
    return 0


def upload(client, bucket: str, files: list[Path], dry_run: bool) -> int:
    sent = 0
    for step in (0, 1, 2):
        batch = [p for p in files if wave(p) == step]
        label = {0: "оформление и данные", 1: "страницы", 2: "service worker"}[step]
        print(f"\n--- Волна {step + 1}: {label} ({len(batch)} файлов) ---", flush=True)
        for path in batch:
            key = str(path.relative_to(ROOT))
            if dry_run:
                print(f"  [пробный прогон] {key} ({content_type(path)})")
                sent += 1
                continue
            client.upload_file(
                str(path), bucket, key,
                ExtraArgs={
                    "ContentType": content_type(path),
                    "CacheControl": cache_control(path),
                    "ACL": "public-read",
                },
            )
            sent += 1
            if sent % 100 == 0:
                print(f"  залито {sent}...", flush=True)
    return sent


def fetch(url: str) -> tuple[int, bytes, str]:
    request = urllib.request.Request(url, headers={"User-Agent": "abhazbereg-deploy-check"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, response.read(), response.headers.get("Content-Type", "")
    except Exception as error:  # noqa: BLE001
        return 0, str(error).encode(), ""


def verify(bucket: str) -> int:
    """Проверить бакет по его собственному адресу — домен ещё на GitHub Pages."""
    base = f"https://{bucket}.website.yandexcloud.net"
    checks = [
        ("/", b"</html>", "text/html"),
        ("/styles.min.css", b"{", "text/css"),
        ("/scripts.min.js", b"", "javascript"),
        ("/offline.html", b"</html>", "text/html"),
        ("/data/catalog-index.json", b"listings", "application/json"),
    ]
    failures = 0
    print(f"Проверяю {base}\n", flush=True)
    for path, needle, expected_type in checks:
        status, body, actual_type = fetch(base + path)
        type_ok = expected_type in actual_type.lower()
        body_ok = needle in body if needle else len(body) > 0
        ok = status == 200 and type_ok and body_ok
        print(f"  {'OK  ' if ok else 'ПЛОХО'} {path:32} код {status}, "
              f"тип «{actual_type or '—'}», {len(body)} байт")
        if not ok:
            failures += 1
            if status != 200:
                print(f"        ответ: {body[:200].decode(errors='replace')}")

    # Страница объекта: именно они открываются у гостей чаще всего, и именно
    # на них ломается адресация вида /hotels/<slug>/ без index.html.
    import json
    index = json.loads((ROOT / "data" / "catalog-index.json").read_text(encoding="utf-8"))
    listing = index["listings"][0]
    slug_path = "/" + ("kvartira" if listing["source_kind"] == "kvartira" else "hotels") \
                + f"/{listing['slug']}/"
    status, body, actual_type = fetch(base + slug_path)
    ok = status == 200 and b"</html>" in body
    print(f"  {'OK  ' if ok else 'ПЛОХО'} {slug_path:32} код {status}, {len(body)} байт "
          f"— адрес папки без index.html")
    if not ok:
        failures += 1

    print(f"\nИтог: провалов {failures}")
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--dry-run", action="store_true",
                        help="показать состав заливки, ничего не отправляя")
    parser.add_argument("--verify-only", action="store_true",
                        help="только проверить уже залитый сайт")
    args = parser.parse_args()

    if args.verify_only:
        return verify(args.bucket)

    files = collect()
    total_mb = sum(p.stat().st_size for p in files) / 1024 / 1024
    print(f"К заливке: {len(files)} файлов, {total_mb:.1f} МБ")
    print("Медиа не заливается — фото и видео уже лежат в бакете abhazbereg-media.\n")

    if args.dry_run:
        upload(None, args.bucket, files, dry_run=True)
        return 0

    import boto3
    client = boto3.client("s3", endpoint_url=ENDPOINT)
    sent = upload(client, args.bucket, files, dry_run=False)
    print(f"\nЗалито файлов: {sent}")
    print("Домен не переключался — сайт по-прежнему открывается с GitHub Pages.")
    return verify(args.bucket)


if __name__ == "__main__":
    raise SystemExit(main())
