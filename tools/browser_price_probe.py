#!/usr/bin/env python3
"""Съём цен со страниц отелей настоящим браузером (Playwright).

Половина площадок (КудаНаМоре, Поехали-на-Море, Суточно, движки бронирования)
рисует прайс скриптом или прячет за кнопкой «Показать цены» — простой запрос
HTML их не видит. Здесь страница открывается Chromium'ом, раскрываются все
кнопки-разворачиватели, после чего собирается помесячный прайс.

Запуск (workflow browser-price-probe.yml):
    PROBE_URLS="<ссылки по одной в строке>" python tools/browser_price_probe.py

Результат: помесячные строки в лог + JSON и скриншоты в output/browser-probe/
(в workflow выгружаются артефактом).
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "output" / "browser-probe"

MONTHS = ("январ", "феврал", "март", "апрел", "мая", "май", "июн", "июл", "август", "сентябр", "октябр", "ноябр", "декабр")
PERIOD_DATE_RX = re.compile(r"\d{2}\.\d{2}\.?\s*[-–—]\s*\d{2}\.\d{2}\.?")
PERIOD_WORD_RX = re.compile(r"(?:^|\s)(?:с\s+)?\d{0,2}\s*(" + "|".join(MONTHS) + r")\w*", re.I)
PRICE_RX = re.compile(r"(\d[\d\s  ]{2,8})\s*(?:₽|руб)", re.I)

# Тексты кнопок, за которыми обычно прячут прайс.
EXPAND_TEXTS = (
    "Показать", "Показать цены", "Все цены", "Цены", "Ещё", "Еще",
    "Подробнее", "Развернуть", "Смотреть цены", "Показать все",
)


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").replace(" ", " ")).strip()


def price_of(text: str) -> int | None:
    m = PRICE_RX.search(text or "")
    if not m:
        return None
    value = int(re.sub(r"\D", "", m.group(1)))
    return value if 300 <= value <= 500000 else None


def expand_everything(page) -> int:
    """Прокликать кнопки-разворачиватели прайса. Возвращает число кликов."""
    clicks = 0
    for label in EXPAND_TEXTS:
        try:
            items = page.get_by_text(re.compile(rf"^\s*{re.escape(label)}\s*$", re.I))
            count = min(items.count(), 6)
        except Exception:  # noqa: BLE001
            continue
        for i in range(count):
            try:
                node = items.nth(i)
                if node.is_visible():
                    node.click(timeout=2500)
                    clicks += 1
                    page.wait_for_timeout(700)
            except Exception:  # noqa: BLE001 — кнопка могла исчезнуть/перекрыться
                continue
    return clicks


# Заголовки чужих блоков: их цены относятся к ДРУГИМ объектам и в сверку не идут.
FOREIGN_RX = re.compile(
    r"похож|рекомендуем|смотрите\s+так|также\s+смотрят|другие\s+(вариант|объект|отел|предложен)"
    r"|поблизости|рядом\s+с\s+этим|вам\s+может|популярн\w+\s+(отел|вариант)|ещё\s+вариант",
    re.I,
)


def foreign_cut(lines: list[str]) -> int:
    """Индекс, с которого начинается блок «похожие объекты» (или len(lines))."""
    for i, line in enumerate(lines):
        if len(line) < 80 and FOREIGN_RX.search(line):
            return i
    return len(lines)


def harvest_rows(page) -> list[dict]:
    """Строки прайса: из таблиц и из плоских блоков «период → цена».

    Всё, что ниже заголовка «Похожие объекты» и подобных, отбрасывается —
    иначе в сверку попадут цены соседних отелей.
    """
    rows: list[dict] = []

    # 1) настоящие таблицы
    try:
        for table in page.locator("table").all()[:12]:
            text = clean(table.inner_text())
            if not PRICE_RX.search(text):
                continue
            for tr in table.locator("tr").all()[:60]:
                cells = [clean(td.inner_text()) for td in tr.locator("td, th").all()]
                cells = [c for c in cells if c]
                if len(cells) < 2:
                    continue
                joined = " | ".join(cells)
                if not PRICE_RX.search(joined):
                    continue
                period = next((c for c in cells if PERIOD_DATE_RX.search(c) or PERIOD_WORD_RX.search(c)), "")
                value = next((price_of(c) for c in cells if price_of(c)), None)
                if value:
                    rows.append({"source": "table", "period": period, "price": value, "raw": joined[:220]})
    except Exception:  # noqa: BLE001
        pass

    # 2) плоский текст: период и цена рядом
    try:
        lines = [clean(l) for l in page.locator("body").inner_text().splitlines()]
        lines = [l for l in lines if l]
    except Exception:  # noqa: BLE001
        lines = []
    lines = lines[: foreign_cut(lines)]
    for i, line in enumerate(lines):
        has_period = PERIOD_DATE_RX.search(line) or (PERIOD_WORD_RX.search(line) and len(line) < 60)
        if not has_period:
            continue
        value = price_of(line)
        window = ""
        if value is None:
            for j in (i + 1, i + 2, i - 1):
                if 0 <= j < len(lines):
                    value = price_of(lines[j])
                    if value:
                        window = lines[j]
                        break
        if value:
            rows.append({"source": "text", "period": line[:80], "price": value, "raw": (line + " | " + window)[:220]})

    # дедуп
    seen: set[tuple] = set()
    unique: list[dict] = []
    for row in rows:
        key = (row["period"][:40], row["price"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique


def probe(page, url: str, index: int) -> dict:
    print(f"\n{'=' * 80}\nURL: {url}", flush=True)
    result = {"url": url, "status": "", "clicks": 0, "rows": []}
    try:
        response = page.goto(url, wait_until="domcontentloaded", timeout=45000)
        result["status"] = str(response.status if response else "нет ответа")
    except Exception as error:  # noqa: BLE001
        print(f"STATUS: ОШИБКА ОТКРЫТИЯ — {error}", flush=True)
        result["status"] = f"error: {error}"
        return result
    page.wait_for_timeout(2500)
    try:
        page.mouse.wheel(0, 4000)
        page.wait_for_timeout(1200)
    except Exception:  # noqa: BLE001
        pass
    result["clicks"] = expand_everything(page)
    rows = harvest_rows(page)
    result["rows"] = rows
    print(f"STATUS: {result['status']} | кликов по «показать»: {result['clicks']} | строк прайса: {len(rows)}", flush=True)
    for row in rows[:60]:
        print(f"   | {row['period'][:44]:44} | {row['price']:>8,} ₽ | {row['raw'][:90]}".replace(",", " "), flush=True)
    try:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(OUT_DIR / f"{index:02d}.png"), full_page=False)
    except Exception:  # noqa: BLE001
        pass
    return result


def main() -> int:
    urls = [u.strip() for u in os.environ.get("PROBE_URLS", "").splitlines() if u.strip()]
    if not urls:
        print("PROBE_URLS пуст — нечего проверять.", file=sys.stderr)
        return 1

    from playwright.sync_api import sync_playwright

    results = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
        context = browser.new_context(
            locale="ru-RU",
            timezone_id="Europe/Moscow",
            viewport={"width": 1440, "height": 1000},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()
        for i, url in enumerate(urls[:40], 1):
            results.append(probe(page, url, i))
        browser.close()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    ok = sum(1 for r in results if r["rows"])
    print(f"\nИТОГО: страниц {len(results)}, с найденным прайсом — {ok}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
