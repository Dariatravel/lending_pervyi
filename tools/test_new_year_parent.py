#!/usr/bin/env python3
"""Новогоднее предложение находит свой отель (scripts/new_year_parent.py).

Примеры — настоящие заголовки и адреса каталога на 16.10.2026.
Запуск: python3 tools/test_new_year_parent.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from new_year_parent import find_parent_listing, is_new_year_offer, quoted_name  # noqa: E402


def row(slug: str, title: str, address: str = "") -> dict:
    return {"slug": slug, "title": title, "location_text": address, "is_active": True}


CATALOG = [
    row("plyazhnyy-kompleks-151-4620", "Пляжный комплекс 151 на берегу", "Лдзаа, ул. Приморская, 18А"),
    row("fazenda-otel-3190", "Фазенда отель с бассейном и питанием", "Пицунда, ул. Фабричная, 13/1"),
    row("fazenda-dvuhetazhnye-3200", "Фазенда двухэтажные коттеджи с бассейном и питанием", "Пицунда, ул. Фабричная, 13/2"),
    row("villa-leona-2755", "Вилла Леона отель с бассейном, питанием и собственным пляжем", "Гагра, ул. Гагрипшское ущелье, литер А"),
    row("grass-otel-2928", "\"ГРАСС ОТЕЛЬ\" коттеджи в горах Абхазии с бассейном", "Рицинское ущелье, 3-й км., дорога на озеро Рица"),
    row("grafit-haus-3707", "Графит Хаус гостевой дом с бассейном", "Гагра"),
    row("grant-otel-2820", '"ГРАНТ" отель номера', "Лдзаа, ул. Политрука Нозадзе, д.58"),
    row("two-a", "Отель Море", "Сухум, ул. Мира, 1"),
    row("two-b", "Апартаменты Море", "Сухум, ул. Мира, 1"),
    row("leto-kv-1587", "\"ЛЕТО\" квартира 2к", "Пицунда"),
]

NY = {
    "151": row("ny-151-5393", "НОВЫЙ ГОД НА БЕРЕГУ МОРЯ В «ПЛЯЖНОМ КОМПЛЕКСЕ 151»", "Лдзаа, ул. Приморская, 18А"),
    "fazenda": row("ny-fazenda-5281", "НОВЫЙ ГОД В ГОСТЕВОМ КОМПЛЕКСЕ «ФАЗЕНДА»", "Пицунда, ул. Фабричная, 13/1"),
    "leona": row("ny-leona-5316", "НОВЫЙ ГОД В «ВИЛЛЕ ЛЕОНА» с трехразовым питанием и бассейном", "Гагра, ул. Гагрипшское ущелье, литер А"),
    "grass": row("ny-grass-5326", "НОВЫЙ ГОД В ГОРАХ В «ГРАСС» С ПОДОГРЕВАЕМЫМ БАССЕЙНОМ", "Рицинское ущелье, 3-й км дороги на озеро Рица"),
    "unknown": row("ny-x", "НОВЫЙ ГОД В «НЕИЗВЕСТНОМ»", "Гудаута"),
    "two": row("ny-two", "НОВЫЙ ГОД У МОРЯ", "Сухум, ул. Мира, 1"),
    # Спецпредложение (17.10.2026): первая пара кавычек — название акции, вторая — отель.
    "special151": row(
        "spets-151-5403",
        "СПЕЦПРЕДЛОЖЕНИЕ НА МЕЖСЕЗОНЬЕ «ОТПРАВЬ РОДИТЕЛЕЙ В АБХАЗИЮ» ❤ «ПЛЯЖНЫЙ КОМПЛЕКС 151» на берегу моря",
        "Лдзаа, ул. Приморская, 18А",
    ),
    "allinc_grass": row("spets-grass", "СПЕЦПРЕДЛОЖЕНИЕ «ВСЁ ВКЛЮЧЕНО» ❤ «ГРАСС»", "Рицинское ущелье, где-то"),
    "leto_unknown": row("spets-leto", "СПЕЦПРЕДЛОЖЕНИЕ «ЛЕТО» в отеле Солнце", "Гудаута, ул. Новая, 1"),
}


def main() -> int:
    failures: list[str] = []
    listings = CATALOG + list(NY.values())

    def expect(key: str, slug: str | None) -> None:
        parent = find_parent_listing(NY[key], listings)
        got = parent["slug"] if parent else None
        if got != slug:
            failures.append(f"{key}: ожидали {slug}, получили {got}")

    expect("151", "plyazhnyy-kompleks-151-4620")  # по адресу
    expect("fazenda", "fazenda-otel-3190")  # по адресу, хотя «Фазенды» две
    expect("leona", "villa-leona-2755")  # по адресу; склонение «в ВИЛЛЕ»
    expect("grass", "grass-otel-2928")  # адрес другой → по названию, не «Графит»
    expect("unknown", None)  # нет такого отеля
    expect("two", None)  # по адресу двое, названия в кавычках нет — не гадаем
    expect("special151", "plyazhnyy-kompleks-151-4620")  # спецпредложение, отель — во второй паре кавычек
    expect("allinc_grass", "grass-otel-2928")  # акция + отель, адрес другой — по последнему названию
    expect("leto_unknown", None)  # «ЛЕТО» — название акции, отель не найден: не цепляться к квартире «Лето»
    if not is_new_year_offer(NY["special151"]):
        failures.append("спецпредложение не распознано")

    # Один адрес у разных отелей: название в кавычках не совпало — по адресу не берём.
    shared = [
        row("apra-4348", "Апра гостевой дом", "Пицунда, ул. Рыбзаводская, 81"),
        row("ny-abyrlash", "НОВЫЙ ГОД В «АБЫРЛАШ»", "Пицунда, ул. Рыбзаводская, 81"),
    ]
    if find_parent_listing(shared[1], shared) is not None:
        failures.append("взят отель с тем же адресом, но другим названием")

    # Новогоднее не может быть отелем для новогоднего.
    only_ny = [NY["151"], row("ny-151-old", "НОВЫЙ ГОД В «ПЛЯЖНОМ КОМПЛЕКСЕ 151» 2025", "Лдзаа, ул. Приморская, 18А")]
    if find_parent_listing(NY["151"], only_ny) is not None:
        failures.append("новогоднее предложение выбрано отелем для новогоднего")

    if not is_new_year_offer(NY["grass"]) or is_new_year_offer(CATALOG[0]):
        failures.append("is_new_year_offer")
    if quoted_name(NY["leona"]["title"]) != "ВИЛЛЕ ЛЕОНА":
        failures.append(f"quoted_name: {quoted_name(NY['leona']['title'])!r}")

    if failures:
        print("ОШИБКИ:")
        for failure in failures:
            print(" -", failure)
        return 1
    print("OK: новогодние предложения находят свой отель")
    return 0


if __name__ == "__main__":
    sys.exit(main())
