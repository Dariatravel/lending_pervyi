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


# Площадки, которым доверяем (крупные + профильные по Абхазии). Всё остальное
# помечается как «сайт вне списка» и в сверку не идёт: мелкие агрегаторы часто
# показывают устаревшие цены и путают объекты.
TRUSTED = (
    "ozon.travel", "travel.ozon.ru", "ostrovok.ru", "travel.yandex.ru", "yandex.ru",
    "hochu-na-yuga.ru", "kudanamore.ru", "sutochno.ru", "sutochno.com", "tvil.ru",
    "101hotels.com", "tutu.ru", "edem-v-gosti.ru", "travelandia.ru", "otdyh-abhazia.ru",
    "poehali-na-more.ru", "broni.travel", "bron.site", "alean.ru", "oyug.ru", "tropki.ru",
    # Крупные известные площадки и абхазский профильный портал.
    "otello.ru", "travel.ru", "hotels.ru", "myapsny.ru", "privettur.ru",
)
# Пакетные туры (перелёт+отель): цену за сутки из них брать нельзя.
PACKAGE = ("level.travel", "bgoperator.ru", "delfin-tour.ru", "intourist.ru", "tez-tour", "sunmar", "tavrica.com", "putevkaru.ru")
# Туроператоры, у которых бывает тариф «только проживание» — смотреть вручную.
OPERATOR_NO_FLIGHT = ("alean.ru",)

NIGHTS_RX = re.compile(r"за\s+(\d{1,2})\s*ноч|(\d{1,2})\s*ноч[еи]", re.I)


def site_kind(url: str, hotel_domain_ok: bool = True) -> str:
    """«доверенный» | «пакетный» | «оператор» | «вне списка»."""
    from urllib.parse import urlparse

    host = urlparse(url).netloc.lower().replace("www.", "")
    if any(p in host for p in PACKAGE):
        return "пакетный"
    if any(o in host for o in OPERATOR_NO_FLIGHT):
        return "оператор"
    if any(t in host for t in TRUSTED):
        return "доверенный"
    return "вне списка"


def per_night(price: int, text: str, nights: int) -> tuple[int, str]:
    """Привести цену к «за сутки»: итог за N ночей делим на N."""
    match = NIGHTS_RX.search(text or "")
    n = int(match.group(1) or match.group(2)) if match else 0
    if n > 1:
        return round(price / n), f"итог за {n} ноч. ({price:,} ₽)".replace(",", " ")
    # Крупная сумма при заданном сроке — почти наверняка итог за весь период.
    if nights > 1 and price > 25000:
        return round(price / nights), f"итог за {nights} ноч. ({price:,} ₽)".replace(",", " ")
    return price, ""


def with_dates(url: str, checkin: str, checkout: str, guests: int) -> str:
    """Добавить даты и число гостей в ссылку по правилам конкретной площадки.

    Суточно, Яндекс, Островок и другие показывают цену только для выбранных
    дат. Кликать по календарю ненадёжно (у всех своя вёрстка), зато все они
    принимают даты параметрами ссылки — этим и пользуемся.
    checkin/checkout: YYYY-MM-DD.
    """
    from urllib.parse import urlencode, urlparse

    host = urlparse(url).netloc.lower()
    dmy_in = "-".join(reversed(checkin.split("-")))   # 25-08-2026
    dmy_out = "-".join(reversed(checkout.split("-")))
    dot_in = dmy_in.replace("-", ".")                  # 25.08.2026
    dot_out = dmy_out.replace("-", ".")
    sep = "&" if "?" in url else "?"

    if "travel.yandex" in host:
        params = {"checkinDate": checkin, "checkoutDate": checkout, "adults": guests, "childrenAges": ""}
    elif "sutochno" in host:
        params = {"occupied": f"{dot_in};{dot_out}", "guests": guests, "guests_adults": guests}
    elif "ostrovok" in host:
        params = {"dates": f"{dot_in}-{dot_out}", "guests": f"{guests}"}
    elif "tvil.ru" in host:
        params = {"date_from": dot_in, "date_to": dot_out, "guests": guests}
    elif "101hotels" in host:
        params = {"checkIn": checkin, "checkOut": checkout, "adults": guests}
    elif "tutu.ru" in host:
        params = {"checkIn": checkin, "checkOut": checkout, "adults": guests}
    elif "broni.travel" in host or "bron.site" in host:
        params = {"arrival": checkin, "departure": checkout, "adults": guests}
    else:
        return url
    return url + sep + urlencode(params)


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").replace(" ", " ")).strip()


