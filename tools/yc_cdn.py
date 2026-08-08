#!/usr/bin/env python3
"""Ресурс Cloud CDN — точка, на которую сможет указать абхазберег.рф.

Object Storage отдаёт собственный домен только по HTTP: свой сертификат к
бакету не привязывается. Чтобы сайт открывался по HTTPS на своём домене,
между доменом и бакетом нужен CDN с сертификатом из Certificate Manager.
CDN здесь не ускоритель, а единственное место, куда сертификат прикрепляется.

    python3 tools/yc_cdn.py probe    # хватает ли прав, что уже создано
    python3 tools/yc_cdn.py create   # создать ресурс (платная услуга)
    python3 tools/yc_cdn.py status   # что с ресурсом сейчас

Ресурс создаётся, но домен на него НЕ переключается: DNS меняется отдельно и
только по согласованию. До этого CDN проверяется по своему адресу.
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
CDN_URL = "https://cdn.api.cloud.yandex.net/cdn/v1"

BUCKET = os.getenv("SITE_BUCKET", "abhazbereg-site")
ORIGIN_HOST = f"{BUCKET}.website.yandexcloud.net"
DOMAIN = "xn--80aacbklan7f0b.xn--p1ai"
WWW_DOMAIN = f"www.{DOMAIN}"
CERTIFICATE_ID = os.getenv("YC_CERTIFICATE_ID", "fpq57jgofcg721oapneo")
GROUP_NAME = "abhazbereg-site-origin"


class ApiError(Exception):
    def __init__(self, code: int, body: str):
        super().__init__(f"{code}: {body}")
        self.code = code
        self.body = body


def api(url: str, token: str | None = None, payload: dict | None = None,
        method: str | None = None) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(url, data=data, method=method or ("POST" if data else "GET"))
    request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as error:
        raise ApiError(error.code, error.read().decode(errors="replace"))


def iam_token() -> str:
    raw = os.environ.get("YC_SA_KEY_JSON", "").strip()
    if not raw:
        raise SystemExit("Нет секрета YC_SA_KEY_JSON.")
    key = json.loads(raw)
    import jwt  # PyJWT

    now = int(time.time())
    assertion = jwt.encode(
        {"aud": IAM_URL, "iss": key["service_account_id"], "iat": now, "exp": now + 360},
        key["private_key"], algorithm="PS256", headers={"kid": key["id"]},
    )
    return api(IAM_URL, payload={"jwt": assertion})["iamToken"]


def folder_id(token: str) -> str:
    explicit = os.environ.get("YC_FOLDER_ID", "").strip()
    if explicit:
        return explicit
    clouds = api(f"{RM_URL}/clouds", token).get("clouds") or []
    if not clouds:
        raise SystemExit("Нет доступа ни к одному облаку.")
    folders = api(f"{RM_URL}/folders?cloudId={clouds[0]['id']}", token).get("folders") or []
    if not folders:
        raise SystemExit("В облаке нет папок — задайте YC_FOLDER_ID.")
    return folders[0]["id"]


def find_resource(token: str, folder: str) -> dict | None:
    resources = api(f"{CDN_URL}/resources?folderId={folder}", token).get("resources") or []
    for resource in resources:
        if resource.get("cname") == DOMAIN:
            return resource
    return None


def find_group(token: str, folder: str) -> dict | None:
    groups = api(f"{CDN_URL}/originGroups?folderId={folder}", token).get("originGroups") or []
    for group in groups:
        if group.get("name") == GROUP_NAME:
            return group
    return None


def probe() -> int:
    """Ничего не создаём — только выясняем, что доступно."""
    token = iam_token()
    folder = folder_id(token)
    print(f"Папка: {folder}")

    print("\n=== Доступ к CDN ===")
    try:
        resources = api(f"{CDN_URL}/resources?folderId={folder}", token).get("resources") or []
        print(f"Права на чтение есть. Ресурсов сейчас: {len(resources)}")
        for resource in resources:
            print(f"  • {resource.get('cname')} → {resource.get('id')}")
    except ApiError as error:
        if error.code in (401, 403):
            print("ПРАВ НЕТ. Сервисному аккаунту нужна роль cdn.editor.")
            print("Это единственное, что нельзя сделать самим ключом: выдача ролей")
            print("требует прав администратора облака.")
            return 2
        if error.code == 404:
            print("Провайдер CDN в этом каталоге ещё не активирован.")
        else:
            print(f"Неожиданный ответ: {error}")
            return 1

    print("\n=== Источник ===")
    group = find_group(token, folder)
    print(f"Группа источников «{GROUP_NAME}»: {'есть' if group else 'нет'}")
    print(f"Источником будет: {ORIGIN_HOST}")

    print("\n=== Сертификат ===")
    print(f"Будет привязан: {CERTIFICATE_ID} ({DOMAIN}, {WWW_DOMAIN})")
    return 0


def ensure_provider(token: str, folder: str) -> None:
    """Провайдер CDN активируется в каталоге один раз."""
    try:
        api(f"{CDN_URL}/providers:activate", token,
            {"folderId": folder, "providerType": "gcore"})
        print("Провайдер CDN активирован.")
    except ApiError as error:
        # Повторная активация — не ошибка, так и говорим.
        if "already" in error.body.lower() or error.code == 409:
            print("Провайдер CDN уже активирован.")
        else:
            raise


def create() -> int:
    token = iam_token()
    folder = folder_id(token)

    existing = find_resource(token, folder)
    if existing:
        print(f"Ресурс для {DOMAIN} уже есть: {existing.get('id')}")
        return status()

    ensure_provider(token, folder)

    group = find_group(token, folder)
    if group:
        print(f"Группа источников уже есть: {group['id']}")
    else:
        group = api(f"{CDN_URL}/originGroups", token, {
            "folderId": folder,
            "name": GROUP_NAME,
            "useNext": True,
            "origins": [{"source": ORIGIN_HOST, "enabled": True}],
        })
        # Операция асинхронная: ответ приходит как operation с metadata.
        group_id = (group.get("metadata") or {}).get("originGroupId") or group.get("id")
        print(f"Группа источников создана: {group_id}")
        time.sleep(3)
        group = find_group(token, folder) or {"id": group_id}

    created = api(f"{CDN_URL}/resources", token, {
        "folderId": folder,
        "cname": DOMAIN,
        "origin": {"originGroupId": str(group["id"])},
        "originProtocol": "HTTP",
        "secondaryHostnames": {"values": [WWW_DOMAIN]},
        "sslCertificate": {"type": "CM", "data": {"cm": {"id": CERTIFICATE_ID}}},
        "active": True,
        "options": {
            # Сжатие текста: HTML, CSS и JS поедут к гостю меньшим весом.
            "browserCacheSettings": {"enabled": True, "value": "0"},
            "redirectHttpToHttps": {"enabled": True, "value": True},
        },
    })
    print(f"Ресурс CDN создан: {json.dumps(created, ensure_ascii=False)[:300]}")
    print("\nДомен НЕ переключался — DNS меняется отдельно и по согласованию.")
    time.sleep(5)
    return status()


def status() -> int:
    token = iam_token()
    folder = folder_id(token)
    resource = find_resource(token, folder)
    if not resource:
        print(f"Ресурса для {DOMAIN} нет — сначала create.")
        return 1

    print(f"\nРесурс CDN: {resource.get('id')}")
    print(f"Домен: {resource.get('cname')}")
    print(f"Дополнительные: {(resource.get('secondaryHostnames') or {}).get('values') or '—'}")
    print(f"Активен: {resource.get('active')}")
    certificate = (resource.get('sslCertificate') or {}).get('type')
    print(f"Сертификат: {certificate}")

    # Адрес, на который потом будет указывать домен.
    print(f"\nКогда дойдёт до переключения, домен направляется на:")
    print(f"  {resource.get('cname')}.cdn.yandex.net (CNAME)")
    print("Сейчас этого делать НЕ нужно.")
    return 0


def main() -> int:
    command = sys.argv[1] if len(sys.argv) > 1 else "probe"
    actions = {"probe": probe, "create": create, "status": status}
    if command not in actions:
        print(__doc__)
        return 1
    try:
        return actions[command]()
    except ApiError as error:
        print(f"Облако ответило {error.code}: {error.body}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
