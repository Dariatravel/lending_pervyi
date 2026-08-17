#!/usr/bin/env python3
"""Добавить/обновить одну запись в существующей зоне Cloud DNS.

Нужен для точечных записей вроде media.абхазберег.рф → CDN, когда зона уже
живёт в облаке и пересоздавать её целиком (yc_dns.py) незачем.

    DNS_ZONE=xn--80aacbklan7f0b.xn--p1ai. \
    RECORD_NAME=media RECORD_TYPE=CNAME \
    RECORD_VALUE=062ff875d101b985.topology.gslb.yccdn.ru. \
    python3 tools/yc_dns_record.py

RECORD_NAME указывается без зоны (media, _acme-challenge.media) или "@" для
корня. Повторный запуск безопасен: upsert заменяет запись с тем же именем.
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


def api(url: str, token: str | None = None, payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(url, data=data, method="POST" if data else "GET")
    request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as error:
        raise SystemExit(f"Облако ответило {error.code}: {error.read().decode(errors='replace')[:400]}")


def iam_token() -> str:
    key = json.loads(os.environ["YC_SA_KEY_JSON"])
    import jwt  # PyJWT

    now = int(time.time())
    assertion = jwt.encode(
        {"aud": IAM_URL, "iss": key["service_account_id"], "iat": now, "exp": now + 360},
        key["private_key"], algorithm="PS256", headers={"kid": key["id"]},
    )
    return api(IAM_URL, payload={"jwt": assertion})["iamToken"]


def main() -> int:
    zone_name = os.environ["DNS_ZONE"].rstrip(".") + "."
    record_name = os.environ["RECORD_NAME"].strip()
    record_type = os.environ["RECORD_TYPE"].strip().upper()
    record_value = os.environ["RECORD_VALUE"].strip()
    ttl = int(os.getenv("RECORD_TTL", "300"))
    full_name = zone_name if record_name in ("@", "") else f"{record_name}.{zone_name}"

    token = iam_token()
    folder = os.environ.get("YC_FOLDER_ID", "").strip()
    if not folder:
        clouds = api(f"{RM_URL}/clouds", token)["clouds"]
        folder = api(f"{RM_URL}/folders?cloudId={clouds[0]['id']}", token)["folders"][0]["id"]

    zones = api(f"{DNS_URL}/zones?folderId={folder}", token).get("dnsZones") or []
    zone = next((z for z in zones if z.get("zone") == zone_name), None)
    if not zone:
        print(f"Зона {zone_name} не найдена в каталоге {folder}.")
        return 1

    result = api(f"{DNS_URL}/zones/{zone['id']}:upsertRecordSets", token, {
        "replacements": [{"name": full_name, "type": record_type, "ttl": ttl,
                          "data": [record_value]}],
    })
    failure = result.get("error")
    if failure:
        print(f"Не удалось: {failure.get('message')}")
        return 1
    print(f"OK: {record_type} {full_name} → {record_value} (ttl {ttl})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