# Промо-условия («Скидка 2000 ₽», «На бронь от 40 000 ₽ по промокоду») —
# это не цена номера, а маркетинг площадки: в сверку такие суммы не идут.
PROMO_RX = re.compile(r"промокод|скидк|кэшб|кешб|бонус|сертификат|подар|акци", re.I)


def price_of(text: str) -> int | None:
    if PROMO_RX.search(text or ""):
        return None
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
    """Индекс начала блока «похожие объекты».

    Ищем только во второй половине страницы: вверху такие слова встречаются
    в меню и баннерах, и обрезка по ним съедала настоящий прайс.
    """
    start = len(lines) // 2
    for i in range(start, len(lines)):
        if len(lines[i]) < 80 and FOREIGN_RX.search(lines[i]):
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
        if DESTINATION_RX.search(line):  # подвал «Популярные направления»
            continue
        has_period = PERIOD_DATE_RX.search(line) or (PERIOD_WORD_RX.search(line) and len(line) < 60)
        if not has_period:
            continue
        value = price_of(line)
        window = ""
        if value is None:
            for j in (i + 1, i + 2, i - 1):
                # Длинная соседняя строка — это текст отзыва («Отдых был 10.07…
                # ужин 300 ₽»), а не прайс: такие цены в сверку не берём.
                if 0 <= j < len(lines) and len(lines[j]) <= 70:
                    value = price_of(lines[j])
                    if value:
                        window = lines[j]
                        break
        if value:
            rows.append({"source": "text", "period": line[:80], "price": value, "raw": (line + " | " + window)[:220]})

    # дедуп + отсев подвала «Популярные направления»
    seen: set[tuple] = set()
    unique: list[dict] = []
    for row in rows:
        if DESTINATION_RX.search(row["period"]) or FOOTER_PRICE_RX.search(row["raw"]):
            continue
        key = (row["period"][:40], row["price"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique


# Признаки карточки ЧУЖОГО объекта в подборке «похожие». Держим список узким:
# каждый лишний шаблон срезает и цены самого отеля (проверено на broni.travel,
# где широкое правило «Слово / Слово» обнулило весь прайс).
#   «Абхазия / Гудаута»          — строка-адрес карточки соседнего объекта
#   «7 ночей • от 5400 руб.»     — подпись карточки в подборке (маркер-буллет)
OTHER_CARD_RX = re.compile(r"^\s*Абхазия\s*/\s*\S|\d+\s*ноч\w*\s*[•·]", re.I)

# Блок «Популярные направления» в подвале площадок: «Санкт-Петербург — от 1 100 ₽
# / сутки». Это цены других городов и стран, к нашему отелю отношения не имеют.
DESTINATION_RX = re.compile(
    r"^\s*(?:Санкт-Петербург|Москва|Сочи|Геленджик|Анапа|Казань|Нижний\s+Новгород|Краснодар"
    r"|Екатеринбург|Калининград|Ростов-на-Дону|Владивосток|Кисловодск|Самара|Ярославль"
    r"|Новосибирск|Зеленоградск|Волгоград|Суздаль|Воронеж|Азербайджан|Турция|Испания"
    r"|Франция|Италия|Египет|ОАЭ|Грузия|Армения|Белоруссия|Беларусь|Крым|Абхазия"
    r"|Китай|Таиланд|Объединённые\s+Арабские\s+Эмираты|Минск|Барселона|Париж|Рим|Дубай"
    r"|Ереван|Кемер|Ницца|Тбилиси|Милан|Аланья|Мадрид|Шанхай|Батуми|Алматы|Паттайя|Пекин"
    r"|Ташкент|Гагра|Сухум|Пицунда|Новый\s+Афон|Гудаута|Цандрипш)\s*$",
    re.I,
)

# Тот же подвал, но со стороны цены: карусели «популярных направлений» и
# «популярных отелей» подписывают суммы строго как «от 1 474 ₽ / сутки».
# Прайсы самих объектов в этих же площадках пишутся иначе («6 000 ₽»,
# «от 6000 руб», «2 500 руб.»), поэтому шаблон отсеивает только подвал.
FOOTER_PRICE_RX = re.compile(r"от\s[\d\s  ]+₽\s*/\s*сутки", re.I)

# Строки самого объекта: если рядом с ценой стоит его собственная кнопка или
# подпись выбранных дат — это наш прайс, фильтр чужих карточек не применяем.
OWN_PRICE_RX = re.compile(
    r"забронировать|выбранн\w+\s+дат|по\s+вашим\s+датам|итого|за\s+весь\s+период|"
    r"стоимость\s+проживания",
    re.I,
)


def marker_distance(lines: list[str], index: int, pattern: re.Pattern, radius: int = 2) -> int:
    """На сколько строк от цены отстоит ближайший маркер (99 — маркера нет)."""
    for distance in range(radius + 1):
        for j in (index - distance, index + distance):
            if 0 <= j < len(lines) and pattern.search(lines[j]):
                return distance
    return 99


def harvest_dated(page, nights: int) -> list[dict]:
    """Сбор цен, когда даты уже выбраны.

    В этом режиме площадка пишет цену без месяца («12 500 ₽ за 5 ночей»,
    «2 500 ₽ за ночь»), поэтому берём все суммы с их подписями.
    """
    try:
        lines = [clean(l) for l in page.locator("body").inner_text().splitlines()]
        lines = [l for l in lines if l]
    except Exception:  # noqa: BLE001
        return []
    lines = lines[: foreign_cut(lines)]
    rows: list[dict] = []
    for i, line in enumerate(lines):
        if len(line) > 90:
            continue
        value = price_of(line)
        if not value:
            continue
        context = ""
        for j in (i - 1, i + 1):
            if 0 <= j < len(lines) and 2 < len(lines[j]) <= 60 and not price_of(lines[j]):
                context = lines[j]
                break
        if PROMO_RX.search(context):  # «по промокоду …» — условие акции, не цена
            continue
        if DESTINATION_RX.search(context):  # подвал «Популярные направления»
            continue
        # Блоки на странице идут вплотную: цена отеля, сразу под ней карточка
        # соседнего объекта. Поэтому решаем по самой строке и её подписи, а не
        # по окну соседей: «Забронировать»/«по выбранным датам» — цена отеля,
        # «Абхазия / город» и «N ночей •» — чужая карточка.
        own_at = marker_distance(lines, i, OWN_PRICE_RX)
        foreign_at = marker_distance(lines, i, OTHER_CARD_RX)
        # Ничья (маркеры одинаково близко) трактуется в пользу отсева: лучше
        # потерять цену, чем записать отелю чужой демпинг.
        if foreign_at <= own_at and foreign_at < 99:
            continue
        rows.append({"source": "dated", "period": context or "по выбранным датам", "price": value,
                     "raw": f"{context} | {line}"[:200]})
    seen: set[tuple] = set()
    unique: list[dict] = []
    for row in rows:
        key = (row["period"][:30], row["price"])
        if key not in seen:
            seen.add(key)
            unique.append(row)
    return unique[:25]


def probe(page, url: str, index: int, checkin: str = "", checkout: str = "", guests: int = 2) -> dict:
    kind = site_kind(url)
    nights = 0
    if checkin and checkout:
        from datetime import date

        y1, m1, d1 = (int(x) for x in checkin.split("-"))
        y2, m2, d2 = (int(x) for x in checkout.split("-"))
        nights = max((date(y2, m2, d2) - date(y1, m1, d1)).days, 0)
    target = with_dates(url, checkin, checkout, guests) if checkin and checkout else url
    print(f"\n{'=' * 80}\nURL: {url}\nПЛОЩАДКА: {kind}", flush=True)
    if kind == "вне списка":
        print("ПРОПУСК: сайт не в списке доверенных площадок.", flush=True)
        return {"url": url, "kind": kind, "status": "skipped", "clicks": 0, "rows": []}
    if kind == "пакетный":
        print("ПРОПУСК: пакетные туры (перелёт+отель) — цена за сутки несопоставима.", flush=True)
        return {"url": url, "kind": kind, "status": "skipped-package", "clicks": 0, "rows": []}
    if kind == "оператор":
        print("ВНИМАНИЕ: туроператор — проверить наличие тарифа «только проживание» (без перелёта).", flush=True)
    if target != url:
        print(f"     (с датами {checkin} → {checkout}, ночей {nights}, гостей {guests})", flush=True)
    result = {"url": url, "kind": kind, "requested": target, "nights": nights, "status": "", "clicks": 0, "rows": []}
    try:
        response = page.goto(target, wait_until="domcontentloaded", timeout=45000)
        result["status"] = str(response.status if response else "нет ответа")
    except Exception as error:  # noqa: BLE001
        print(f"STATUS: ОШИБКА ОТКРЫТИЯ — {error}", flush=True)
        result["status"] = f"error: {error}"
        return result
    page.wait_for_timeout(2500)
    # Цены на площадках с календарём подгружаются после ответа сервера —
    # ждём появления любой суммы в рублях (до 15 секунд).
    try:
        page.wait_for_function(
            "() => /\\d[\\d\\s\\u00a0]{2,}\\s*(₽|руб)/.test(document.body.innerText)",
            timeout=15000,
        )
    except Exception:  # noqa: BLE001 — цен может не быть вовсе
        pass
    try:
        page.mouse.wheel(0, 4000)
        page.wait_for_timeout(1500)
    except Exception:  # noqa: BLE001
        pass
    try:
        result["title"] = clean(page.title())[:90]
        print(f"ЗАГОЛОВОК: {result['title']}", flush=True)
    except Exception:  # noqa: BLE001
        pass
    result["clicks"] = expand_everything(page)
    rows = harvest_rows(page)
    if not rows and nights:
        rows = harvest_dated(page, nights)
    for row in rows:
        row["price_night"], row["note"] = per_night(row["price"], row["raw"], nights)
    result["rows"] = rows
    print(f"STATUS: {result['status']} | кликов по «показать»: {result['clicks']} | строк прайса: {len(rows)}", flush=True)
    for row in rows[:60]:
        tail = f" [{row['note']}]" if row.get("note") else ""
        line = f"   | {row['period'][:40]:40} | {row['price_night']:>8,} ₽/сутки{tail} | {row['raw'][:70]}"
        print(line.replace(",", " "), flush=True)
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
    checkin = os.environ.get("PROBE_CHECKIN", "").strip()
    checkout = os.environ.get("PROBE_CHECKOUT", "").strip()
    guests = int(os.environ.get("PROBE_GUESTS", "2") or 2)

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
        # Некоторые площадки уводят браузер на партнёрскую ссылку Яндекс.Путешествий,
        # там встречает капча, и следующая страница падает с «навигация прервана».
        # Блокируем такие переходы — они всё равно бесполезны для сверки.
        context.route(
            re.compile(r"travel\.yandex\.ru/(showcaptcha|\?affiliate)"),
            lambda route: route.abort(),
        )
        for i, url in enumerate(urls[:40], 1):
            # Каждую страницу открываем в своей вкладке: иначе редирект одной
            # площадки обрывает загрузку следующей и ломает всю пачку.
            page = context.new_page()
            try:
                results.append(probe(page, url, i, checkin, checkout, guests))
            finally:
                try:
                    page.close()
                except Exception:  # noqa: BLE001
                    pass
        browser.close()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    ok = sum(1 for r in results if r["rows"])
    print(f"\nИТОГО: страниц {len(results)}, с найденным прайсом — {ok}", flush=True)

    # Короткая сводка: заголовок страницы и снятые суммы одной строкой на объект.
    # Полный лог прогона длинный, а для сверки нужны ровно эти цифры.
    summary = []
    for item in results:
        prices = ", ".join(
            f"{row['price']}₽ ({row['period'][:40]})" for row in item["rows"][:12]
        ) or "прайса нет"
        summary.append(f"{item.get('title', '')[:70]} :: {prices}\n    {item['url']}")
    (OUT_DIR / "summary.txt").write_text("\n".join(summary), encoding="utf-8")
    print("\n=== СВОДКА ===\n" + "\n".join(summary), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
