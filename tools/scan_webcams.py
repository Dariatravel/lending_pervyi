#!/usr/bin/env python3
"""Разведчик веб-камер Абхазии: APSNY.CAMERA и A-MOBILE.CAMERA.

Оба источника рисуют список камер скриптами, поэтому обычный обход ссылок
ничего не находит. Здесь другой подход: скачать главную и её JS-бандлы,
вытащить из них адреса потоков (m3u8/mpd), служебные API-адреса и упоминания
камер, постучаться в найденные API и сложить всё в артефакт
output/webcams-scan.json для ручного разбора.

Запускать из GitHub Actions (workflow webcams-scan.yml): из песочниц агента
внешние сайты закрыты, с раннеров — открыты.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "webcams-scan.json"

SOURCES = {
    "apsny.camera": "https://apsny.camera/",
    "a-mobile.camera": "https://a-mobile.camera/",
}
TIMEOUT = 25
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36 abhazbereg-webcam-scan"

SCRIPT_SRC_RE = re.compile(r'<script[^>]+src=["\']([^"\']+)["\']', re.I)
STREAM_RE = re.compile(r'[^"\'\s()]+\.(?:m3u8|mpd)(?:\?[^"\'\s()]*)?', re.I)
URL_RE = re.compile(r'https?://[^"\'\s\\<>{}]+')
API_PATH_RE = re.compile(r'["\'](/(?:api|cams?|cameras?|list|data)[^"\'\s]*)["\']', re.I)


def fetch_bytes(url: str, limit: int = 3_000_000) -> tuple[int, bytes]:
    request = Request(url, headers={"User-Agent": UA, "Accept-Language": "ru"})
    try:
        with urlopen(request, timeout=TIMEOUT) as response:
            return response.status, response.read(limit)
    except HTTPError as error:
        return error.code, b""
    except (URLError, OSError, ValueError) as error:
        return 0, f"__error__ {type(error).__name__}: {error}".encode()


def fetch_text(url: str) -> tuple[int, str]:
    status, body = fetch_bytes(url)
    return status, body.decode("utf-8", errors="replace")


def context_snippets(text: str, needle: str, radius: int = 120, limit: int = 3) -> list[str]:
    """Кусочки текста вокруг найденного адреса — рядом обычно имя камеры."""
    snippets = []
    start = 0
    for _ in range(limit):
        index = text.find(needle, start)
        if index < 0:
            break
        snippets.append(text[max(0, index - radius): index + len(needle) + radius].replace("\n", " "))
        start = index + len(needle)
    return snippets


def probe(url: str) -> dict:
    """Что отвечает адрес: код, тип, начало тела."""
    status, body = fetch_bytes(url, limit=6000)
    head = body.decode("utf-8", errors="replace")
    return {"status": status, "head": head[:1500]}


def scan_source(name: str, base: str) -> dict:
    status, home = fetch_text(base)
    print(f"\n=== {name}: главная — код {status}, {len(home)} байт", flush=True)
    result: dict = {"source": name, "base": base, "home_status": status}
    if not home or home.startswith("__error__"):
        result["home_error"] = home[:300]
        return result

    # JS-бандлы с того же сайта: у SPA список камер и адреса потоков внутри них.
    scripts = []
    for src in SCRIPT_SRC_RE.findall(home):
        full = urljoin(base, src)
        if base.split("//")[1].split("/")[0] not in full:
            continue
        js_status, js = fetch_text(full)
        print(f"    скрипт {full} — код {js_status}, {len(js)} байт")
        scripts.append({"url": full, "status": js_status, "text": js})
    result["scripts_meta"] = [{"url": s["url"], "status": s["status"], "bytes": len(s["text"])} for s in scripts]

    corpus = home + "\n".join(s["text"] for s in scripts)

    streams = sorted(set(STREAM_RE.findall(corpus)))
    result["streams"] = [
        {"url": s, "context": context_snippets(corpus, s)} for s in streams
    ]

    hosts = sorted({u.split("/")[2] for u in URL_RE.findall(corpus) if "/" in u[8:]})
    result["hosts"] = hosts

    # Полные адреса на служебных хостах (кроме счётчиков, шрифтов и соцсетей):
    # где-то среди них — список камер и потоки.
    noise = (
        "mc.yandex.ru", "yandex.ru", "yastatic.net", "fonts.g", "www.w3.org",
        "vk.com", "instagram.com", "facebook.com", "digitalcaramel.com",
        "googleapis.com", "gstatic.com",
    )
    urls = sorted({
        u.rstrip("\\',;)") for u in URL_RE.findall(corpus)
        if not any(n in u for n in noise)
    })
    result["urls"] = [{"url": u, "context": context_snippets(corpus, u, radius=160, limit=2)} for u in urls]

    api_paths = sorted(set(API_PATH_RE.findall(corpus)))
    result["api_paths"] = api_paths
    result["api_probes"] = {}
    for full in [urljoin(base, path) for path in api_paths[:15]] + [u for u in urls if "." in u.split("/")[-1] or u.rstrip("/").count("/") >= 3][:15]:
        result["api_probes"][full] = probe(full)
        print(f"    probe {full} → {result['api_probes'][full]['status']}")

    print(f"    потоков в коде: {len(streams)}, служебных адресов: {len(urls)}, хостов: {len(hosts)}")
    return result


def post_form(url: str, fields: dict[str, str] | None = None) -> tuple[int, str]:
    """POST формой, как это делает app.js APSNY (FormData)."""
    import uuid
    boundary = uuid.uuid4().hex
    parts = []
    for key, value in (fields or {}).items():
        parts.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{key}\"\r\n\r\n{value}\r\n"
        )
    parts.append(f"--{boundary}--\r\n")
    body = "".join(parts).encode()
    request = Request(
        url,
        data=body,
        headers={
            "User-Agent": UA,
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Origin": "https://apsny.camera",
            "Referer": "https://apsny.camera/",
        },
    )
    try:
        with urlopen(request, timeout=TIMEOUT) as response:
            return response.status, response.read(400_000).decode("utf-8", errors="replace")
    except HTTPError as error:
        return error.code, error.read(4000).decode("utf-8", errors="replace")
    except (URLError, OSError, ValueError) as error:
        return 0, f"__error__ {type(error).__name__}: {error}"


def apsny_api() -> dict:
    """Список локаций и камер APSNY: их фронт ходит в API POST-формой."""
    out: dict = {}
    for label, url, fields in (
        ("locations", "https://proxy-api.cyxym.net/bigbrother/v1?locations.get", {}),
        ("cams", "https://proxy-api.cyxym.net/bigbrother/v2?cams.get", {}),
        ("cams_loc1", "https://proxy-api.cyxym.net/bigbrother/v2?cams.get", {"location": "1"}),
        ("cams_id1", "https://proxy-api.cyxym.net/bigbrother/v2?cams.get", {"id": "1"}),
    ):
        status, body = post_form(url, fields)
        out[label] = {"status": status, "body": body[:120_000]}
        print(f"    POST {label} → {status}, {len(body)} байт, начало: {body[:120]!r}")
    return out


def amobile_cameras() -> list[dict]:
    """Полный список камер A-MOBILE прямо из их JS-бандла."""
    status, home = fetch_text("https://a-mobile.camera/")
    cams: list[dict] = []
    for src in SCRIPT_SRC_RE.findall(home):
        if "assets/" not in src:
            continue
        _, js = fetch_text(urljoin("https://a-mobile.camera/", src))
        for m in re.finditer(
            r'name:"([A-Za-z0-9_-]+)",title:"([^"]+)",comment:"([^"]*)",status:"(\w+)"(?:,clients_count:\d+)?(?:,preview:"([^"]*)")?',
            js,
        ):
            cams.append(
                {
                    "name": m.group(1),
                    "title": m.group(2),
                    "comment": m.group(3),
                    "status": m.group(4),
                    "preview": m.group(5) or f"https://a-mobile.camera/preview/{m.group(1)}.jpeg",
                }
            )
    unique = {c["name"]: c for c in cams}
    print(f"    камер a-mobile в бандле: {len(unique)}")
    return sorted(unique.values(), key=lambda c: c["name"])


def main() -> int:
    results = [
        {"apsny_api": apsny_api()},
        {"amobile_cameras": amobile_cameras()},
    ]
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nАртефакт: {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
