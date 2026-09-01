#!/usr/bin/env python3
"""Будочка-редиректор для abhazbereg.ru: каждый старый адрес → своя страница.

В отличие от abhazbereg.com (там все пути один в один переносятся на новый
домен), у Тильды адреса не совпадают с новым сайтом. Яндекс-хранилище не
умеет x-amz-website-redirect-location (отвечает NotImplemented), поэтому
на каждый путь из data/old-site-redirects.json кладётся крошечная
страница-переезд: мгновенный meta refresh + rel=canonical на точную
страницу абхазберег.рф. Поисковики склеивают такие страницы с целевыми
(так работала и переадресация самой Тильды), гость переезжает мгновенно.

Неизвестные пути ловит error.html с переездом на главную.

    python3 tools/build_ru_redirector.py           # создать/обновить и проверить
    python3 tools/build_ru_redirector.py --verify  # только проверить
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

ROOT = Path(__file__).resolve().parents[1]
MAP_PATH = ROOT / "data" / "old-site-redirects.json"
BUCKET = "abhazbereg-ru-redirect"
ENDPOINT = os.getenv("ENDPOINT", "https://storage.yandexcloud.net")
TARGET_HOST_PUNY = "https://xn--80aacbklan7f0b.xn--p1ai"
TARGET_HOST_HUMAN = "https://абхазберег.рф"

PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="0;url={puny}">
<link rel="canonical" href="{human}">
<script>location.replace("{puny}");</script>
<title>Страница переехала — АБХАЗБЕРЕГ</title>
</head>
<body>
<p>Страница переехала: <a href="{puny}">{human}</a></p>
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
    return path.lstrip("/") or "index.html"


def redirect_page(target: str) -> bytes:
    return PAGE_TEMPLATE.format(puny=f"{TARGET_HOST_PUNY}{target}",
                                human=f"{TARGET_HOST_HUMAN}{target}").encode("utf-8")


def make_public(s3) -> None:
    try:
        s3.put_bucket_acl(Bucket=BUCKET, ACL="public-read")
        print("Публичное чтение: включено через ACL бакета.")
        return
    except ClientError as error:
        print(f"ACL бакета: {error.response['Error'].get('Code')} — пробуем bucket policy.")
    policy = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": "*",
            "Action": "s3:GetObject",
            "Resource": f"arn:aws:s3:::{BUCKET}/*",
        }],
    }
    try:
        s3.put_bucket_policy(Bucket=BUCKET, Policy=json.dumps(policy))
        print("Публичное чтение: включено через bucket policy.")
    except ClientError as error:
        print(f"Bucket policy: {error.response['Error'].get('Code')} — "
              "если проверка ниже покажет 403, публичный доступ включается "
              "в консоли: бакет abhazbereg-ru-redirect → Настройки → "
              "Публичный доступ → «Чтение объектов».")


def build() -> int:
    redirects = json.loads(MAP_PATH.read_text(encoding="utf-8"))["redirects"]
    s3 = s3_client()

    try:
        s3.head_bucket(Bucket=BUCKET)
        print(f"Бакет {BUCKET} уже есть.")
    except ClientError:
        s3.create_bucket(Bucket=BUCKET)
        print(f"Бакет {BUCKET} создан.")

    make_public(s3)

    s3.put_bucket_website(Bucket=BUCKET, WebsiteConfiguration={
        "IndexDocument": {"Suffix": "index.html"},
        "ErrorDocument": {"Key": "error.html"},
    })
    print("Website-режим включён (index.html / error.html).")

    def put(key: str, body: bytes) -> None:
        try:
            s3.put_object(Bucket=BUCKET, Key=key, Body=body, ACL="public-read",
                          ContentType="text/html; charset=utf-8",
                          CacheControl="public, max-age=3600")
        except ClientError as error:
            if error.response["Error"].get("Code") in ("AccessDenied", "NotImplemented"):
                s3.put_object(Bucket=BUCKET, Key=key, Body=body,
                              ContentType="text/html; charset=utf-8",
                              CacheControl="public, max-age=3600")
            else:
                raise

    count = 0
    for path, value in sorted(redirects.items()):
        target = value["to"] if isinstance(value, dict) else value
        put(path_to_key(path), redirect_page(target))
        count += 1
    put("error.html", redirect_page("/"))

    # Короткие ссылки для рассылок (data/short-links*.json): работают и на
    # abhazbereg.ru — кладём и «ключ/index.html» (путь со слэшем), и просто
    # «ключ» (путь без слэша), чтобы срабатывали оба написания.
    shorts = 0
    for name in ("short-links.json", "short-links-generated.json"):
        try:
            links = json.loads((ROOT / "data" / name).read_text(encoding="utf-8")).get("links") or {}
        except (OSError, json.JSONDecodeError):
            links = {}
        for key, href in sorted(links.items()):
            page = redirect_page(str(href))
            put(f"{key}/index.html", page)
            put(key, page)
            shorts += 1
    print(f"Загружено страниц-переездов: {count} + error.html + коротких ссылок {shorts}")
    return 0


def fetch(url: str) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            return response.status, response.read().decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8", errors="ignore")


def verify() -> int:
    redirects = json.loads(MAP_PATH.read_text(encoding="utf-8"))["redirects"]
    base = f"http://{BUCKET}.website.yandexcloud.net"
    samples = ["/", "/catalog", "/tpost/granica",
               "/tproduct/994323046982-grant-otel",
               "/page62959751.html"]
    tproducts = [p for p in redirects if p.startswith("/tproduct/")]
    samples += tproducts[::max(1, len(tproducts) // 3)][:3]

    failures = 0
    print(f"\nПроверяю {base}")
    for path in dict.fromkeys(samples):
        value = redirects.get(path)
        want = (value["to"] if isinstance(value, dict) else value) if value else "/"
        status, body = fetch(base + path)
        ok = status == 200 and f"{TARGET_HOST_PUNY}{want}" in body
        print(f"  {'OK  ' if ok else 'ПЛОХО'} {path} → {status}, переезд на {want}: {'да' if ok else 'НЕТ'}")
        if not ok:
            failures += 1

    status, body = fetch(base + "/takogo-puti-net-12345")
    ok = TARGET_HOST_PUNY in body
    print(f"  {'OK  ' if ok else 'ПЛОХО'} неизвестный путь → {status}, страница-переезд: {'да' if ok else 'НЕТ'}")
    if not ok:
        failures += 1

    print(f"\nИтог: провалов {failures}")
    return 1 if failures else 0


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
