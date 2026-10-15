"""Отметки фильтров, которые выводятся из других данных, а не из галочек «БАЗЫ».

Решение Дарьи 15.10.2026 (бот «Быстрый подбор по каталогу» в АБХАЗБИЗНЕС
должен понимать «тёплый бассейн» и «работает в межсезон»):

- ``room: heated-pool`` — бассейн с подогревом. Берётся из того, что уже
  известно: текст столбца AT «бассейн ВСЕ варианты» таблицы «БАЗА»
  (apply_all_filters_from_sheet.infer_room) и описание объекта на сайте
  (у «Грасса» в AT просто «Бассейн», а в описании — «с подогревом»).
  «Без подогрева» отметку не даёт.
- ``stay: offseason`` — объект из подборки «Межсезон» (пост
  t.me/abhazbooking/5348 → data/telegram-collections.json["mezhsezon"]).
  Подборка пополняется, поэтому отметка не хранится в снимке каталога, а
  ставится заново при каждой записи data/catalog-index.json: убрали объект
  из поста — при следующей сборке пропала и отметка.

Обе отметки попадают в catalog-index.json, оттуда часовой синк шахматки
(travel_time, scripts/hotel-filters-cron-sync.mjs) переносит их в
public.hotel_filters, а бот подбора читает уже оттуда.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
COLLECTIONS_PATH = ROOT / "data" / "telegram-collections.json"

HEATED_POOL = "heated-pool"
OFFSEASON = "offseason"

_POOL_RE = re.compile(r"бассейн|бессейн|басик", re.I)
# Слово про тепло рядом с бассейном. «Тёплый» — только вплотную к бассейну:
# «в тёплое время года бассейн открыт» про подогрев ничего не говорит.
_HEAT_RE = re.compile(
    r"подогр\w*|обогрев\w*|термальн\w*|т[её]пл\w*\s+(?:бассейн|басик)|(?:бассейн|басик)\w*\s+т[её]пл\w*",
    re.I,
)
# «без подогрева», «не подогревается», «(без подогрева)».
_NEGATION_RE = re.compile(r"(?:без|не)\s*\(?\s*$", re.I)
_SENTENCE_SPLIT_RE = re.compile(r"[.!?\n;]+")


def mentions_heated_pool(text: str) -> bool:
    """В тексте есть фраза про бассейн с подогревом (и это не «без подогрева»)."""
    for sentence in _SENTENCE_SPLIT_RE.split(str(text or "").replace("ё", "е").replace("Ё", "Е")):
        if not _POOL_RE.search(sentence):
            continue
        for match in _HEAT_RE.finditer(sentence):
            before = sentence[max(0, match.start() - 8):match.start()]
            if not _NEGATION_RE.search(before):
                return True
    return False


def listing_text(row: dict[str, Any]) -> str:
    """Все тексты карточки объекта из снимка каталога одной строкой."""
    details = row.get("details") if isinstance(row.get("details"), dict) else {}
    parts: list[str] = [str(row.get(key) or "") for key in ("title", "summary", "excerpt")]
    parts.append(str(details.get("lead") or ""))
    for section in details.get("sections") or []:
        if not isinstance(section, dict):
            continue
        parts.append(str(section.get("label") or ""))
        parts.extend(str(line or "") for line in section.get("lines") or [])
    return "\n".join(parts)


def _slug_of_href(href: Any) -> str:
    return str(href or "").strip().strip("/").split("/")[-1]


def collection_slugs(collection: Any) -> set[str]:
    if not isinstance(collection, dict):
        return set()
    return {
        _slug_of_href(href)
        for group in collection.get("groups") or []
        if isinstance(group, dict)
        for href in group.get("hrefs") or []
        if _slug_of_href(href)
    }


def load_offseason_slugs(path: Path = COLLECTIONS_PATH) -> set[str] | None:
    """Слаги подборки «Межсезон». None — файл не прочитался (не путать с пустой подборкой)."""
    try:
        collections = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(collections, dict):
        return None
    return collection_slugs(collections.get("mezhsezon"))


def _with(values: Iterable[Any], code: str, present: bool) -> list[str]:
    out = [str(v) for v in values or [] if str(v) != code]
    if present:
        out.append(code)
    return out


def apply_derived_filters(
    filters: dict[str, Any],
    row: dict[str, Any],
    offseason_slugs: set[str] | None,
) -> dict[str, Any]:
    """Копия фильтров объекта с отметками heated-pool и offseason.

    heated-pool уже мог прийти из таблицы (infer_room) — тогда остаётся; иначе
    ставится по описанию. Бассейн с подогревом — это бассейн, поэтому вместе
    с ним ставится и pool. offseason пересчитывается по подборке каждый раз;
    если подборку прочитать не удалось (None), отметку не трогаем.
    """
    result = dict(filters or {})
    room = [str(v) for v in result.get("room") or []]
    heated = HEATED_POOL in room or mentions_heated_pool(listing_text(row))
    if heated:
        room = _with(room, HEATED_POOL, True)
        if "pool" not in room:
            room.insert(0, "pool")
    if heated or "room" in result:
        result["room"] = room
    if offseason_slugs is not None:
        in_collection = str(row.get("slug") or "") in offseason_slugs
        if in_collection or "stay" in result:
            result["stay"] = _with(result.get("stay") or [], OFFSEASON, in_collection)
    return result
