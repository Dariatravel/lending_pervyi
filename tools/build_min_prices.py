#!/usr/bin/env python3
"""Минимальная цена каждого объекта на текущий месяц → data/min-prices-today.json.

Источник — блок «Цены» (details.prices) в data/catalog-snapshot.json.
Файл фиксируется ежедневным workflow price-refresh (03:00 МСК): все
пересборки карточек в течение дня используют зафиксированные значения.

Отчёт (покрытие, непокрытые объекты, подозрительные значения):
output/min-prices-report.txt
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_PATH = ROOT / "data" / "catalog-snapshot.json"
OUT_PATH = ROOT / "data" / "min-prices-today.json"
REPORT_PATH = ROOT / "output" / "min-prices-report.txt"

MSK = timezone(timedelta(hours=3))

MONTH_PATTERNS = {
    1: r"январ", 2: r"феврал", 3: r"март", 4: r"апрел", 5: r"ма[йяе]\b|\bмая\b",
    6: r"июн", 7: r"июл", 8: r"август", 9: r"сентябр", 10: r"октябр",
    11: r"ноябр", 12: r"декабр",
}
MONTH_LABEL = {
    1: "в январе", 2: "в феврале", 3: "в марте", 4: "в апреле", 5: "в мае",
    6: "в июне", 7: "в июле", 8: "в августе", 9: "в сентябре", 10: "в октябре",
    11: "в ноябре", 12: "в декабре",
}

# Цена: число с валютой/суткой, либо число в начале строки перед « - месяц».
PRICE_WITH_CURRENCY = re.compile(r"(\d[\d\s ]{2,6})\s*(?:₽|руб|р\.|/\s*сутки)", re.I)
PRICE_LEADING = re.compile(r"^\s*(\d{3,6})\s*[-—–]")

# Строки, которые не являются ценой размещения за ночь.
STOP_WORDS = re.compile(
    r"доп\.?\s*место|доп\.?\s*чел|дополнительн|трансфер|депозит|залог|скидк|"
    r"кэшбек|кешбэк|экскурс|за\s+весь|за\s+месяц|предоплат",
    re.I,
)
YEARS = {2024, 2025, 2026, 2027}
MIN_PRICE, MAX_PRICE = 800, 150000


ALL_YEAR = re.compile(r"круглый\s+год|любой\s+месяц|весь\s+год|всесезонн|в\s+любое\s+время", re.I)


def month_at(text: str, pos_map: list[tuple[int, int]], index: int) -> int:
    return pos_map[index][1]


def months_in(text: str) -> set[int]:
    low = text.lower()
    if ALL_YEAR.search(low):
        return set(range(1, 13))

    hits: list[tuple[int, int]] = []  # (позиция в строке, месяц)
    for num, pat in MONTH_PATTERNS.items():
        for m in re.finditer(pat, low):
            hits.append((m.start(), num))
    hits.sort()
    if not hits:
        return set()

    months = {num for _, num in hits}

    # «с <м1> по <м2>» — заполняем диапазон (в т.ч. через новый год)
    for m in re.finditer(r"\bс\b[^,;]*?\bпо\b", low):
        inside = [num for pos, num in hits if m.start() <= pos <= m.end() + 12]
        if len(inside) >= 2:
            start, end = inside[0], inside[-1]
            cur = start
            while cur != end:
                months.add(cur)
                cur = cur % 12 + 1
            months.add(end)
    # открытый «с <месяц>» без «по» (заголовок сезона) — до конца года.
    # Продлеваем ТОЛЬКО когда после «с» идёт НАЗВАНИЕ месяца («с июня», «с 15 июня»,
    # либо строка целиком заканчивается «… с <месяцем>»). НЕ трогаем:
    #   • «июнь с 15го» — «15го» это день месяца, а не открытый сезон;
    #   • «декабрь с 30.12 - май», «с 25 мая, июнь» — это диапазоны, не сезон «до конца года».
    # Иначе низкая цена «затекает» в июль/август и занижает «Цену от …».
    starts_with_s = bool(re.match(r"^\s*с\s", low)) and " по " not in low and len(hits) == 1
    tail_open = re.search(r"\bс\s+(?:\d{1,2}\s+)?([а-яё]+)\s*$", low.strip())
    tail_is_month = bool(tail_open) and any(re.search(pat, tail_open.group(1)) for pat in MONTH_PATTERNS.values())
    if starts_with_s or tail_is_month:
        months.update(range(hits[0][1], 13))
    return months


def extract_price(text: str) -> int | None:
    if STOP_WORDS.search(text):
        return None
    cleaned = text.replace(" ", " ")
    m = PRICE_WITH_CURRENCY.search(cleaned)
    if not m:
        m = PRICE_LEADING.search(cleaned)
    if not m:
        return None
    try:
        value = int(re.sub(r"\D", "", m.group(1)))
    except ValueError:
        return None
    if value in YEARS or not (MIN_PRICE <= value <= MAX_PRICE):
        return None
    return value


def promo_deadline(text: str) -> date | None:
    """Крайний срок ограниченной цены: «до 4 июля», «до 15.09», «Акция до 15 июля».

    Возвращает дату (текущий год) или None, если строка не ограничена сроком.
    Строки вида «июль, август, сентябрь до 15.09» тоже дают дату — но она в
    БУДУЩЕМ, поэтому в main() такие цены остаются (истекают только прошедшие).
    """
    low = text.lower()
    m = re.search(r"\bдо\s+(\d{1,2})\s*[.\-/]\s*(\d{1,2})", low)  # до 15.09
    if m:
        day, mon = int(m.group(1)), int(m.group(2))
    else:
        m = re.search(r"\bдо\s+(\d{1,2})\s+([а-яё]+)", low)  # до 4 июля
        if not m:
            return None
        day, name, mon = int(m.group(1)), m.group(2), None
        for num, pat in MONTH_PATTERNS.items():
            if re.search(pat, name):
                mon = num
                break
        if mon is None:
            return None
    if not (1 <= mon <= 12 and 1 <= day <= 31):
        return None
    try:
        return date(datetime.now(MSK).year, mon, day)
    except ValueError:
        return None


def monthly_min_prices(price_rows: list, today: date | None = None) -> dict[int, int]:
    """Stateful-проход: строка-заголовок с месяцами задаёт контекст для цен ниже.

    Заголовок со стоп-словами («Дополнительное место:», «За ребёнка:»…)
    блокирует все цены под ним до следующего заголовка — иначе доп.места
    попадают в «Цену от …» (кейс «Манон»: 1500 ₽ за доп.место).
    """
    result: dict[int, int] = {}
    context_months: set[int] = set()
    blocked_context = False
    for item in price_rows:
        text = str(item.get("text") if isinstance(item, dict) else item or "").strip()
        if not text:
            continue
        line_months = months_in(text)
        price = extract_price(text)
        if price is None:
            # Любая строка-заголовок устанавливает или сбрасывает блокировку.
            blocked_context = bool(STOP_WORDS.search(text))
            if line_months and not blocked_context:
                context_months = line_months  # «Июнь до 15 числа», «Апрель (без питания)»
            continue
        if blocked_context:
            continue
        # Ограниченная сроком цена («2000₽ до 4 июля», «Акция до 15 июля»),
        # срок которой уже прошёл — не действует, в «Цену от …» не берём.
        if today is not None:
            deadline = promo_deadline(text)
            if deadline is not None and deadline < today:
                continue
        target = line_months or context_months
        for month in target:
            if month not in result or price < result[month]:
                result[month] = price

    if not result:
        # Во всём блоке нет ни одного месяца — прайс постоянный, действует всегда.
        year_round: int | None = None
        for item in price_rows:
            text = str(item.get("text") if isinstance(item, dict) else item or "").strip()
            price = extract_price(text) if text else None
            if price is not None and (year_round is None or price < year_round):
                year_round = price
        if year_round is not None:
            result = {month: year_round for month in range(1, 13)}
    return result


def main() -> int:
    now = datetime.now(MSK)
    month = now.month
    today = now.date()
    snap = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    rows = [r for r in snap.get("listings") or [] if r.get("slug") and r.get("is_active", True)]

    prices: dict[str, int] = {}
    uncovered: list[tuple[str, list[str]]] = []
    suspicious: list[str] = []
    for row in rows:
        raw = (row.get("details") or {}).get("prices") or []
        monthly = monthly_min_prices(raw, today)
        value = monthly.get(month)
        if value is None:
            texts = [str(p.get("text") if isinstance(p, dict) else p or "")[:70] for p in raw][:6]
            uncovered.append((row["slug"], texts))
            continue
        prices[row["slug"]] = value
        if value < 1500 or value > 60000:
            suspicious.append(f"{row['slug']}: {value} ₽")

    payload = {
        "generated_at": now.isoformat(),
        "month": month,
        "month_label": MONTH_LABEL[month],
        "prices": dict(sorted(prices.items())),
    }
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        f"Минимальные цены на {MONTH_LABEL[month].replace('в ', '')} — {now.strftime('%d.%m.%Y %H:%M МСК')}",
        f"Покрыто: {len(prices)} из {len(rows)} активных объектов",
        "",
        f"Без распознанной цены ({len(uncovered)}):",
    ]
    for slug, texts in uncovered:
        lines.append(f"- {slug}")
        for t in texts:
            lines.append(f"    | {t}")
    lines.append("")
    lines.append(f"Подозрительные значения ({len(suspicious)}):")
    lines.extend(f"- {s}" for s in suspicious or ["(нет)"])
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"месяц: {MONTH_LABEL[month]} | покрыто {len(prices)}/{len(rows)} | без цены: {len(uncovered)} | подозрительных: {len(suspicious)}")
    print(f"отчёт: {REPORT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
