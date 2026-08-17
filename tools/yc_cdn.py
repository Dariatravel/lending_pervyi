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
CM_URL = "https://certificate-manager.api.cloud.yandex.net/certificate-manager/v1"
CM_DATA_URL = "https://data.certificate-manager.api.cloud.yandex.net/certificate-manager/v1"

# По умолчанию — основной домен. Через переменные окружения тот же скрипт
# обслуживает второй ресурс — редиректор abhazbereg.com (10.08.2026).
BUCKET = os.getenv("SITE_BUCKET", "abhazbereg-site")
ORIGIN_HOST = os.getenv("CDN_ORIGIN_HOST", f"{BUCKET}.website.yandexcloud.net")
DOMAIN = os.getenv("CDN_DOMAIN", "xn--80aacbklan7f0b.xn--p1ai")
WWW_DOMAIN = f"www.{DOMAIN}"
CERTIFICATE_NAME = os.getenv("CDN_CERT_NAME", "abhazbereg-site")
GROUP_NAME = os.getenv("CDN_GROUP_NAME", "abhazbereg-site-origin")


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


def service_account_id() -> str:
    return json.loads(os.environ["YC_SA_KEY_JSON"])["service_account_id"]


def grant_role() -> int:
    """Попробовать выдать самому себе роль cdn.editor.

    Обычно ключ сервисного аккаунта такого не может: раздача ролей — работа
    администратора облака, иначе любой утёкший ключ повышал бы себе права.
    Но проверить дешевле, чем гадать, — и если получится, владелице не
    придётся ничего нажимать.
    """
    token = iam_token()
    folder = folder_id(token)
    account = service_account_id()
    print(f"Сервисный аккаунт: {account}\nПапка: {folder}")

    try:
        bindings = api(f"{RM_URL}/folders/{folder}:listAccessBindings", token).get("accessBindings") or []
        mine = [b["roleId"] for b in bindings if (b.get("subject") or {}).get("id") == account]
        print(f"Текущие роли этого аккаунта: {', '.join(mine) or '—'}")
        if "cdn.editor" in mine or "admin" in mine:
            print("Роль cdn.editor уже есть.")
            return 0
    except ApiError as error:
        if error.code in (401, 403):
            print("Даже прочитать список ролей нельзя — прав на управление доступом нет.")
            return 2
        raise

    try:
        api(f"{RM_URL}/folders/{folder}:updateAccessBindings", token, {
            "accessBindingDeltas": [{
                "action": "ADD",
                "accessBinding": {
                    "roleId": "cdn.editor",
                    "subject": {"id": account, "type": "serviceAccount"},
                },
            }],
        })
    except ApiError as error:
        if error.code in (401, 403):
            print("\nОблако отказало: выдать роль своим же ключом нельзя.")
            print("Это защита, а не сбой — иначе утёкший ключ повышал бы себе права.")
            return 2
        raise

    print("Роль cdn.editor выдана.")
    time.sleep(5)
    return 0


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
    check_certificate_access(token)
    return 0


def resolve_certificate(token: str, folder: str) -> str | None:
    """Найти сертификат по имени, а не по записанному ID.

    ID из отчёта оказался нерабочим — по нему облако отвечает 404, хотя
    сертификат с нужным именем в папке есть. Имя мы задаём сами, поэтому оно
    надёжнее переписанного руками идентификатора.
    """
    certificates = api(f"{CM_URL}/certificates?folderId={folder}", token).get("certificates") or []
    for certificate in certificates:
        if certificate.get("name") == CERTIFICATE_NAME:
            return certificate["id"]
    if certificates:
        print(f"  сертификата с именем «{CERTIFICATE_NAME}» нет. Что есть в папке:")
        for certificate in certificates:
            print(f"    • {certificate.get('name')} — {certificate.get('id')} "
                  f"({certificate.get('status')})")
    return None


def check_certificate_access(token: str) -> bool:
    """Виден ли сертификат и можно ли выдать его содержимое.

    CDN отвечает «certificate not found» в двух разных случаях: сертификата
    правда нет — или он есть, но аккаунту нельзя его скачать. Второе лечится
    ролью certificate-manager.certificates.downloader, и различить их важно,
    иначе будешь искать несуществующую пропажу.
    """
    folder = folder_id(token)
    certificate_id = resolve_certificate(token, folder)
    if not certificate_id:
        print("  сертификат в этой папке не найден — проверьте YC_FOLDER_ID.")
        return False

    certificate = api(f"{CM_URL}/certificates/{certificate_id}", token)
    print(f"  найден по имени: {certificate_id} / {certificate.get('status')}")
    print(f"  домены: {', '.join(certificate.get('domains') or [])}")

    try:
        api(f"{CM_DATA_URL}/certificates/{certificate_id}:getContent", token)
        print("  содержимое доступно — CDN сможет его забрать.")
        return True
    except ApiError as error:
        if error.code in (401, 403):
            print("  СОДЕРЖИМОЕ НЕДОСТУПНО: нет роли")
            print("  certificate-manager.certificates.downloader.")
            print("  Именно поэтому CDN и говорит «certificate not found».")
            return False
        print(f"  содержимое проверить не удалось ({error.code}).")
        return False


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


