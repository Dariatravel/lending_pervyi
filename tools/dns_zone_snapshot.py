#!/usr/bin/env python3
"""Снимок DNS-зоны домена — перед переносом и для сверки после.

Смена DNS-серверов переносит зону целиком. Всё, что не перенесли, просто
исчезает: подтверждения прав в Яндекс.Вебмастере и Метрике, привязки к
соцсетям, почтовые записи. Поэтому до переключения нужен полный список того,
что в зоне есть сейчас, а после — сверка с ним.

Запускать в GitHub Actions: из песочницы агента внешний DNS недоступен.

    python3 tools/dns_zone_snapshot.py
    ZONE=пример.рф python3 tools/dns_zone_snapshot.py

Ничего не меняет — только читает и печатает.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request

DOH = "https://dns.google/resolve"
ZONE = os.getenv("ZONE", "xn--80aacbklan7f0b.xn--p1ai")

# Что спрашиваем у корня зоны.
ROOT_TYPES = ("SOA", "NS", "A", "AAAA", "MX", "TXT", "CAA")

# Имена, под которыми обычно живут подтверждения и служебные записи. Списка
# «всех поддоменов» в DNS не существует — зону нельзя перечислить снаружи,
# поэтому проверяем распространённые и наши собственные.
SUBDOMAINS = (
    "www", "mail", "smtp", "imap", "pop", "webmail", "autodiscover", "autoconfig",
    "_dmarc", "_domainkey", "mail._domainkey", "yandex._domainkey",
    "_acme-challenge", "_acme-challenge.www",
    "m", "api", "cdn", "static", "blog", "shop", "lk", "test", "dev",
)
SUB_TYPES = ("A", "AAAA", "CNAME", "TXT", "MX")


def resolve(name: str, record_type: str) -> list[str]:
    query = urllib.parse.urlencode({"name": name, "type": record_type})
    request = urllib.request.Request(f"{DOH}?{query}", headers={"Accept": "application/dns-json"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.loads(response.read().decode())
    except Exception as error:  # noqa: BLE001
        return [f"(ошибка запроса: {error})"]
    answers = data.get("Answer") or []
    return [a.get("data", "") for a in answers if a.get("data")]


def main() -> int:
    print(f"Снимок зоны: {ZONE}")
    print("Источник: публичный DNS. Записи, скрытые от внешнего мира, сюда не попадут.\n")

    print("=" * 70)
    print("КОРЕНЬ ЗОНЫ")
    print("=" * 70)
    found_any = False
    for record_type in ROOT_TYPES:
        values = resolve(ZONE, record_type)
        if not values:
            continue
        found_any = True
        print(f"\n{record_type}:")
        for value in values:
            print(f"   {value}")

    if not found_any:
        print("Ничего не ответило — проверьте имя зоны.", file=sys.stderr)
        return 1

    print("\n" + "=" * 70)
    print("ПОДДОМЕНЫ (проверяем распространённые имена)")
    print("=" * 70)
    for sub in SUBDOMAINS:
        name = f"{sub}.{ZONE}"
        lines: list[str] = []
        for record_type in SUB_TYPES:
            values = [v for v in resolve(name, record_type) if not v.startswith("(ошибка")]
            for value in values:
                lines.append(f"   {record_type:6} {value}")
        if lines:
            print(f"\n{name}")
            print("\n".join(lines))

    print("\n" + "=" * 70)
    print("ЧТО С ЭТИМ ДЕЛАТЬ")
    print("=" * 70)
    print("Перед сменой DNS-серверов перенести в новую зону всё перечисленное,")
    print("кроме SOA и NS — их создаёт сам новый провайдер.")
    print("Особое внимание записям TXT: в них живут подтверждения прав")
    print("Яндекс.Вебмастера, Метрики и привязки к другим сервисам.")
    print("После переноса запустить этот же снимок и сравнить построчно.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
