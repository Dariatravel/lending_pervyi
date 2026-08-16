#!/usr/bin/env python3
"""Будочка-редиректор для abhazbereg.ru: каждый старый адрес → своя страница.

В отличие от abhazbereg.com (там все пути один в один переносятся на новый
домен), у Тильды адреса не совпадают с новым сайтом: /tproduct/...-grant-otel
должен вести на /hotels/grant-otel-nomera-2664/. Поэтому вместо общего
RedirectAllRequestsTo — по пустому объекту на каждый путь из
data/old-site-redirects.json с заголовком x-amz-website-redirect-location:
статический сайт бакета отвечает на такой объект честным 301.

Неизвестные пути ловит error.html: мгновенный переезд на главную через
meta refresh + canonical.

    python3 tools/build_ru_redirector.py           # создать/обновить и проверить
    python3 tools/build_ru_redirector.py --verify  # только проверить
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

ROOT = Path(__file__).resolve().parents[1]
MAP_PATH = ROOT / "data" / "old-site-redirects.json"
BUCKET = "abhazbereg-ru-redirect"
ENDPOINT = os.getenv("ENDPOINT", "https://storage.yandexcloud.net")
TARGET_HOST = "https://xn--80aacbklan7f0b.xn--p1ai"  # абхазберег.рф

ERROR_HTML = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="0;url=https://абхазберег.рф/">
<link rel="canonical" href="https://абхазберег.рф/">
<title>Сайт переехал — АБХАЗБЕРЕГ</title>
</head>
<body>
<p>Сайт переехал на <a href="https://абхазберег.рф/">абхазберег.рф</a>. Сейчас откроется сам.</p>
</body>
</html>
"""


def s3_client():
    return boto3.client(
        "s3",
        endpoint_url=ENDPOINT,
        region_name=os.getenv("AWS_DEFAULT_REGION", "ru-central1"),
        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
    )


def path_to_key(path: str) -> str:
    key = path.lstrip("/")
    return key or "index.html"


def build() -> int:
    redirects = json.loads(MAP_PATH.read_text(encoding="utf-8"))["redirects"]
    s3 = s3_client()

    try:
        s3.head_bucket(Bucket=BUCKET)
        print(f"Бакет {BUCKET} уже есть.")
    except ClientError:
        s3.create_bucket(Bucket=BUCKET)
        print(f"Бакет {BUCKET} создан.")

    # Будочка отдаёт объекты (пусть и пустые) — публичное чтение обязательно.
    try:
        s3.put_bucket_acl(Bucket=BUCKET, ACL="public-read")
        print("Публичное чтение бакета включено.")
    except ClientError as error:
        print(f"ACL бакета не выставился ({error.response['Error'].get('Code')}) — "
              "пробуем ACL на объектах.")

    s3.put_bucket_website(Bucket=BUCKET, WebsiteConfiguration={
        "IndexDocument": {"Suffix": "index.html"},
        "ErrorDocument": {"Key": "error.html"},
    })
    print("Website-режим включён (index.html / error.html).")

    def put(key: str, body: bytes, **extra) -> None:
        try:
            s3.put_object(Bucket=BUCKET, Key=key, Body=body, ACL="public-read", **extra)
        except ClientError as error:
            if error.response["Error"].get("Code") == "AccessDenied":
                s3.put_object(Bucket=BUCKET, Key=key, Body=body, **extra)
            else:
                raise

    count = 0
    for path, value in sorted(redirects.items()):
        target = value["to"] if isinstance(value, dict) else value
        put(path_to_key(path), b"", WebsiteRedirectLocation=f"{TARGET_HOST}{target}",
            ContentType="text/html")
        count += 1
    put("error.html", ERROR_HTML.encode("utf-8"), ContentType="text/html; charset=utf-8")
    print(f"Загружено переездов: {count} + error.html")
    return 0


def verify() -> int:
    redirects = json.loads(MAP_PATH.read_text(encoding="utf-8"))["redirects"]
    base = f"http://{BUCKET}.website.yandexcloud.net"
    samples = ["/", "/catalog", "/tpost/granica",
               "/tproduct/994323046982-grant-otel",
               "/page62959751.html"]
    # плюс три случайных tproduct для честности
    tproducts = [p for p in redirects if p.startswith("/tproduct/")]
    samples += tproducts[::max(1, len(tproducts) // 3)][:3]

    failures = 0
    print(f"\nПроверяю {base}")
    for path in dict.fromkeys(samples):
        value = redirects.get(path)
        want = (value["to"] if isinstance(value, dict) else value) if value else None
        request = urllib.request.Request(base + path, method="HEAD")
        try:
            # 301 не следуем — он и есть ответ
            opener = urllib.request.build_opener(NoRedirect)
            with opener.open(request, timeout=30) as response:
                status, location = response.status, response.headers.get("Location", "")
        except urllib.error.HTTPError as error:
            status, location = error.code, error.headers.get("Location", "")
        except Exception as error:  # noqa: BLE001
            print(f"  ПЛОХО {path}: {error}")
            failures += 1
            continue
        ok = status == 301 and location == f"{TARGET_HOST}{want}"
        print(f"  {'OK  ' if ok else 'ПЛОХО'} {path} → {status} {location}")
        if not ok:
            failures += 1

    # неизвестный путь должен отдавать error.html с переездом на главную
    status, body = 0, b""
    try:
        with urllib.request.urlopen(base + "/takogo-puti-net-12345", timeout=30) as response:
            status, body = response.status, response.read()
    except urllib.error.HTTPError as error:
        status, body = error.code, error.read()
    ok = "абхазберег.рф".encode() in body or b"xn--80aacbklan7f0b" in body
    print(f"  {'OK  ' if ok else 'ПЛОХО'} неизвестный путь → {status}, страница-переезд: {'да' if ok else 'нет'}")
    if not ok:
        failures += 1

    print(f"\nИтог: провалов {failures}")
    return 1 if failures else 0


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):  # noqa: D102
        return None


def main() -> int:
    if "--verify" in sys.argv:
        return verify()
    code = build()
    if code:
        return code
    time.sleep(5)
    return verify()


if __name__ == "__main__":
    raise SystemExit(main())