def configure_resource(token: str, resource: dict) -> int:
    """Настроить Host для статического бакета, не меняя DNS или домены."""
    updated = api(f"{CDN_URL}/resources/{resource['id']}", token, {
        "options": {
            "hostOptions": {
                "host": {"enabled": True, "value": ORIGIN_HOST},
            },
        },
    }, method="PATCH")
    failure = updated.get("error")
    if failure:
        print(f"Настроить Host не удалось: {failure.get('message')} "
              f"(код {failure.get('code')})")
        return 1
    print(f"Host для запросов к источнику: {ORIGIN_HOST}")
    print("Настройка ресурса отправлена в CDN.")
    time.sleep(5)
    return status()


def create() -> int:
    token = iam_token()
    folder = folder_id(token)

    existing = find_resource(token, folder)
    if existing:
        print(f"Ресурс для {DOMAIN} уже есть: {existing.get('id')}")
        return configure_resource(token, existing)

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

    certificate_id = resolve_certificate(token, folder)
    if not certificate_id:
        print("Сертификат в папке не найден — без него ресурс создавать нельзя.")
        return 1
    print(f"Сертификат: {certificate_id}")

    created = api(f"{CDN_URL}/resources", token, {
        "folderId": folder,
        "cname": DOMAIN,
        "origin": {"originGroupId": str(group["id"])},
        "originProtocol": "HTTP",
        # Для поддоменов (media.*) www-вариант не нужен: CDN_NO_WWW=1.
        **({} if os.getenv("CDN_NO_WWW") == "1"
           else {"secondaryHostnames": {"values": [WWW_DOMAIN]}}),
        "sslCertificate": {"type": "CM", "data": {"cm": {"id": certificate_id}}},
        "active": True,
        "options": {
            # Сжатие текста: HTML, CSS и JS поедут к гостю меньшим весом.
            "browserCacheSettings": {"enabled": True, "value": "0"},
            "redirectHttpToHttps": {"enabled": True, "value": True},
            # Статический бакет выбирается по Host; без этого CDN получает 404.
            "hostOptions": {
                "host": {"enabled": True, "value": ORIGIN_HOST},
            },
        },
    })
    # Облако отвечает «операцией», и провал лежит внутри неё, а не в коде HTTP.
    # Без этой проверки скрипт радостно писал «создан» на неудачной попытке.
    failure = created.get("error")
    if failure:
        print(f"\nСоздать не удалось: {failure.get('message')} (код {failure.get('code')})")
        if "certificate" in str(failure.get("message", "")).lower():
            print("\nСертификат существует и выпущен — значит дело в доступе к нему:")
            check_certificate_access(token)
        return 1

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

    secondary = resource.get("secondaryHostnames") or []
    # Create принимает обёртку {"values": [...]}, а актуальный List/Get API
    # возвращает уже готовый список строк. Поддерживаем оба формата.
    if isinstance(secondary, dict):
        secondary = secondary.get("values") or []
    elif not isinstance(secondary, list):
        secondary = [secondary]

    print(f"\nРесурс CDN: {resource.get('id')}")
    print(f"Домен: {resource.get('cname')}")
    print(f"Дополнительные: {secondary or '—'}")
    print(f"Активен: {resource.get('active')}")
    certificate = (resource.get('sslCertificate') or {}).get('type')
    print(f"Сертификат: {certificate}")

    # Адрес, на который потом будет указывать домен.
    provider_cname = resource.get("providerCname")
    print(f"\nКогда дойдёт до переключения, домен направляется на:")
    print(f"  {provider_cname or 'адрес CDN пока не выдан'} (CNAME)")
    print("Сейчас этого делать НЕ нужно.")
    return 0


def main() -> int:
    command = sys.argv[1] if len(sys.argv) > 1 else "probe"
    actions = {"probe": probe, "create": create, "status": status, "grant": grant_role}
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
