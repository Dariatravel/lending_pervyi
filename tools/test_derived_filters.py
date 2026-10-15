#!/usr/bin/env python3
"""Проверка отметок «тёплый бассейн» и «межсезон» (scripts/derived_filters.py).

Фразы — настоящие, из таблицы «БАЗА» (столбец AT) и описаний объектов на 15.10.2026.
Запуск: python3 tools/test_derived_filters.py
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from derived_filters import (  # noqa: E402
    apply_derived_filters,
    collection_slugs,
    load_offseason_slugs,
    mentions_heated_pool,
)

HEATED = [
    "Бассейн с подогревом",
    "бассейн с подогревом пресной воды",
    "Три бассейна с подогревом",
    "Подогреваемый бассейн, с детской зоной",
    "Бассейн 6×4 м с морской водой, подогревом и детской зоной.",
    "Каркасный бассейн (размером 4,5 × 2,5 м, с подогревом)",
    "2 бассейна для возрослых и детей с подогревом",
    "Открытый круглогодичный бассейн с подогревом, работающий с 08:00 до 20:00",
    "НОВЫЙ ГОД В ГОРАХ В «ГРАСС» С ПОДОГРЕВАЕМЫМ БАССЕЙНОМ",
    "Тёплый бассейн и баня",
    "Бассейн с подогревом (работает с 1 мая), шезлонгами и зонтами",
]
NOT_HEATED = [
    "Бассейн без подогрева",
    "Бассейн (без подогрева), шезлонги, зонты",
    "бессейн без подогрева",
    "Каркасный бассейн размером 6 × 4,5 м, глубина 1,5 м, с красивой подсветкой (без подогрева)",
    "Два бассейна для взрослых и детей без подогрева под голубой крышей",
    "Каркасный бассейн",
    "Да",
    "Бассейн + источники",
    # подогрев не про бассейн
    "Оснащение: кондиционер, обогреватель, водонагреватель. Во дворе бассейн.",
    "В тёплое время года работает бассейн",
    "",
    # находки ревью 15.10: отрицание после слова, подогрев не бассейна
    "Бассейн (подогрев не предусмотрен)",
    "Подогрев бассейна отсутствует",
    "бассейн: подогрев — нет",
    "Бассейн с подогревом не работает",
    "Кондиционер, обогреватель, бассейн",
    "подогрев пола, во дворе бассейн",
    "термальные источники и бассейн",
    "Подогрев полов в номерах. На территории есть большой открытый бассейн с шезлонгами и зонтами",
    "Бассейн нет подогрева",
    "Обогрев номеров, бассейн",
]
HEATED += [
    "Бассейн с подогревом полностью крытый",
    "Термальный бассейн",
    "Бассейн с термальной водой",
    "Бассейн 10*5 м, шезлонги, зонтики, бар, подогрев",
]
# Столбец AT сам про бассейн: там бывает просто «С подогревом».
AT_HEATED = ["С подогревом", "Да, подогрев", "Да (с подогревом)", "Есть, подогреваемый", "бассейн; подогрев"]
AT_NOT_HEATED = ["Без подогрева", "Да", "Каркасный", "подогрев не предусмотрен", "Да, нет подогрева", "Есть, нет подогрева"]


def check(cond: bool, message: str, failures: list[str]) -> None:
    if not cond:
        failures.append(message)


def main() -> int:
    failures: list[str] = []

    for text in HEATED:
        check(mentions_heated_pool(text), f"должен быть тёплый: {text!r}", failures)
    for text in NOT_HEATED:
        check(not mentions_heated_pool(text), f"не должен быть тёплым: {text!r}", failures)
    for text in AT_HEATED:
        check(mentions_heated_pool(text, require_pool=False), f"AT должен быть тёплым: {text!r}", failures)
    for text in AT_NOT_HEATED:
        check(not mentions_heated_pool(text, require_pool=False), f"AT не должен быть тёплым: {text!r}", failures)

    # Строка через «|» не рассыпается на буквы.
    out = apply_derived_filters({"stay": "pets|cottages"}, {"slug": "a"}, {"a"})
    check(out["stay"] == ["pets", "cottages", "offseason"], f"строка через |: {out}", failures)

    # Отметка из таблицы сохраняется, даже если в описании подогрева нет.
    row = {"slug": "a", "title": "Отель", "details": {"lead": "Бассейн"}}
    out = apply_derived_filters({"room": ["pool", "heated-pool"], "stay": []}, row, set())
    check(out["room"] == ["pool", "heated-pool"], f"отметка из таблицы потерялась: {out}", failures)

    # Подогрев только в описании («Грасс»): ставится heated-pool, pool из таблицы не трогаем.
    row = {
        "slug": "grass",
        "title": "Грасс",
        "details": {"sections": [{"label": "ТЕРРИТОРИЯ", "lines": ["Бассейн с подогревом прямо рядом с домиками"]}]},
    }
    out = apply_derived_filters({"room": ["kitchen"], "stay": []}, row, {"grass"})
    check(out["room"] == ["kitchen", "heated-pool"], f"подогрев из описания: {out}", failures)
    check(out["stay"] == ["offseason"], f"межсезон по подборке: {out}", failures)

    # Убрали из подборки — отметка пропадает при следующей сборке.
    out = apply_derived_filters({"room": [], "stay": ["pets", "offseason"]}, {"slug": "old"}, {"grass"})
    check(out["stay"] == ["pets"], f"старая отметка межсезона не снялась: {out}", failures)

    # Подборка не прочиталась (None) — отметку не трогаем, а не снимаем у всех.
    out = apply_derived_filters({"stay": ["offseason"]}, {"slug": "x"}, None)
    check(out["stay"] == ["offseason"], f"при нечитаемой подборке отметка снята: {out}", failures)

    # Объект без фильтров и без отметок — лишних пустых групп не добавляем.
    out = apply_derived_filters({}, {"slug": "x", "title": "Дом"}, {"y"})
    check(out == {}, f"добавились пустые группы: {out}", failures)

    # Входной словарь не меняется.
    source = {"room": ["pool"], "stay": []}
    apply_derived_filters(source, {"slug": "grass", "title": "бассейн с подогревом"}, {"grass"})
    check(source == {"room": ["pool"], "stay": []}, f"исходные фильтры изменились: {source}", failures)

    # Подборка: hrefs вида /hotels/<slug>/ из всех групп поста.
    collection = {"groups": [{"hrefs": ["/hotels/a-1/", "/kvartira/b-2/"]}, {"hrefs": ["/hotels/c-3"]}, {}]}
    check(collection_slugs(collection) == {"a-1", "b-2", "c-3"}, "слаги подборки", failures)
    check(collection_slugs(None) == set(), "пустая подборка", failures)

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "c.json"
        path.write_text(json.dumps({"mezhsezon": collection}), encoding="utf-8")
        check(load_offseason_slugs(path) == {"a-1", "b-2", "c-3"}, "чтение подборки из файла", failures)
        path.write_text("{битый", encoding="utf-8")
        check(load_offseason_slugs(path) is None, "битый файл подборки → None", failures)
        check(load_offseason_slugs(Path(tmp) / "нет.json") is None, "нет файла → None", failures)
        path.write_text(json.dumps({"novyy-god-2027": collection}), encoding="utf-8")
        check(load_offseason_slugs(path) is None, "нет подборки в файле → None", failures)

    if failures:
        print("ОШИБКИ:")
        for failure in failures:
            print(" -", failure)
        return 1
    print(f"OK: {len(HEATED) + len(NOT_HEATED) + len(AT_HEATED) + len(AT_NOT_HEATED)} фраз и проверки отметок")
    return 0


if __name__ == "__main__":
    sys.exit(main())
