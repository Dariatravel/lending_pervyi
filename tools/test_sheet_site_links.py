#!/usr/bin/env python3
"""Столбец «Сайт» таблицы БАЗА: короткие ссылки abhazbereg.com, акции не объекты, чужие ссылки целы.

Запуск: python3 tools/test_sheet_site_links.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import update_sheet_site_links as u  # noqa: E402


def test_short_link_prefers_catalog_short_url() -> None:
    item = {"short_url": "https://abhazbereg.com/grass", "page_url": "https://абхазберег.рф/hotels/grass-2928/"}
    assert u.short_link_of(item, {"/hotels/grass-2928/": "staryy"}, "/hotels/grass-2928/") == "abhazbereg.com/grass"
    assert u.short_link_of({}, {"/hotels/x-1/": "x"}, "/hotels/x-1/") == "abhazbereg.com/x"
    assert u.short_link_of({}, {}, "/hotels/x-1/") == "abhazbereg.com/hotels/x-1/"


def test_shorten_existing_changes_only_domain_and_flags_promo() -> None:
    keys = {"/hotels/grass-2928/": "grass", "/hotels/novyy-god-5326/": "grass-novyy-god"}
    assert u.shorten_existing("abhazbereg.ru/grass", keys, set()) == "abhazbereg.com/grass"
    assert u.shorten_existing("https://абхазберег.рф/hotels/grass-2928/", keys, set()) == "abhazbereg.com/grass"
    # ключ акции в строке объекта — не «уже короткая», а в отчёт
    assert u.shorten_existing("abhazbereg.ru/grass-novyy-god", keys, {"grass-novyy-god"}) is None
    # чужие ссылки не наши
    assert u.shorten_existing("https://clck.ru/3TEmxy", keys, set()) is None
    assert u.shorten_existing("https://t.me/abhazbooking/5", keys, set()) is None
    assert u.is_our_link("https://clck.ru/x") is False
    assert u.is_our_link("abhazbereg.ru/grass") is True
    assert u.is_our_link("") is True


def test_promo_pages_are_not_objects() -> None:
    assert u.is_promo({"title": "НОВЫЙ ГОД В ГОРАХ В «ГРАСС» С ПОДОГРЕВАЕМЫМ БАССЕЙНОМ"})
    assert u.is_promo({"title": "СПЕЦПРЕДЛОЖЕНИЕ НА МЕЖСЕЗОНЬЕ «ОТПРАВЬ РОДИТЕЛЕЙ»"})
    assert not u.is_promo({"title": '"ГРАСС ОТЕЛЬ" коттеджи в горах'})
    assert u.quoted_name('"ГРАСС" коттеджи') == "грасс"


def main() -> int:
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"Все проверки пройдены: {len(tests)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
