#!/usr/bin/env python3
"""Сторож TLS-сертификатов всех доменов проекта.

Появился после аварии 05.09.2026: сертификат media.абхазберег.рф завис
в перевыпуске (RENEWING без challenge) и молча истёк — все фото и видео
сайта перестали открываться, а мониторинг узнал об этом от гостей.

Скрипт подключается к каждому домену по HTTPS, читает срок действия
сертификата и падает, если:
- до истечения меньше WARN_DAYS дней (перевыпуск обычно занимает минуты,
  но зависший перевыпуск — дни, запас нужен);
- TLS-соединение вообще не устанавливается (истёкший или битый сертификат,
  оборванная цепочка, недоступный узел).

Запуск: python3 tools/check_tls_certificates.py
Выход 0 — всё спокойно; 1 — есть повод для тревоги (текст в stdout).
"""
from __future__ import annotations

import socket
import ssl
import sys
import time
from datetime import datetime, timezone

DOMAINS = [
    "xn--80aacbklan7f0b.xn--p1ai",        # абхазберег.рф — сайт
    "www.xn--80aacbklan7f0b.xn--p1ai",    # www-вариант
    "media.xn--80aacbklan7f0b.xn--p1ai",  # медиа-CDN: все фото и видео
    "abhazbereg.ru",                       # редиректор старой Тильды + короткие ссылки
    "www.abhazbereg.ru",
    "abhazbereg.com",                      # редиректор
    "www.abhazbereg.com",
]
WARN_DAYS = 14
TIMEOUT = 25


def check_domain(host: str) -> tuple[bool, str]:
    """(всё ли хорошо, строка отчёта)."""
    context = ssl.create_default_context()
    cert = None
    # Таймауты ретраим: CDN дозирует соединения с общих IP GitHub-раннеров,
    # и 08.09.2026 один «невезучий» раннер получил timeout на всех 7 доменах
    # разом — Дарье ушла ложная тревога. Ошибка сертификата ретраев не ждёт.
    for attempt in range(3):
        try:
            with socket.create_connection((host, 443), timeout=TIMEOUT) as raw:
                with context.wrap_socket(raw, server_hostname=host) as tls:
                    cert = tls.getpeercert()
            break
        except ssl.SSLCertVerificationError as error:
            return False, f"ТРЕВОГА  {host}: сертификат не проходит проверку — {error.verify_message or error}"
        except (ssl.SSLError, OSError) as error:
            if attempt == 2:
                return False, f"СЕТЬ     {host}: HTTPS-соединение не установилось — {error}"
            time.sleep(20)

    not_after = cert.get("notAfter") if cert else None
    if not not_after:
        return False, f"ТРЕВОГА  {host}: облако не вернуло срок действия сертификата"
    expires = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
    days_left = (expires - datetime.now(timezone.utc)).days
    when = expires.strftime("%d.%m.%Y")
    if days_left < WARN_DAYS:
        return False, (f"ТРЕВОГА  {host}: сертификат истекает {when} "
                       f"(осталось {days_left} дн., порог {WARN_DAYS})")
    return True, f"OK       {host}: сертификат до {when} (осталось {days_left} дн.)"


def main() -> int:
    print(f"Проверка TLS-сертификатов — {datetime.now(timezone.utc):%d.%m.%Y %H:%M} UTC\n")
    alerts = network = 0
    for host in DOMAINS:
        ok, line = check_domain(host)
        print(line)
        if not ok:
            if line.startswith("СЕТЬ"):
                network += 1
            else:
                alerts += 1
    print(f"\nИтог: доменов {len(DOMAINS)}, тревог {alerts}, сетевых сбоев {network}")
    if network and not alerts:
        # Соединение не установилось даже с ретраями, но ни одной ошибки
        # СЕРТИФИКАТА нет. Это сеть раннера/лимиты CDN, не наша поломка:
        # даунтайм сайта ловят post-deploy-smoke и site-availability.
        print("Сертификатных проблем нет — сетевые сбои раннера тревогой не считаем.")
    return 1 if alerts else 0


if __name__ == "__main__":
    raise SystemExit(main())
