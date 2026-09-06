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


def api_get(path: str, retries: int = 3) -> dict:
    """GET к check-host.net с повторами при 429.

    IP-адреса GitHub-раннеров общие на тысячи проектов, и лимит запросов
    check-host.net часто выеден чужими прогонами — 429 здесь не «мы сломали»,
    а «не повезло с соседями по IP». Пауза и повтор обычно спасают.
    """
    last_error: Exception | None = None
    for attempt in range(retries):
        request = urllib.request.Request(
            f"{API}{path}",
            headers={"Accept": "application/json", "User-Agent": "abhazbereg-availability-check"},
        )
        try:
            with urllib.request.urlopen(request, timeout=40) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            if error.code != 429 or attempt == retries - 1:
                raise
            last_error = error
            print(f"check-host.net лимитирует (429), жду 90 с и повторяю "
                  f"({attempt + 1}/{retries - 1})…", flush=True)
            time.sleep(90)
    raise last_error  # недостижимо, но успокаивает линтер


def direct_check(url: str) -> bool:
    """Запасная проверка с самого раннера: отвечает ли сайт вообще.

    Когда check-host.net не пускает, главный вопрос «жив ли сайт» всё равно
    должен получить ответ — иначе проверка красная из-за постороннего сервиса.
    Раннер за границей, поэтому российскую специфику так не увидеть, но
    полную недоступность сайта — вполне.
    """
    try:
        request = urllib.request.Request(
            url, headers={"User-Agent": "abhazbereg-availability-check"})
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read(200_000)
            print(f"Прямая проверка с раннера: код {response.status}, "
                  f"{len(body)} байт — сайт отвечает.")
            return 200 <= response.status < 400
    except Exception as error:  # noqa: BLE001
        print(f"Прямая проверка с раннера: САЙТ НЕ ОТВЕЧАЕТ — {error}", file=sys.stderr)
        return False


def node_parts(info) -> tuple[str, str, str]:
    """Код страны, страна и город узла.

    check-host.net описывает узел списком вида
    ["ru", "Russia", "Moscow", "1.2.3.4", ...] — берём первые три поля.
    """
    if isinstance(info, (list, tuple)):
        values = list(info) + ["", "", ""]
        return str(values[0] or ""), str(values[1] or ""), str(values[2] or "")
    if isinstance(info, dict):
        return "", str(info.get("country") or ""), str(info.get("city") or "")
    return "", "", ""


def describe(node: str, info) -> str:
    """Человеческая подпись узла: «Russia, Moscow»."""
    _code, country, city = node_parts(info)
    return ", ".join(part for part in (country, city) if part) or node


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

    # Без явного списка сервис берёт узлы случайно, и российских попадает
    # два-три из двадцати пяти — по такой выборке ничего не скажешь. Поэтому
    # сначала спрашиваем полный список точек и перечисляем все российские.
    ru_nodes: list[str] = []
    try:
        hosts = api_get("/nodes/hosts").get("nodes") or {}
        for name, info in hosts.items():
            location = info.get("location") if isinstance(info, dict) else None
            code = (location[0] if isinstance(location, (list, tuple)) and location else "") or ""
            if str(code).lower() == "ru":
                ru_nodes.append(name)
    except Exception as error:  # noqa: BLE001
        print(f"Список узлов получить не удалось ({error}), берём выборку по умолчанию.", flush=True)

    query = f"/check-http?host={urllib.parse.quote(url, safe='')}&max_nodes=30"
    if ru_nodes:
        print(f"Российских точек проверки: {len(ru_nodes)}", flush=True)
        query += "".join(f"&node={urllib.parse.quote(name)}" for name in ru_nodes[:20])

    try:
        started = api_get(query)
    except Exception as error:  # noqa: BLE001
        print(f"Не удалось запустить проверку через check-host.net: {error}", file=sys.stderr)
        print("Переключаюсь на запасную прямую проверку.", flush=True)
        return 0 if direct_check(url) else 1
    if not started.get("ok"):
        print(f"check-host.net отказал: {started}", file=sys.stderr)
        return 0 if direct_check(url) else 1

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
        code, country, _city = node_parts(info)
        russian = code.lower() == "ru" or country.lower().startswith(("russia", "рос"))
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
