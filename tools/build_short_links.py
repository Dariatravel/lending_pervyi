#!/usr/bin/env python3
"""Короткие ссылки для рассылок: /pamyatka → /blog/pamyatka-turistu-abkhazia/.

Реестр — data/short-links.json. Для каждого ключа собирается страничка
<ключ>/index.html с мгновенным переездом (meta refresh), canonical на цель
и noindex — чтобы короткий адрес не конкурировал со статьёй в поиске.
Цель обязана существовать в собранном сайте, иначе скрипт падает.

Запуск: python3 tools/build_short_links.py [--check]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "short-links.json"

STUB = """<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8"/>
<meta http-equiv="refresh" content="0;url={href}"/>
<link rel="canonical" href="https://абхазберег.рф{href}"/>
<meta name="robots" content="noindex"/>
<title>Открываем страницу — АБХАЗБЕРЕГ</title></head>
<body><p>Открываем страницу: <a href="{href}">{href}</a></p></body></html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="только показать, ничего не менять")
    args = parser.parse_args()

    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    links = payload.get("links") or {}
    broken = 0
    for key, href in sorted(links.items()):
        target = ROOT / href.strip("/") / "index.html"
        if not target.is_file():
            print(f"  ! цель не найдена: /{key} → {href}")
            broken += 1
            continue
        out_dir = ROOT / key
        if not args.check:
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "index.html").write_text(STUB.format(href=href), encoding="utf-8")
        print(f"  {'будет' if args.check else 'готово'}: /{key} → {href}")
    print(f"\nИтог: ссылок {len(links)}, целей не найдено {broken}")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
