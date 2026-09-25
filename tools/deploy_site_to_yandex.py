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
import hashlib
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENDPOINT = os.getenv("ENDPOINT", "https://storage.yandexcloud.net")

# Каталоги, которым в публичном бакете делать нечего. Всё остальное считается
# частью сайта и заливается. Раньше был обратный подход — ручной список
# «что включать», — и он молча потерял одиннадцать разделов (vezu, гайды,
# лендинги городов, go-переходы): на GitHub Pages они были, в бакете нет,
# после переключения домена гости получали 404. Новый раздел, созданный
# генератором, теперь попадает в заливку сам.
SKIP_TOP_DIRS = {
    ".git", ".github", "media", "output", "scripts", "tools", "docs",
    "deploy", "node_modules", "__pycache__",
}

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
    # AI-поиск: визитка для ИИ-агентов и ключ IndexNow (обязан лежать в корне —
    # зона полномочий ключа определяется каталогом его размещения).
    "llms.txt", "b67d7f52dcffbe7873f8353e316784a2.txt",
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
    return top not in SKIP_TOP_DIRS


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
    for base in sorted(ROOT.iterdir()):
        if not base.is_dir() or base.name in SKIP_TOP_DIRS or base.name.startswith("."):
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


def remote_etags(client, bucket: str) -> dict[str, str]:
    """Отпечатки (ETag) всех файлов бакета одним списком — пара LIST-запросов."""
    etags: dict[str, str] = {}
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket):
        for obj in page.get("Contents") or []:
            etags[obj["Key"]] = str(obj.get("ETag") or "").strip('"')
    return etags


def local_md5(path: Path) -> str:
    digest = hashlib.md5()  # noqa: S324 — сравнение с ETag хранилища, не криптография
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def upload(client, bucket: str, files: list[Path], dry_run: bool, remote: dict[str, str] | None = None) -> int:
    """Заливает только изменённые файлы (MD5 ≠ ETag в бакете).

    Раньше каждая выкладка отправляла все ~1100 файлов сайта: за сентябрь
    2026 — 221 выкладка и 227 тысяч PUT-запросов (124 ₽ в месяц), хотя
    автосинк обычно меняет пару страниц. ETag хранилища для обычной (не
    multipart) заливки — это MD5 файла, так что сравнение точное. Файлы с
    multipart-ETag (содержит «-») и отсутствующие в бакете заливаются всегда.
    """
    sent = 0
    skipped = 0
    remote = remote or {}
    for step in (0, 1, 2):
        batch = [p for p in files if wave(p) == step]
        label = {0: "оформление и данные", 1: "страницы", 2: "service worker"}[step]
        print(f"\n--- Волна {step + 1}: {label} ({len(batch)} файлов) ---", flush=True)
        for path in batch:
            key = str(path.relative_to(ROOT))
            etag = remote.get(key, "")
            if etag and "-" not in etag and etag == local_md5(path):
                skipped += 1
                continue
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
    print(f"\nБез изменений, пропущено: {skipped}", flush=True)
    return sent


def fetch(url: str) -> tuple[int, bytes, str]:
    """Запрос с повтором сетевых сбоев.

    Ответ сервера (404, 403) — настоящая поломка заливки, повторять нечего.
    А вот оборванное рукопожатие TLS — это узел облака или сеть раннера:
    25.09.2026 один такой таймаут на «/» покрасил всю выкатку, хотя сайт
    уже был залит целиком и все остальные проверки прошли.
    """
    request = urllib.request.Request(url, headers={"User-Agent": "abhazbereg-deploy-check"})
    last = ""
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.status, response.read(), response.headers.get("Content-Type", "")
        except urllib.error.HTTPError as error:
            return error.code, error.read()[:500], error.headers.get("Content-Type", "")
        except Exception as error:  # noqa: BLE001
            last = str(error)
            if attempt < 2:
                print(f"        сеть подвела ({last}) — попытка {attempt + 2} из 3", flush=True)
                time.sleep(10)
    return 0, last.encode(), ""


def verify(bucket: str) -> int:
    """Проверить бакет по его собственному адресу — домен ещё на GitHub Pages."""
    base = f"https://{bucket}.website.yandexcloud.net"
    checks = [
        ("/", b"</html>", "text/html"),
        ("/styles.min.css", b"{", "text/css"),
        ("/scripts.min.js", b"", "javascript"),
        ("/offline.html", b"</html>", "text/html"),
        ("/data/catalog-index.json", b"listings", "application/json"),
        # Раздел, который однажды выпал из ручного списка заливки целиком.
        ("/vezu/", b"</html>", "text/html"),
        ("/gagra/", b"</html>", "text/html"),
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

    # Файлы подтверждения прав. Их отсутствие не видно на глаз — сайт работает,
    # а из Вебмастера и Google он тихо выпадает.
    for pattern in VERIFICATION_PATTERNS:
        for candidate in ROOT.glob(pattern):
            status, body, _ = fetch(f"{base}/{candidate.name}")
            ok = status == 200 and len(body) > 0
            print(f"  {'OK  ' if ok else 'ПЛОХО'} /{candidate.name:31} код {status} "
                  f"— подтверждение прав")
            if not ok:
                failures += 1

    # Карта: точек должно быть сотни. 24 точки вместо 219 — так выглядела
    # поломка 11.08, когда фильтр генератора отсёк почти все объекты.
    import json
    status, body, _ = fetch(base + "/data/objects-map-points.json")
    try:
        points = len(json.loads(body).get("points") or [])
    except (json.JSONDecodeError, AttributeError):
        points = 0
    ok = status == 200 and points >= 150
    print(f"  {'OK  ' if ok else 'ПЛОХО'} {'/data/objects-map-points.json':32} код {status}, "
          f"точек на карте: {points} (нужно ≥150)")
    if not ok:
        failures += 1

    # Страница объекта: именно они открываются у гостей чаще всего, и именно
    # на них ломается адресация вида /hotels/<slug>/ без index.html.
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
    parser.add_argument("--force-all", action="store_true",
                        help="залить все файлы, даже неизменённые (например, после смены "
                             "Cache-Control или Content-Type — их отпечаток файла не меняет)")
    args = parser.parse_args()
    force_all = args.force_all or os.getenv("DEPLOY_FORCE_ALL", "").strip() in {"1", "true", "yes"}

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
    remote: dict[str, str] = {}
    if not force_all:
        try:
            remote = remote_etags(client, args.bucket)
            print(f"В бакете сейчас файлов: {len(remote)} — неизменённые пропустим.")
        except Exception as error:  # noqa: BLE001
            # Не смогли прочитать список — безопасный путь: залить всё, как раньше.
            print(f"Список бакета не получен ({error}) — заливаю все файлы.")
            remote = {}
    sent = upload(client, args.bucket, files, dry_run=False, remote=remote)
    print(f"\nЗалито файлов: {sent}")
    print("Домен не переключался — сайт по-прежнему открывается с GitHub Pages.")
    return verify(args.bucket)


if __name__ == "__main__":
    raise SystemExit(main())
