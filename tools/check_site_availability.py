#!/usr/bin/env python3
"""Проверка доступности сайта из разных городов через check-host.net.

Гости из некоторых регионов жалуются, что сайт не открывается. Хостинг —
GitHub Pages, то есть заграница, и у части российских операторов доступ к нему
пропадает. Этот скрипт просит check-host.net открыть наш сайт с их узлов
(в том числе российских) и показывает, откуда он отвечает, а откуда нет.

Запуск (в GitHub Actions — у раннера свободный интернет):
    python3 tools/check_site_availability.py
    SITE_URL=https://пример.рф python3 tools/check_site_availability.py
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.parse
import urllib.request

API = "https://check-host.net"
DEFAULT_URL = "https://xn--80aacbklan7f0b.xn--p1ai/"


def api_get(path: str) -> dict:
    request = urllib.request.Request(
        f"{API}{path}",
        headers={"Accept": "application/json", "User-Agent": "abhazbereg-availability-check"},
    )
    with urllib.request.urlopen(request, timeout=40) as response:
        return json.loads(response.read().decode("utf-8"))


def describe(node: str, info: dict) -> str:
    """Человеческая подпись узла: «Россия, Москва»."""
    country = info.get("2") or ""
    city = info.get("3") or ""
    return f"{country}, {city}".strip(", ") or node


def verdict(result) -> str:
    """Что вернул узел. Формат ответа check-host.net: [успех, время, текст, код]."""
    if result is None:
        return "нет ответа (узел не успел)"
    if isinstance(result, list) and result:
        item = result[0]
        if isinstance(item, list) and item:
            ok, seconds, message, code = (item + [None] * 4)[:4]
            if ok == 1:
                return f"ОТКРЫЛСЯ за {float(seconds or 0):.2f} c (код {code})"
            return f"НЕ ОТКРЫЛСЯ — {message or 'ошибка соединения'}"
        if isinstance(item, dict):
            return f"НЕ ОТКРЫЛСЯ — {item}"
    return "нет данных"


def main() -> int:
    url = os.environ.get("SITE_URL", DEFAULT_URL)
    print(f"Проверяем: {url}\n", flush=True)

    try:
        started = api_get(f"/check-http?host={urllib.parse.quote(url, safe='')}&max_nodes=25")
    except Exception as error:  # noqa: BLE001
        print(f"Не удалось запустить проверку: {error}", file=sys.stderr)
        return 1
    if not started.get("ok"):
        print(f"check-host.net отказал: {started}", file=sys.stderr)
        return 1

    request_id = started["request_id"]
    nodes = started.get("nodes") or {}
    print(f"Узлов в проверке: {len(nodes)}")
    print(f"Ссылка на результат: {started.get('permanent_link')}\n", flush=True)

    # Узлы отвечают не мгновенно — опрашиваем результат, пока не соберём всё.
    results: dict = {}
    for _ in range(12):
        time.sleep(5)
        try:
            results = api_get(f"/check-result/{request_id}")
        except Exception:  # noqa: BLE001
            continue
        if results and all(value is not None for value in results.values()):
            break

    ru_ok, ru_fail, other_ok, other_fail = [], [], [], []
    for node, info in sorted(nodes.items(), key=lambda kv: describe(kv[0], kv[1])):
        name = describe(node, info)
        line = verdict(results.get(node))
        russian = str(info.get("2") or "").lower().startswith(("ru", "рос"))
        bucket = (ru_ok if "ОТКРЫЛСЯ за" in line else ru_fail) if russian else \
                 (other_ok if "ОТКРЫЛСЯ за" in line else other_fail)
        bucket.append(f"   {name:34} {line}")

    print("=== РОССИЯ ===")
    print("\n".join(ru_ok + ru_fail) or "   российских узлов в проверке не оказалось")
    print("\n=== ОСТАЛЬНОЙ МИР ===")
    print("\n".join(other_ok + other_fail) or "   нет данных")

    total_ru = len(ru_ok) + len(ru_fail)
    print(f"\nИТОГО по России: открылся {len(ru_ok)} из {total_ru}; "
          f"в мире: открылся {len(other_ok)} из {len(other_ok) + len(other_fail)}")
    if ru_fail and not other_fail:
        print("ВЫВОД: за границей сайт открывается, а из России — не везде. "
              "Это подтверждает проблему доступа к зарубежному хостингу.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
