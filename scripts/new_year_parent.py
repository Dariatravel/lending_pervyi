"""Новогоднее предложение получает фильтры своего отеля (решение Дарьи 16.10.2026).

Новогодние посты («НОВЫЙ ГОД НА БЕРЕГУ МОРЯ В «ПЛЯЖНОМ КОМПЛЕКСЕ 151»»)
выходят отдельными объектами, а строки в таблице «БАЗА» у них нет. Поэтому
фильтров у них не было — кроме города из адреса. Дарья: «с новогодними
предложениями фильтрация должна быть такая же, как у отеля, в котором это
предложение»; отдельная строка в «БАЗЕ» не нужна, если отель уже выложен.

Отель ищем так:
1. тот же адрес (location_text) — так нашлись «Фазенда», «Вилла Леона»,
   «Пляжный комплекс 151»;
2. иначе — название в кавычках из заголовка поста («ГРАСС» → «Грасс отель»),
   слова сравниваются по началу, чтобы склонение не мешало («в ВИЛЛЕ ЛЕОНА»
   = «Вилла Леона»).
Берём, только если подходит ровно один объект: ошибиться отелем хуже, чем
оставить новогоднее предложение без фильтров (оно попадёт в отчёт).
"""
from __future__ import annotations

import re
from typing import Any, Iterable

# Новогодние предложения и спецпредложения (17.10.2026: «СПЕЦПРЕДЛОЖЕНИЕ НА МЕЖСЕЗОНЬЕ
# «ОТПРАВЬ РОДИТЕЛЕЙ В АБХАЗИЮ» ❤ «ПЛЯЖНЫЙ КОМПЛЕКС 151»…») — фильтры своего отеля.
NEW_YEAR_RE = re.compile(r"НОВЫЙ\s+ГОД|НОВОГОДН|СПЕЦ\s*-?\s*ПРЕДЛОЖЕН", re.I)
_QUOTED_RE = re.compile(r"[«\"“]([^»\"”]{2,80})[»\"”]")
_WORD_RE = re.compile(r"[а-яa-z0-9]+")
# Слова, которые не отличают один объект от другого.
_STOPWORDS = {"в", "на", "и", "с", "у", "отель", "отеле", "мини", "гостевой", "гостевом", "дом", "доме"}


def _norm(text: Any) -> str:
    return str(text or "").lower().replace("ё", "е")


def is_new_year_offer(row: dict[str, Any]) -> bool:
    return bool(NEW_YEAR_RE.search(str(row.get("title") or "")))


def _address_key(text: Any) -> str:
    key = " ".join(_WORD_RE.findall(_norm(text)))
    return key if len(key) >= 6 else ""


def _stem(word: str) -> str:
    """Начало слова без окончания: «вилле»/«вилла» → «вилл», «комплексе»/«комплекс» → «компл».

    Не короче четырёх букв: «грасс» и «грант» по трём («гра») не различить.
    """
    if word.isdigit() or len(word) <= 4:
        return word
    return word[: max(4, min(5, len(word) - 2))]


def _stems(text: Any) -> set[str]:
    return {_stem(w) for w in _WORD_RE.findall(_norm(text)) if w not in _STOPWORDS}


def quoted_name(title: Any) -> str:
    match = _QUOTED_RE.search(str(title or ""))
    return match.group(1).strip() if match else ""


def quoted_names(title: Any) -> list[str]:
    """Все названия в кавычках: у спецпредложения первым бывает название акции, а не отеля."""
    return [m.strip() for m in _QUOTED_RE.findall(str(title or "")) if m.strip()]


def find_parent_listing(row: dict[str, Any], listings: Iterable[dict[str, Any]]) -> dict[str, Any] | None:
    """Летний объект того же отеля для новогоднего предложения; None — не нашли однозначно."""
    candidates = [
        other for other in listings
        if other is not row
        and other.get("slug") != row.get("slug")
        and other.get("is_active", True)
        and not is_new_year_offer(other)
    ]
    # Названия в кавычках — с последнего: у спецпредложения первым идёт название
    # акции («ОТПРАВЬ РОДИТЕЛЕЙ В АБХАЗИЮ», «ВСЁ ВКЛЮЧЕНО»), отель — в конце.
    names = [stems for stems in (_stems(n) for n in reversed(quoted_names(row.get("title")))) if stems]

    def matching(rows: list[dict[str, Any]], stems: set[str]) -> list[dict[str, Any]]:
        return [other for other in rows if stems <= _stems(other.get("title"))]

    # По одному адресу бывают разные отели («Аква» и «Аиша», «Апра» и «Абырлаш»),
    # поэтому название в кавычках, если оно есть, должно совпасть и здесь.
    address = _address_key(row.get("location_text"))
    same_address = (
        [other for other in candidates if _address_key(other.get("location_text")) == address] if address else []
    )
    if address and not names and len(same_address) == 1:
        return same_address[0]
    for stems in names:
        found = matching(same_address, stems)
        if len(found) == 1:
            return found[0]

    # Без совпадения адреса: по последнему названию — как есть; по остальным
    # (вероятно, название акции) не берём — «ЛЕТО» или «ВИД НА МОРЕ» найдут чужой отель.
    # И только в том же городе (первая часть адреса до запятой), если адрес есть.
    # Без адреса и при нескольких названиях не угадываем: непонятно, где акция, а где отель.
    if names and not (not address and len(names) > 1):
        found = matching(candidates, names[0])
        city = _city_key(row.get("location_text"))
        if city:
            found = [other for other in found if _city_key(other.get("location_text")) in ("", city)]
        if len(found) == 1:
            return found[0]
    return None


def _city_key(text: Any) -> str:
    """Город из адреса: первые слова до запятой («Лдзаа, ул. …» → «лдзаа», «Рицинское ущелье, …»)."""
    head = _norm(text).split(",", 1)[0]
    return " ".join(_WORD_RE.findall(head))
