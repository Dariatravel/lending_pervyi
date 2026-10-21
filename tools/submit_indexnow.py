#!/usr/bin/env python3
"""Отправка изменённых страниц в IndexNow — Яндексу и Bing.

Определяет изменённые *.html по git-диапазону (по умолчанию HEAD~1..HEAD —
то, что закоммитил автосинк), превращает их в канонические URL и шлёт
отдельными POST-запросами в Яндекс и в Bing (Bing Webmaster; на Bing во многом
опирается поиск ChatGPT — просьба Дарьи 21.10.2026). Ключ публичный, лежит в
корне сайта, секретов здесь нет.

Использование:
  python3 tools/submit_indexnow.py                  # изменения последнего коммита
  python3 tools/submit_indexnow.py HEAD~5..HEAD     # свой диапазон
  python3 tools/submit_indexnow.py --urls / /blog/  # явный список путей
  python3 tools/submit_indexnow.py --sitemap        # все адреса из sitemap.xml
Ответ 200 — принято, 202 — ключ ещё проверяется (повторить на следующий день).
Ошибка одного поисковика не мешает отправке в другой; ошибки сети не валят
пайплайн: выходим с кодом 0 и печатаем предупреждение.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
HOST = "xn--80aacbklan7f0b.xn--p1ai"
KEY = "b67d7f52dcffbe7873f8353e316784a2"
# Ключ обязан лежать в КОРНЕ сайта: зона полномочий ключа = каталог размещения
# (ключ в /ai/ разрешал бы слать только /ai/*). С переезда на Yandex CDN
# корневой /<key>.txt открывается с кодом 200 (проверено 21.10.2026).
KEY_LOCATION = f"https://{HOST}/{KEY}.txt"
ENDPOINTS = (
    ("Яндекс", "https://yandex.com/indexnow"),
    ("Bing", "https://www.bing.com/indexnow"),
)

# Разделы, страницы которых имеет смысл переиндексировать
SECTIONS = ("hotels/", "kvartira/", "blog/", "podborki/", "answers/", "about/")
# Порядок при отправке всей карты сайта: сначала ответы и подборки
SITEMAP_PRIORITY = ("/answers/", "/podborki/")


def changed_urls(rev_range: str) -> list[str]:
    out = subprocess.run(
        ["git", "diff", "--name-only", rev_range],
        cwd=ROOT, capture_output=True, text=True, check=False,
    ).stdout.splitlines()
    urls: set[str] = set()
    for name in out:
        if not name.endswith(".html"):
            continue
        if name == "index.html":
            urls.add(f"https://{HOST}/")
            continue
        if name.endswith("/index.html") and name.startswith(SECTIONS):
            urls.add(f"https://{HOST}/{name[: -len('index.html')]}")
    return sorted(urls)


def sitemap_urls() -> list[str]:
    text = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
    paths = []
    for loc in re.findall(r"<loc>([^<]+)</loc>", text):
        path = urlsplit(loc.strip()).path or "/"
        if path not in paths:
            paths.append(path)
    def rank(path: str) -> int:
        for i, prefix in enumerate(SITEMAP_PRIORITY):
            if path.startswith(prefix):
                return i
        return len(SITEMAP_PRIORITY)
    paths.sort(key=rank)  # sort стабильный: внутри групп — порядок карты сайта
    return [f"https://{HOST}{p}" for p in paths]


def submit(name: str, endpoint: str, urls: list[str]) -> None:
    payload = {"host": HOST, "key": KEY, "keyLocation": KEY_LOCATION, "urlList": urls[:10000]}
    req = Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urlopen(req, timeout=30) as resp:
            status = resp.status
            body = resp.read(300).decode("utf-8", "replace").strip()
    except HTTPError as error:
        status = error.code
        body = error.read(300).decode("utf-8", "replace").strip()
    except Exception as error:  # noqa: BLE001 — сеть не должна валить автосинк
        print(f"IndexNow {name}: не удалось отправить ({error}) — пропускаю, это не критично.")
        return
    note = {200: "принято", 202: "принято, ключ ещё проверяется — повторить завтра"}.get(status, "ошибка")
    print(f"IndexNow {name}: {status} ({note}) — отправлено {min(len(urls), 10000)} URL"
          + (f" | {body[:200]}" if body and status not in (200, 202) else ""))


def main() -> int:
    args = sys.argv[1:]
    if args and args[0] == "--urls":
        urls = [f"https://{HOST}{p if p.startswith('/') else '/' + p}" for p in args[1:]]
    elif args and args[0] == "--sitemap":
        urls = sitemap_urls()
    else:
        rev_range = args[0] if args else "HEAD~1..HEAD"
        urls = changed_urls(rev_range)
    if not urls:
        print("IndexNow: изменённых страниц нет — отправлять нечего.")
        return 0
    # Лимит IndexNow — 10 000 URL за запрос; нам с запасом хватает одного батча.
    for name, endpoint in ENDPOINTS:
        submit(name, endpoint, urls)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
