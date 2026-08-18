#!/usr/bin/env python3
"""Донастройка CDN-ресурса медиа после создания.

Ресурс media.абхазберег.рф создавался скриптом для САЙТА, и вместе с ним
приехала настройка browserCacheSettings=0 («браузеру не кэшировать») — для
страниц она правильная, а для фото и видео вредная: гость перекачивает те же
файлы при каждом просмотре, хотя у объектов стоит immutable на год.

Что делает:
  - browserCacheSettings: выключает подмену — к гостю проходят honest
    заголовки хранилища (public, max-age=31536000, immutable);
  - slice: включает передачу больших файлов кусками — видео стартует быстрее
    и не заставляет край CDN тянуть весь файл ради первого кадра;
  - edgeCacheSettings: кэш на краях 7 суток.

    CDN_DOMAIN=media.xn--80aacbklan7f0b.xn--p1ai python3 tools/yc_cdn_tune_media.py
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

IAM_URL = "https://iam.api.cloud.yandex.net/iam/v1/tokens"
RM_URL = "https://resource-manager.api.cloud.yandex.net/resource-manager/v1"
CDN_URL = "https://cdn.api.cloud.yandex.net/cdn/v1"
DOMAIN = os.getenv("CDN_DOMAIN", "media.xn--80aacbklan7f0b.xn--p1ai")


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
    token = iam_token()
    folder = os.environ.get("YC_FOLDER_ID", "").strip()
    if not folder:
        clouds = api(f"{RM_URL}/clouds", token)["clouds"]
        folder = api(f"{RM_URL}/folders?cloudId={clouds[0]['id']}", token)["folders"][0]["id"]

    resources = api(f"{CDN_URL}/resources?folderId={folder}", token).get("resources") or []
    resource = next((r for r in resources if r.get("cname") == DOMAIN), None)
    if not resource:
        print(f"Ресурс {DOMAIN} не найден.")
        return 1
    resource_id = resource["id"]
    print(f"Ресурс: {resource_id} ({DOMAIN})")

    result = api(f"{CDN_URL}/resources/{resource_id}", token, method="PATCH", payload={
        "options": {
            # Выключаем подмену: заголовки кэша диктует хранилище (immutable год).
            "browserCacheSettings": {"enabled": False, "value": "0"},
            # Большие файлы — кусками: видео стартует с первых байтов.
            "slice": {"enabled": True, "value": True},
            # Кэш на краях: неделя (файлы неизменяемые, вариантов имён нет).
            "edgeCacheSettings": {"enabled": True, "defaultValue": "604800"},
        },
    })
    failure = result.get("error")
    if failure:
        print(f"Не удалось обновить: {failure.get('message')}")
        return 1
    print("Опции обновлены: browserCache — по заголовкам хранилища, slice — вкл, edge — 7 суток.")
    print("Конфигурация разъезжается по узлам несколько минут.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
