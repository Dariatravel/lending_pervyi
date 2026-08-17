#!/usr/bin/env python3
"""Мёртвое серверлес-наследие: посмотреть и удалить.

Контейнеры collab_bot / cashback_tracker удалены из кода ещё 13.07.2026 (K4),
но их облачные оболочки остались и капают ~330₽/мес: Serverless Containers,
API Gateway, Container Registry. Скрипт сначала ПОКАЗЫВАЕТ всё это добро
(list), удаление (delete) — отдельной командой и только после того, как
Дарья глазами подтвердила список.

    python3 tools/yc_serverless_cleanup.py list
    python3 tools/yc_serverless_cleanup.py delete   # необратимо!
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
SERVICES = {
    "Serverless Containers": (
        "https://serverless-containers.api.cloud.yandex.net/containers/v1/containers",
        "containers",
    ),
    "API Gateway": (
        "https://serverless-apigw.api.cloud.yandex.net/apigateways/v1/apigateways",
        "apiGateways",
    ),
    "Container Registry": (
        "https://container-registry.api.cloud.yandex.net/container-registry/v1/registries",
        "registries",
    ),
}


def api(url: str, token: str | None = None, payload: dict | None = None,
        method: str | None = None) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(url, data=data, method=method or ("POST" if data else "GET"))
    request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode() or "{}")
    except urllib.error.HTTPError as error:
        body = error.read().decode(errors="replace")
        raise SystemExit(f"Облако ответило {error.code} на {url.split('?')[0]}: {body[:300]}")


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
    folders = api(f"{RM_URL}/folders?cloudId={clouds[0]['id']}", token).get("folders") or []
    return folders[0]["id"]


def collect(token: str, folder: str) -> dict[str, list[dict]]:
    found: dict[str, list[dict]] = {}
    for service, (url, field) in SERVICES.items():
        try:
            items = api(f"{url}?folderId={folder}", token).get(field) or []
        except SystemExit as error:
            print(f"{service}: нет доступа ({error})")
            items = []
        found[service] = items
    return found


def list_all() -> int:
    token = iam_token()
    folder = folder_id(token)
    found = collect(token, folder)
    total = 0
    for service, items in found.items():
        print(f"\n=== {service}: {len(items)} ===")
        for item in items:
            total += 1
            print(f"  id: {item.get('id')}")
            print(f"     имя: {item.get('name')}, создан: {item.get('createdAt', '?')[:10]}, "
                  f"статус: {item.get('status', '—')}")
    print(f"\nВсего объектов: {total}")
    print("Удаление — отдельным запуском с командой delete, после подтверждения Дарьи.")
    return 0


def delete_all() -> int:
    token = iam_token()
    folder = folder_id(token)
    found = collect(token, folder)
    failures = 0
    for service, (url, _field) in SERVICES.items():
        for item in found.get(service) or []:
            item_id = item.get("id")
            name = item.get("name")
            try:
                operation = api(f"{url}/{item_id}", token, method="DELETE")
                error = operation.get("error")
                if error:
                    print(f"ПЛОХО {service} «{name}»: {error.get('message')}")
                    failures += 1
                else:
                    print(f"OK    {service} «{name}» ({item_id}) — удаление запущено")
            except SystemExit as err:
                print(f"ПЛОХО {service} «{name}»: {err}")
                failures += 1
    print(f"\nПровалов: {failures}")
    return 1 if failures else 0


def main() -> int:
    command = sys.argv[1] if len(sys.argv) > 1 else "list"
    if command == "list":
        return list_all()
    if command == "delete":
        return delete_all()
    print(__doc__)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
