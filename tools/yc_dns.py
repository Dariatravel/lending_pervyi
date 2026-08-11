#!/usr/bin/env python3
"""Зона abhazbereg.com в Yandex Cloud DNS — последний кирпич переезда будочки.

Латинский домен служит редиректором на абхазберег.рф. Его зона переезжает от
Рег.ру к Яндексу по той же причине, что и основная 9 августа: Рег.ру не умеет
направлять корень домена на CDN (у корня по стандарту не может быть CNAME,
а ANAME Рег.ру не поддерживает).

    python3 tools/yc_dns.py create   # зона + четыре записи (повторный запуск безопасен)
    python3 tools/yc_dns.py status   # что в зоне и какие серверы имён указывать в Рег.ру

Сами серверы имён в Рег.ру скрипт НЕ меняет — это делает владелица.
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
DNS_URL = "https://dns.api.cloud.yandex.net/dns/v1"

ZONE = os.getenv("DNS_ZONE", "abhazbereg.com.")           # с точкой на конце
ZONE_NAME = os.getenv("DNS_ZONE_NAME", "abhazbereg-com")  # имя ресурса в облаке
CDN_CNAME = os.getenv("DNS_CDN_CNAME", "062ff875d101b985.topology.gslb.yccdn.ru.")
ACME_VALUE = os.getenv("DNS_ACME_VALUE", "fpqjsjjk3soljtbjsb3e.cm.yandexcloud.net.")

# Полный состав зоны. Старые A-записи GitHub Pages сюда не переносятся:
# корень должен вести на CDN-редиректор. NS и SOA облако создаёт само.
RECORD_SETS = [
    {"name": ZONE, "type": "ANAME", "ttl": 300, "data": [CDN_CNAME]},
    {"name": f"www.{ZONE}", "type": "CNAME", "ttl": 300, "data": [CDN_CNAME]},
    {"name": f"_acme-challenge.{ZONE}", "type": "CNAME", "ttl": 300, "data": [ACME_VALUE]},
    {"name": f"_acme-challenge.www.{ZONE}", "type": "CNAME", "ttl": 300, "data": [ACME_VALUE]},
]


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
    folders = api(f"{RM_URL}/folders?cloudId={clouds[0]['id']}", token).get("folders") or []
    return folders[0]["id"]


def find_zone(token: str, folder: str) -> dict | None:
    zones = api(f"{DNS_URL}/zones?folderId={folder}", token).get("dnsZones") or []
    for zone in zones:
        if zone.get("zone") == ZONE:
            return zone
    return None


def show(token: str, zone: dict) -> int:
    print(f"\nЗона: {zone.get('zone')} (id {zone.get('id')})")
    records = api(f"{DNS_URL}/zones/{zone['id']}:listRecordSets", token).get("recordSets") or []
    print("Записи:")
    name_servers: list[str] = []
    for record in records:
        values = ", ".join(record.get("data") or [])
        print(f"  {record.get('type'):6} {record.get('name'):40} {values}")
        if record.get("type") == "NS" and record.get("name") == ZONE:
            name_servers = record.get("data") or []

    print("\nЧтобы переключить домен, в Рег.ру для abhazbereg.com указать серверы имён:")
    for server in name_servers or ["ns1.yandexcloud.net.", "ns2.yandexcloud.net."]:
        print(f"  {server.rstrip('.')}")
    print("Скрипт этого НЕ делает — только владелица, и только когда решит.")

    # Записи должны совпасть с планом — сверяем построчно.
    existing = {(r.get("name"), r.get("type")): sorted(r.get("data") or []) for r in records}
    problems = 0
    for wanted_record in RECORD_SETS:
        key = (wanted_record["name"], wanted_record["type"])
        if existing.get(key) != sorted(wanted_record["data"]):
            print(f"РАСХОЖДЕНИЕ: {key} = {existing.get(key)}, ждали {wanted_record['data']}")
            problems += 1
    if not problems:
        print("\nВсе четыре записи на месте и совпадают с планом.")
    return 1 if problems else 0


def create() -> int:
    token = iam_token()
    folder = folder_id(token)

    zone = find_zone(token, folder)
    if zone:
        print(f"Зона {ZONE} уже существует — создавать не нужно.")
    else:
        try:
            operation = api(f"{DNS_URL}/zones", token, {
                "folderId": folder,
                "name": ZONE_NAME,
                "zone": ZONE,
                "publicVisibility": {},
            })
        except ApiError as error:
            if error.code in (401, 403):
                print("Прав на Cloud DNS нет — нужна роль dns.editor на каталог.")
                return 2
            raise
        failure = operation.get("error")
        if failure:
            print(f"Создать зону не удалось: {failure.get('message')}")
            return 1
        print(f"Зона {ZONE} создана.")
        time.sleep(3)
        zone = find_zone(token, folder)
        if not zone:
            print("Зона не находится после создания — повторите status через минуту.")
            return 1

    # upsert: существующие записи с теми же именами заменяются, повторный
    # запуск не плодит дублей.
    result = api(f"{DNS_URL}/zones/{zone['id']}:upsertRecordSets", token,
                 {"replacements": RECORD_SETS})
    failure = result.get("error")
    if failure:
        print(f"Записи внести не удалось: {failure.get('message')}")
        return 1
    print("Четыре записи внесены.")
    time.sleep(2)
    return show(token, zone)


def status() -> int:
    token = iam_token()
    folder = folder_id(token)
    zone = find_zone(token, folder)
    if not zone:
        print(f"Зоны {ZONE} нет — сначала create.")
        return 1
    return show(token, zone)


def main() -> int:
    command = sys.argv[1] if len(sys.argv) > 1 else "status"
    actions = {"create": create, "status": status}
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
