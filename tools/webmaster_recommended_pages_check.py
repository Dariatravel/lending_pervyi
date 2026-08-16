#!/usr/bin/env python3
"""Проверка важных страниц сайта — тех, что Вебмастер показывает в топе.

Для каждой страницы: код ответа, время ответа, наличие title и canonical,
запрет индексации. Нужна, чтобы заметить пропажу страницы из поиска раньше,
чем это покажет Вебмастер.

Список страниц: data/webmaster-key-pages.json (если файла нет — берётся
встроенный список топа из Вебмастера).

Запуск:
    python3 tools/webmaster_recommended_pages_check.py
    python3 tools/webmaster_recommended_pages_check.py --strict   # выход 1 при проблемах
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = ROOT / "output" / "webmaster_pages_health.txt"
PAGES_FILE = ROOT / "data" / "webmaster-key-pages.json"
ORIGIN = "https://xn--80aacbklan7f0b.xn--p1ai"  # абхазберег.рф в punycode — для http-запроса
TIMEOUT = 20

DEFAULT_PATHS = [
    "/",
    "/blog/",
    "/podborki/",
    "/blog/veyp-i-elektronnye-sigarety-abhaziya/",
    "/blog/marshrutki-ot-granitsy-psou/",
    "/blog/duty-free-na-granitse-psou/",
    "/blog/kak-projti-granicu-psou/",
    "/blog/chto-takoe-citrusovyy-abhaziya/",
    "/blog/vremya-v-abhazii-moskovskoe/",
    "/blog/edinyj-bilet-v-abhaziyu/",
    "/blog/ldzaa-shtil-pitsunda-volny/",
    "/blog/poezdka-v-abhaziyu-s-zhivotnym/",
]

TITLE_RX = re.compile(r"<title[^>]*>(.*?)</title>", re.S | re.I)
CANONICAL_RX = re.compile(r'<link[^>]*rel=["\']canonical["\'][^>]*>', re.I)
HREF_RX = re.compile(r'href=["\']([^"\']+)["\']', re.I)
NOINDEX_RX = re.compile(r'<meta[^>]*name=["\']robots["\'][^>]*noindex|<meta[^>]*noindex[^>]*robots', re.I)


def load_paths() -> list[str]:
    if PAGES_FILE.is_file():
        try:
            data = json.loads(PAGES_FILE.read_text(encoding="utf-8"))
            paths = data if isinstance(data, list) else data.get("paths", [])
            if paths:
                return [str(p) for p in paths]
        except json.JSONDecodeError:
            pass
    return DEFAULT_PATHS


def check(path: str) -> dict:
    url = f"{ORIGIN}{path}"
    request = urllib.request.Request(url, headers={"User-Agent": "abhazbereg-health-check/1.0"})
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            body = response.read().decode("utf-8", errors="ignore")
            status = response.status
    except urllib.error.HTTPError as error:
        return {"path": path, "status": error.code, "ms": int((time.monotonic() - started) * 1000),
                "title": "", "canonical": "", "noindex": False, "error": ""}
    except Exception as error:  # noqa: BLE001 — сеть, DNS, TLS
        return {"path": path, "status": 0, "ms": int((time.monotonic() - started) * 1000),
                "title": "", "canonical": "", "noindex": False, "error": str(error)[:90]}

    title = TITLE_RX.search(body)
    canonical_tag = CANONICAL_RX.search(body)
    canonical = ""
    if canonical_tag:
        href = HREF_RX.search(canonical_tag.group(0))
        canonical = href.group(1) if href else ""
    return {
        "path": path,
        "status": status,
        "ms": int((time.monotonic() - started) * 1000),
        "title": re.sub(r"\s+", " ", title.group(1)).strip() if title else "",
        "canonical": canonical,
        "noindex": bool(NOINDEX_RX.search(body)),
        "error": "",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="выход 1 при проблемах")
    args = parser.parse_args()

    lines = ["Здоровье важных страниц (топ Яндекс.Вебмастера)", ""]
    problems = 0
    for path in load_paths():
        row = check(path)
        # Первый запрос к редкой странице может попасть на холодный узел CDN
        # и ответить за 4–9 секунд — это не поломка сайта. Меряем второй раз
        # и верим прогретому замеру; красним только если медленно оба раза.
        if row["status"] == 200 and row["ms"] > 3000:
            first_ms = row["ms"]
            row = check(path)
            row["cold_first_ms"] = first_ms
        issues = []
        if row["status"] != 200:
            issues.append(f"код {row['status'] or 'нет ответа'}{' — ' + row['error'] if row['error'] else ''}")
        else:
            if not row["title"]:
                issues.append("нет title")
            if not row["canonical"]:
                issues.append("нет canonical")
            if row["noindex"]:
                issues.append("закрыта от индексации")
            if row["ms"] > 3000:
                issues.append(f"медленный ответ {row['ms']} мс")
        mark = "OK  " if not issues else "ПРОБЛЕМА"
        if issues:
            problems += 1
        cold_note = f" (первый запрос {row['cold_first_ms']} мс — холодный кэш CDN)" if row.get("cold_first_ms") else ""
        lines.append(f"[{mark}] {row['path']} — {row['status']}, {row['ms']} мс{cold_note}"
                     + (f" | {'; '.join(issues)}" if issues else ""))
        if row["title"]:
            lines.append(f"         title: {row['title'][:90]}")

    lines.append("")
    lines.append(f"ИТОГО: страниц {len(load_paths())}, с проблемами {problems}")
    text = "\n".join(lines)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(text + "\n", encoding="utf-8")
    print(text)
    print(f"\nОтчёт: {OUT_PATH.relative_to(ROOT)}")
    return 1 if (args.strict and problems) else 0


if __name__ == "__main__":
    sys.exit(main())
