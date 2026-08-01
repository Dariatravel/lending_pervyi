#!/usr/bin/env python3
"""Съём цен сразу со страниц-каталогов площадки (десятки объектов за один заход).

Проверять отели по одному долго: на каждый нужен поиск площадки и отдельный
заход браузера. Но площадки сами публикуют списки «Гостиницы Пицунды», где у
каждой карточки уже написано «от N руб. номер/сутки в августе». Один такой
список закрывает сразу два-три десятка объектов.

Скрипт открывает страницы-каталоги, собирает карточки (название, ссылка, цена)
и сопоставляет их с нашим каталогом по названию.

Запуск (в GitHub Actions):
    PROBE_URLS="<ссылки на каталоги, по одной в строке>" python3 tools/catalog_price_harvest.py
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "output" / "catalog-harvest"
SNAPSHOT = ROOT / "data" / "catalog-snapshot.json"

PRICE_RX = re.compile(r"(\d[\d\s ]{2,})\s*(?:₽|руб)", re.I)
MONTH_RX = re.compile(r"в\s+(январ|феврал|март|апрел|ма[ей]|июн|июл|август|сентябр|октябр|ноябр|декабр)\w*", re.I)
PER_PERSON_RX = re.compile(r"чел\.?/сут|за\s+человек|/\s*чел", re.I)


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").replace(" ", " ")).strip()


CITIES = ("гагра", "пицунда", "лдзаа", "лидзава", "алахадзы", "цандрипш", "гудаута",
          "новый афон", "сухум", "холодная речка", "мюссера", "бзыпь")


def our_titles() -> list[tuple[str, str, str]]:
    """(нормализованное имя, исходное название, город) по активным объектам."""
    if not SNAPSHOT.is_file():
        return []
    data = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    rows = data.get("listings") or data.get("rows") or []
    out = []
    for row in rows:
        if row.get("is_active") is False:
            continue
        title = str(row.get("title") or "")
        core = re.sub(r"[«»\"']", "", title)
        core = re.split(r"\s+(?:отель|гостев|гостиниц|домики|апартамент|мини-|глэмпинг|комплекс|апарт)", core, 1)[0]
        core = clean(core).lower()
        blob = json.dumps(row, ensure_ascii=False).lower()
        city = next((c for c in CITIES if c in blob), "")
        if len(core) >= 3:
            out.append((core, title, city))
    return out


def match_our(name: str, ours: list[tuple[str, str, str]], context: str = "") -> str:
    """Совпадение по названию + подтверждение городом.

    Названия у объектов повторяются («Ривьера» есть и в Лдзаа, и в Гудауте),
    поэтому если в тексте карточки или в адресе каталога назван другой город —
    совпадение не засчитываем.
    """
    low = clean(name).lower()
    ctx = (low + " " + context).lower()
    for core, title, city in ours:
        if not core:
            continue
        # Название объекта на площадке пишут в кавычках или ставят в начало
        # карточки. Просто «встречается в тексте» не годится: слово «Пицунда»
        # есть в адресе каждой второй карточки, а у нас есть отель «Пицунда».
        quoted = any(f"{q}{core}{q2}" in low for q, q2 in (("«", "»"), ('"', '"'), ("“", "”")))
        heads = low.startswith(core) or low.startswith(f"отель {core}") or low.startswith(f"гостевой дом {core}")
        if not quoted and not (heads and core not in CITIES):
            continue
        if city:
            other = [c for c in CITIES if c in ctx and c != city]
            if other and city not in ctx:
                continue
        return title
    return ""


def harvest(page, url: str, ours: list[tuple[str, str, str]]) -> list[dict]:
    print(f"\n{'=' * 80}\nКАТАЛОГ: {url}", flush=True)
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
    except Exception as error:  # noqa: BLE001
        print(f"ОШИБКА ОТКРЫТИЯ: {error}", flush=True)
        return []
    page.wait_for_timeout(2500)
    for _ in range(6):  # ленивая подгрузка списка
        try:
            page.mouse.wheel(0, 6000)
            page.wait_for_timeout(900)
        except Exception:  # noqa: BLE001
            break
    try:
        print(f"ЗАГОЛОВОК: {clean(page.title())[:90]}", flush=True)
    except Exception:  # noqa: BLE001
        pass

    # Цена почти никогда не лежит внутри самой ссылки — она рядом, в карточке.
    # Поэтому от каждой ссылки поднимаемся вверх по дереву, пока не найдём
    # блок, где есть и название, и сумма. Один вызов в браузер вместо сотен.
    try:
        cards = page.evaluate(
            """() => [...document.querySelectorAll('a[href]')].map(a => {
                let node = a, txt = a.innerText || '';
                for (let i = 0; i < 4 && node; i++) {
                    const t = node.innerText || '';
                    if (/\\d[\\d\\s\\u00a0]{2,}\\s*(₽|руб)/i.test(t)) { txt = t; break; }
                    node = node.parentElement;
                }
                return { href: a.href || '', text: (txt || '').slice(0, 400) };
            })"""
        )
    except Exception:  # noqa: BLE001
        return []

    seen: set[str] = set()
    found: list[dict] = []
    for card in cards[:1200]:
        href = card.get("href") or ""
        text = clean(card.get("text") or "")
        if not href or len(text) < 8 or len(text) > 400:
            continue
        price = PRICE_RX.search(text)
        if not price:
            continue
        value = int(re.sub(r"\D", "", price.group(1)))
        if not (300 <= value <= 200000):
            continue
        ours_title = match_our(text, ours, f"{url} {href}")
        if not ours_title:
            continue
        key = f"{ours_title}|{value}|{href}"
        if key in seen:
            continue
        seen.add(key)
        month = MONTH_RX.search(text)
        found.append({
            "our_title": ours_title,
            "price": value,
            "per_person": bool(PER_PERSON_RX.search(text)),
            "month": month.group(1) if month else "",
            "href": href if href.startswith("http") else url.rstrip("/") + "/" + href.lstrip("/"),
            "raw": text[:160],
        })

    for item in found:
        mark = " (за человека!)" if item["per_person"] else ""
        month = f" [{item['month']}]" if item["month"] else ""
        print(f"   {item['our_title'][:38]:40} {item['price']:>7} ₽{mark}{month} | {item['raw'][:70]}", flush=True)
    print(f"НАЙДЕНО СОВПАДЕНИЙ С НАШИМ КАТАЛОГОМ: {len(found)}", flush=True)
    return found


def main() -> int:
    urls = [u.strip() for u in os.environ.get("PROBE_URLS", "").splitlines() if u.strip()]
    if not urls:
        print("PROBE_URLS пуст.", file=sys.stderr)
        return 1
    ours = our_titles()
    print(f"Объектов в нашем каталоге для сопоставления: {len(ours)}", flush=True)

    from playwright.sync_api import sync_playwright

    results: list[dict] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
        context = browser.new_context(
            locale="ru-RU", timezone_id="Europe/Moscow",
            viewport={"width": 1440, "height": 1000},
            user_agent=("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
        )
        context.route(re.compile(r"travel\.yandex\.ru/(showcaptcha|\?affiliate)"), lambda route: route.abort())
        for url in urls[:30]:
            page = context.new_page()
            try:
                for item in harvest(page, url, ours):
                    item["catalog"] = url
                    results.append(item)
            finally:
                try:
                    page.close()
                except Exception:  # noqa: BLE001
                    pass
        browser.close()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    objects = {r["our_title"] for r in results}
    print(f"\nИТОГО: каталогов {len(urls)}, строк с ценами {len(results)}, наших объектов затронуто {len(objects)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
