#!/usr/bin/env python3
"""HTTPS-сертификат на абхазберег.рф в Yandex Certificate Manager.

Ключи YANDEX_S3_* открывают только хранилище файлов. Сертификаты — отдельная
служба облака, и ей нужен авторизованный ключ сервисного аккаунта (JSON).
Положите его в GitHub Secrets как YC_SA_KEY_JSON — дальше всё делает скрипт.

    python3 tools/yc_certificate.py request    # заказать сертификат
    python3 tools/yc_certificate.py status     # что с ним сейчас и чего он ждёт

Домен кириллический, поэтому в API передаём его техническую Punycode-запись.
Yandex Cloud считает абхазберег.рф и xn--80aacbklan7f0b.xn--p1ai одним доменом
и отклоняет запрос, если указать оба написания как отдельные домены.

Подтверждение владения идёт через DNS: облако называет запись, которую нужно
добавить у регистратора. Пока записи нет, сертификат висит в ожидании — это
нормально и ничего не ломает.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

IAM_URL = "https://iam.api.cloud.yandex.net/iam/v1/tokens"
RM_URL = "https://resource-manager.api.cloud.yandex.net/resource-manager/v1"
CM_URL = "https://certificate-manager.api.cloud.yandex.net/certificate-manager/v1"

# По умолчанию — основной домен; через переменные окружения тем же скриптом
# выпускается сертификат для редиректора abhazbereg.com (10.08.2026).
DOMAIN_PUNYCODE = os.getenv("CERT_DOMAIN", "xn--80aacbklan7f0b.xn--p1ai")
CERT_NAME = os.getenv("CERT_NAME", "abhazbereg-site")


def api(url: str, token: str | None = None, payload: dict | None = None,
        method: str | None = None) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(url, data=data, method=method or ("POST" if data else "GET"))
    request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=40) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as error:
        body = error.read().decode(errors="replace")
        raise SystemExit(f"Облако ответило {error.code}: {body}")


def iam_token() -> str:
    """Обменять ключ сервисного аккаунта на временный токен доступа."""
    raw = os.environ.get("YC_SA_KEY_JSON", "").strip()
    if not raw:
        raise SystemExit(
            "Нет секрета YC_SA_KEY_JSON.\n"
            "Создайте авторизованный ключ сервисного аккаунта в консоли Яндекс Облака\n"
            "и положите его целиком (файл JSON) в GitHub Secrets под этим именем."
        )
    try:
        key = json.loads(raw)
    except json.JSONDecodeError as error:
        raise SystemExit(f"YC_SA_KEY_JSON — не JSON: {error}")

    try:
        import jwt  # PyJWT
    except ImportError:
        raise SystemExit("Нет библиотеки PyJWT. Установите: pip install pyjwt cryptography")

    now = int(time.time())
    assertion = jwt.encode(
        {"aud": IAM_URL, "iss": key["service_account_id"], "iat": now, "exp": now + 360},
        key["private_key"],
        algorithm="PS256",
        headers={"kid": key["id"]},
    )
    return api(IAM_URL, payload={"jwt": assertion})["iamToken"]


def folder_id(token: str) -> str:
    """Папка, в которой живёт сертификат. Берём ту, где уже лежит наше облако."""
    explicit = os.environ.get("YC_FOLDER_ID", "").strip()
    if explicit:
        return explicit
    clouds = api(f"{RM_URL}/clouds", token).get("clouds") or []
    if not clouds:
        raise SystemExit("У сервисного аккаунта нет доступа ни к одному облаку.")
    folders = api(f"{RM_URL}/folders?cloudId={clouds[0]['id']}", token).get("folders") or []
    if not folders:
        raise SystemExit("В облаке нет папок — укажите YC_FOLDER_ID вручную.")
    print(f"Облако: {clouds[0].get('name')} | папка: {folders[0].get('name')}")
    return folders[0]["id"]


def find_certificate(token: str, folder: str) -> dict | None:
    certificates = api(f"{CM_URL}/certificates?folderId={folder}", token).get("certificates") or []
    for certificate in certificates:
        if certificate.get("name") == CERT_NAME:
            return certificate
    return None


def show(token: str, certificate: dict) -> int:
    """Показать состояние и — главное — какую запись ждёт облако."""
    full = api(f"{CM_URL}/certificates/{certificate['id']}?view=FULL", token)
    status = full.get("status", "?")
    print(f"\nСертификат «{CERT_NAME}»: {status}")
    print(f"Домены: {', '.join(full.get('domains') or [])}")

    if status == "ISSUED":
        print("\nСертификат выпущен.")
        print("Но одного его для переключения домена НЕ хватает: Object Storage")
        print("отдаёт собственный домен только по HTTP. Чтобы абхазберег.рф работал")
        print("по HTTPS, нужен ресурс Cloud CDN с этим сертификатом — он и будет")
        print("той точкой, на которую укажет домен. Только после этого меняем DNS.")
        return 0

    challenges = full.get("challenges") or []
    dns_challenges = [c for c in challenges if c.get("type") == "DNS"]
    if not dns_challenges:
        print("\nОблако ещё не выдало проверочную запись — повторите через минуту.")
        return 1

    cname_challenges = [
        challenge for challenge in dns_challenges
        if (challenge.get("dnsChallenge") or {}).get("type") == "CNAME"
        or challenge.get("dnsType") == "CNAME"
    ]
    if cname_challenges:
        dns_challenges = cname_challenges

    print("\nЧтобы облако убедилось, что домен ваш, добавьте у регистратора "
          "(Рег.ру → Домены → абхазберег.рф → DNS-серверы и управление зоной):\n")
    for challenge in dns_challenges:
        dns = challenge.get("dnsChallenge") or {}
        name = dns.get("name") or challenge.get("dnsName", "")
        value = dns.get("value") or challenge.get("dnsValue", "")
        record_type = dns.get("type") or challenge.get("dnsType", "CNAME")
        print(f"  Тип:      {record_type}")
        print(f"  Имя:      {name}")
        print(f"  Значение: {value}\n")
    print("После добавления записи подождите 15–30 минут и запустите status ещё раз.")
    return 0


def request_certificate() -> int:
    token = iam_token()
    folder = folder_id(token)

    existing = find_certificate(token, folder)
    if existing:
        print("Такой сертификат уже заказан — новый не создаю.")
        return show(token, existing)

    created = api(
        f"{CM_URL}/certificates/requestNew",
        token,
        {
            "folderId": folder,
            "name": CERT_NAME,
            "description": "Сайт абхазберег.рф в Object Storage",
            "domains": [DOMAIN_PUNYCODE, f"www.{DOMAIN_PUNYCODE}"],
            "challengeType": "DNS",
        },
    )
    print(f"Сертификат заказан: {created.get('id', '—')}")
    time.sleep(5)
    certificate = find_certificate(token, folder)
    return show(token, certificate) if certificate else 1


def status() -> int:
    token = iam_token()
    folder = folder_id(token)
    certificate = find_certificate(token, folder)
    if not certificate:
        print("Сертификат ещё не заказан — сначала request.")
        return 1
    return show(token, certificate)


def main() -> int:
    command = sys.argv[1] if len(sys.argv) > 1 else "status"
    if command == "request":
        return request_certificate()
    if command == "status":
        return status()
    print(__doc__)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
