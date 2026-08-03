#!/usr/bin/env python3
"""Съём условий бронирования и отмены со страниц объектов на площадках.

Тот же приём, что и в сверке цен (tools/browser_price_probe.py), только ищем
не суммы, а правила: предоплата, сроки отмены, штрафы, расчётный час, залог,
условия для детей и животных. Задача — увидеть, не обещает ли отель гостю
на стороне условия мягче или жёстче наших.

Запуск (в GitHub Actions):
    PROBE_URLS="<ссылки, по одной в строке>" python3 tools/booking_terms_probe.py
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "output" / "booking-terms"

# Правила бронирования площадки пишут прозой, поэтому ищем предложения с этими
# словами. Список узкий: «цена» и «стоимость» сюда не входят — иначе в выборку
# попадёт весь прайс, а он собирается отдельным скриптом.
TERMS_RX = re.compile(
    r"предоплат|аванс|задаток|залог|депозит|брониров|бронь|заявк\w+\s+на\s+брон"
    r"|отмен\w*\s+(?:брон|заезд|прожив)|аннул|возврат\w*\s+(?:сред|денег|предоплат|аванс)"
    r"|штраф|неустойк|расч[её]тный\s+час|заезд|выезд|заселени|выселени"
    r"|не\s+возвращается|удержива",
    re.I,
)
# Отдельно помечаем то, что относится именно к отмене: в таблице это главное.
CANCEL_RX = re.compile(r"отмен|аннул|возврат|штраф|неустойк|не\s+возвращается|удержива", re.I)
PREPAY_RX = re.compile(r"предоплат|аванс|задаток|залог|депозит", re.I)
CHECKIN_RX = re.compile(r"расч[её]тный\s+час|заезд|выезд|заселени|выселени", re.I)

# Строки-обёртки интерфейса: кнопки и меню, где эти слова тоже встречаются.
NOISE_RX = re.compile(
    r"^\s*(?:забронировать|бронировать|отменить|подробнее|показать|ещё|еще|далее|"
    r"условия\s+бронирования|правила)\s*$|^\s*\d+\s*$",
    re.I,
)


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").replace(" ", " ")).strip()


def expand(page) -> int:
    """Раскрыть аккордеоны «Условия бронирования», «Правила заселения»."""
    clicks = 0
    labels = ("Условия", "Правила", "Показать", "Подробнее", "Ещё", "Еще", "Развернуть")
    for label in labels:
        try:
            items = page.get_by_text(re.compile(label, re.I)).all()[:6]
        except Exception:  # noqa: BLE001
            continue
        for item in items:
            try:
                item.click(timeout=1200)
                clicks += 1
                page.wait_for_timeout(400)
            except Exception:  # noqa: BLE001
                continue
    return clicks


def harvest(page) -> list[dict]:
    """Предложения с правилами брони, разложенные по трём темам."""
    try:
        raw = page.locator("body").inner_text()
    except Exception:  # noqa: BLE001
        return []
    # Режем не по строкам, а по предложениям: правила часто идут сплошным
    # абзацем («Предоплата 30%. При отмене менее чем за 7 дней не возвращается»).
    chunks: list[str] = []
    for line in raw.splitlines():
        line = clean(line)
        if not line or NOISE_RX.search(line):
            continue
        chunks.extend(part.strip() for part in re.split(r"(?<=[.!?])\s+", line) if part.strip())

    seen: set[str] = set()
    found: list[dict] = []
    for chunk in chunks:
        if not (12 <= len(chunk) <= 320) or not TERMS_RX.search(chunk):
            continue
        key = chunk.lower()[:80]
        if key in seen:
            continue
        seen.add(key)
        found.append({
            "text": chunk,
            "topic": ("отмена" if CANCEL_RX.search(chunk) else
                      "предоплата" if PREPAY_RX.search(chunk) else
                      "заезд/выезд" if CHECKIN_RX.search(chunk) else "бронирование"),
        })
    return found[:20]


def probe(page, url: str) -> dict:
    print(f"\n{'=' * 80}\nURL: {url}", flush=True)
    result = {"url": url, "title": "", "status": "", "terms": []}
    try:
        response = page.goto(url, wait_until="domcontentloaded", timeout=45000)
        result["status"] = str(response.status if response else "нет ответа")
    except Exception as error:  # noqa: BLE001
        result["status"] = f"error: {error}"
        print(f"ОШИБКА ОТКРЫТИЯ: {error}", flush=True)
        return result
    page.wait_for_timeout(2000)
    try:
        result["title"] = clean(page.title())[:90]
    except Exception:  # noqa: BLE001
        pass
    expand(page)
    try:
        page.mouse.wheel(0, 6000)
        page.wait_for_timeout(1200)
    except Exception:  # noqa: BLE001
        pass
    result["terms"] = harvest(page)
    print(f"ЗАГОЛОВОК: {result['title']}", flush=True)
    print(f"STATUS: {result['status']} | найдено правил: {len(result['terms'])}", flush=True)
    for item in result["terms"]:
        print(f"   [{item['topic']:12}] {item['text'][:150]}", flush=True)
    return result


def main() -> int:
    urls = [u.strip() for u in os.environ.get("PROBE_URLS", "").splitlines() if u.strip()]
    if not urls:
        print("PROBE_URLS пуст.", file=sys.stderr)
        return 1

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
        for url in urls[:40]:
            page = context.new_page()
            try:
                results.append(probe(page, url))
            finally:
                try:
                    page.close()
                except Exception:  # noqa: BLE001
                    pass
        browser.close()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")

    summary = []
    for item in results:
        if item["terms"]:
            lines = "; ".join(f"[{t['topic']}] {t['text'][:110]}" for t in item["terms"][:6])
        else:
            lines = "правил не найдено"
        summary.append(f"{item['title'][:70]} :: {lines}\n    {item['url']}")
    (OUT_DIR / "summary.txt").write_text("\n".join(summary), encoding="utf-8")

    ok = sum(1 for r in results if r["terms"])
    print(f"\nИТОГО: страниц {len(results)}, с найденными правилами — {ok}", flush=True)
    print("\n=== СВОДКА ===\n" + "\n".join(summary), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
