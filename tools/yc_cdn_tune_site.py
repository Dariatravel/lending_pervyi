#!/usr/bin/env python3
"""Сжатие текста на CDN сайта абхазберег.рф.

25.09.2026 расшифровка Lighthouse показала: HTML, CSS, JS и
data/catalog-index.json уходят гостю несжатыми — лишние ~460 КБ на главной
(~1,1 с на медленном мобильном) и ~400 КБ на странице отеля (~2,1 с).
В yc_cdn.py у создания ресурса стоит комментарий «Сжатие текста», но самой
опции там нет — сжатие так и не включилось.

Действия (CDN_DOMAIN — домен ресурса, по умолчанию сайт):
  status  — напечатать текущие опции ресурса (только чтение);
  gzip-on — включить gzip на краях CDN и очистить кэш узлов;
  gzip-off — откат: выключить gzip и очистить кэш.

Опции отправляются ПОЛНЫМ набором: берём текущие с ресурса и меняем только
сжатие. Иначе можно потерять hostOptions (без него бакет отвечает 404) и
редирект на https.

    CDN_DOMAIN=xn--80aacbklan7f0b.xn--p1ai python3 tools/yc_cdn_tune_site.py status
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
DOMAIN = os.getenv("CDN_DOMAIN", "xn--80aacbklan7f0b.xn--p1ai")


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
        raise SystemExit(f"Облако ответило {error.code}: {error.read().decode(errors='replace')[:600]}")


def iam_token() -> str:
    key = json.loads(os.environ["YC_SA_KEY_JSON"])
    import jwt  # PyJWT

    now = int(time.time())
    assertion = jwt.encode(
        {"aud": IAM_URL, "iss": key["service_account_id"], "iat": now, "exp": now + 360},
        key["private_key"], algorithm="PS256", headers={"kid": key["id"]},
    )
    return api(IAM_URL, payload={"jwt": assertion})["iamToken"]


def find_resource(token: str) -> dict | None:
    folder = os.environ.get("YC_FOLDER_ID", "").strip()
    if not folder:
        clouds = api(f"{RM_URL}/clouds", token)["clouds"]
        folder = api(f"{RM_URL}/folders?cloudId={clouds[0]['id']}", token)["folders"][0]["id"]
    resources = api(f"{CDN_URL}/resources?folderId={folder}", token).get("resources") or []
    return next((r for r in resources if r.get("cname") == DOMAIN), None)


def wait_operation(token: str, operation: dict) -> dict:
    """Облако отвечает операцией; ждём её конца и возвращаем итог."""
    op_id = operation.get("id")
    for _ in range(30):
        if operation.get("done") or not op_id:
            return operation
        time.sleep(2)
        operation = api(f"https://operation.api.cloud.yandex.net/operations/{op_id}", token)
    return operation


def set_gzip(token: str, resource: dict, enabled: bool) -> int:
    options = dict(resource.get("options") or {})
    before = json.dumps(options, ensure_ascii=False, sort_keys=True)
    options["compressionOptions"] = {"gzipOn": {"enabled": True, "value": enabled}}
    result = wait_operation(token, api(
        f"{CDN_URL}/resources/{resource['id']}", token, method="PATCH",
        payload={"options": options},
    ))
    if result.get("error"):
        print(f"Не удалось обновить: {result['error'].get('message')}")
        return 1

    # Контроль: все прежние опции на месте, сжатие в нужном положении.
    after_options = (api(f"{CDN_URL}/resources/{resource['id']}", token).get("options") or {})
    lost = [key for key in json.loads(before) if key not in after_options and key != "compressionOptions"]
    print(f"Опции после: {json.dumps(after_options, ensure_ascii=False, sort_keys=True)}")
    if lost:
        print(f"ВНИМАНИЕ: пропали опции {lost} — нужен откат (gzip-off вернёт их из этой копии):")
        print(before)
        return 1
    print(f"Сжатие gzip: {'включено' if enabled else 'выключено'}; прежние опции сохранены.")

    purge = wait_operation(token, api(f"{CDN_URL}/cache/{resource['id']}:purge", token, payload={"paths": []}))
    if purge.get("error"):
        print(f"Кэш не почистился: {purge['error'].get('message')}")
        return 1
    print("Кэш узлов очищен — новые ответы пойдут уже со сжатием. Разъезжается несколько минут.")
    return 0


def main() -> int:
    action = (sys.argv[1] if len(sys.argv) > 1 else "status").strip()
    token = iam_token()
    resource = find_resource(token)
    if not resource:
        print(f"Ресурс {DOMAIN} не найден.")
        return 1
    print(f"Ресурс: {resource['id']} ({DOMAIN})")
    if action == "status":
        print(json.dumps(resource.get("options") or {}, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if action in ("gzip-on", "gzip-off"):
        return set_gzip(token, resource, action == "gzip-on")
    print(f"Неизвестное действие: {action}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
