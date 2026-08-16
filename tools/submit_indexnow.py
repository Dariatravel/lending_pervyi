#!/usr/bin/env python3
"""Отправка изменённых страниц в IndexNow (Яндекс индексирует за минуты).

Определяет изменённые *.html по git-диапазону (по умолчанию HEAD~1..HEAD —
то, что закоммитил автосинк), превращает их в канонические URL и шлёт одним
POST в https://yandex.com/indexnow. Ключ публичный (лежит на сайте в /ai/),
секретов здесь нет.

Использование:
  python3 tools/submit_indexnow.py                # изменения последнего коммита
  python3 tools/submit_indexnow.py HEAD~5..HEAD   # свой диапазон
  python3 tools/submit_indexnow.py --urls / /blog/  # явный список путей
Ошибки сети не валят пайплайн: выходим с кодом 0 и печатаем предупреждение.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
HOST = "xn--80aacbklan7f0b.xn--p1ai"
KEY = "b67d7f52dcffbe7873f8353e316784a2"
# Ключ обязан лежать в КОРНЕ сайта: зона полномочий ключа = каталог размещения
# (ключ в /ai/ разрешал бы слать только /ai/*). Файл /<key>.txt есть в git,
# но nginx-прокси домена пока отдаёт 404 на новые корневые файлы (как и
# /llms.txt) — IndexNow оживёт, когда хостер уберёт это ограничение.
KEY_LOCATION = f"https://{HOST}/{KEY}.txt"
ENDPOINT = "https://yandex.com/indexnow"

# Разделы, страницы которых имеет смысл переиндексировать
SECTIONS = ("hotels/", "kvartira/", "blog/", "podborki/", "answers/", "about/")


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


def main() -> int:
    args = sys.argv[1:]
    if args and args[0] == "--urls":
        urls = [f"https://{HOST}{p if p.startswith('/') else '/' + p}" for p in args[1:]]
    else:
        rev_range = args[0] if args else "HEAD~1..HEAD"
        urls = changed_urls(rev_range)
    if not urls:
        print("IndexNow: изменённых страниц нет — отправлять нечего.")
        return 0
    # Лимит IndexNow — 10 000 URL за запрос; нам с запасом хватает одного батча.
    payload = {"host": HOST, "key": KEY, "keyLocation": KEY_LOCATION, "urlList": urls[:10000]}
    req = Request(
        ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urlopen(req, timeout=30) as resp:
            print(f"IndexNow: {resp.status} — отправлено {len(urls)} URL")
    except Exception as error:  # noqa: BLE001 — сеть не должна валить автосинк
        print(f"IndexNow: не удалось отправить ({error}) — пропускаю, это не критично.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
