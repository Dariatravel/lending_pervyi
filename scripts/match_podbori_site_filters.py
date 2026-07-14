#!/usr/bin/env python3
"""
Сопоставление подборок из ~/Documents/ПОДБОРКИ (*_сайт.txt) с карточками каталога в index.html
и проверкой ожидаемых токенов фильтров (логика как в scripts.js).

Запуск из корня репозитория:
  python3 scripts/match_podbori_site_filters.py

Отчёт по умолчанию:
  <ПОДБОРКИ>/соответствие_фильтрам_сайта.md
"""
from __future__ import annotations

import argparse
import html as html_lib
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = REPO_ROOT / "index.html"

BEACH_FILTERS = {
    "SAND_LDZAA": "sand-ldzaa",
    "SAND_SUKHUM": "sand-sukhum",
    "PINE_PEBBLE_LDZAA_PITSUNDA": "pine-pebble-ldzaa-pitsunda",
    "PITSUNDA_BAY_MIXED": "pitsunda-bay-mixed",
    "PEBBLE": "pebble",
}
CANONICAL_FILTER_VALUES = {
    "distance": {"beachfront", "up-to-5", "up-to-10", "over-10"},
    "food": {"no-food", "half-board", "full-board", "breakfast", "cafe"},
    "price": {"economy", "midrange", "premium"},
    "city": {"ldzaa", "pitsunda", "gagra", "alakhadzy", "gudauta", "new-afon", "sukhum", "tsandripsh"},
    "beach": set(BEACH_FILTERS.values()),
    "room": {"sea-view", "pool", "balcony", "terrace", "tv", "kitchen", "five-plus", "two-room-plus", "beachfront-room"},
    "stay": {"cottages", "apartments", "turnkey-house", "pets", "no-small-kids"},
}
LEGACY_FILTER_VALUE_MAP = {
    "price": {
        "up-to-3000": "economy",
        "up-to-4000": "economy",
        "up-to-5000": "economy",
        "up-to-6000": "midrange",
        "up-to-7000": "midrange",
        "up-to-8000": "midrange",
        "up-to-9000": "midrange",
        "up-to-10000": "midrange",
    },
    "beach": {
        "sand": "sand-ldzaa",
        "pine-pebble": "pine-pebble-ldzaa-pitsunda",
        "mixed": "pitsunda-bay-mixed",
    },
    "room": {
        "two-room": "two-room-plus",
    },
}

DEFAULT_PODBORKI = Path.home() / "Documents" / "ПОДБОРКИ"


def dedupe(seq: list[str]) -> list[str]:
    seen: set[str] = set()
    out = []
    for x in seq:
        if not x or x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out


def to_filter_array(raw: str) -> list[str]:
    if not raw:
        return []
    return [p.strip() for p in str(raw).split("|") if p.strip()]


def normalize_price(raw: str) -> str:
    if raw in LEGACY_FILTER_VALUE_MAP["price"]:
        return LEGACY_FILTER_VALUE_MAP["price"][raw]
    lower = raw.lower()
    if "12000" in lower or "12 000" in lower or "дороже" in lower:
        return "premium"
    if "5000" in lower or "5 000" in lower:
        return "economy"
    if "10000" in lower or "10 000" in lower:
        return "midrange"
    if raw in ("economy", "midrange", "premium"):
        return raw
    return raw


def normalize_beach_value(raw: str, city_values: list[str]) -> str:
    if not raw:
        return ""
    lower = raw.lower()
    cities = set(city_values)
    is_sukhum = "sukhum" in cities
    is_ldzaa_or_pitsunda = "ldzaa" in cities or "pitsunda" in cities
    special = {
        BEACH_FILTERS["SAND_LDZAA"],
        BEACH_FILTERS["SAND_SUKHUM"],
        BEACH_FILTERS["PINE_PEBBLE_LDZAA_PITSUNDA"],
        BEACH_FILTERS["PITSUNDA_BAY_MIXED"],
        BEACH_FILTERS["PEBBLE"],
    }
    if raw in special:
        return raw
    if raw in LEGACY_FILTER_VALUE_MAP["beach"]:
        if raw == "sand":
            return BEACH_FILTERS["SAND_SUKHUM"] if is_sukhum else BEACH_FILTERS["SAND_LDZAA"]
        if raw == "mixed":
            return BEACH_FILTERS["PITSUNDA_BAY_MIXED"] if is_ldzaa_or_pitsunda else BEACH_FILTERS["PEBBLE"]
        return LEGACY_FILTER_VALUE_MAP["beach"][raw]
    if raw == "mixed":
        return BEACH_FILTERS["PITSUNDA_BAY_MIXED"] if is_ldzaa_or_pitsunda else BEACH_FILTERS["PEBBLE"]
    if "песчан" in lower and "сухум" in lower:
        return BEACH_FILTERS["SAND_SUKHUM"]
    if "песчан" in lower and "лдзаа" in lower:
        return BEACH_FILTERS["SAND_LDZAA"]
    if "соснов" in lower and "лдзаа" in lower:
        return BEACH_FILTERS["PINE_PEBBLE_LDZAA_PITSUNDA"]
    if "соснов" in lower and "пицунд" in lower:
        return BEACH_FILTERS["PINE_PEBBLE_LDZAA_PITSUNDA"]
    if "пицундск" in lower and "бухт" in lower:
        return BEACH_FILTERS["PITSUNDA_BAY_MIXED"]
    if "галеч" in lower:
        return BEACH_FILTERS["PEBBLE"]
    if "песчан" in lower:
        return BEACH_FILTERS["SAND_SUKHUM"] if is_sukhum else BEACH_FILTERS["SAND_LDZAA"]
    return raw


def normalize_room_value(value: str) -> str:
    raw = str(value or "").strip()
    lower = raw.lower()
    if not raw or raw in ("ac", "one-room"):
        return ""
    if raw in LEGACY_FILTER_VALUE_MAP["room"]:
        return LEGACY_FILTER_VALUE_MAP["room"][raw]
    if raw == "beachfront-room":
        return "beachfront-room"
    if "вид на море" in lower:
        return "sea-view"
    if (
        "прямо на берегу" in lower
        or "на первой линии" in lower
        or "отели на берегу" in lower
        or "на берегу моря" in lower
    ):
        return "beachfront-room"
    if "бассейн" in lower:
        return "pool"
    if "балкон" in lower:
        return "balcony"
    if "террас" in lower:
        return "terrace"
    if "кухн" in lower:
        return "kitchen"
    if "пять" in lower and "гостей" in lower:
        return "five-plus"
    if "две комнат" in lower:
        return "two-room-plus"
    return raw


def normalize_stay_value(value: str) -> str:
    raw = str(value or "").strip()
    lower = raw.lower()
    if not raw or raw == "kids":
        return ""
    if "домики" in lower or "коттедж" in lower:
        return "cottages"
    if "квартир" in lower:
        return "apartments"
    if "дом под ключ" in lower:
        return "turnkey-house"
    if "животн" in lower:
        return "pets"
    if "без маленьких детей" in lower:
        return "no-small-kids"
    return raw


def infer_stay_by_card(title: str, summary: str, href: str) -> list[str]:
    blob = f"{title} {summary} {href}".lower()
    values = []
    if re.search(r"(домик|коттедж|шале|бунгало|глэмпинг|glamping)", blob):
        values.append("cottages")
    if re.search(r"(квартир|апартамент|студи)", blob):
        values.append("apartments")
    if re.search(r"дом под ключ", blob):
        values.append("turnkey-house")
    if re.search(r"(с животн|питомц|pet friendly|с собачк)", blob):
        values.append("pets")
    return dedupe(values)


def infer_city(title: str, summary: str, href: str) -> list[str]:
    blob = f"{title} {summary} {href}".lower()
    values = []
    if "сухум" in blob:
        values.append("sukhum")
    if "новый афон" in blob:
        values.append("new-afon")
    if "гудаута" in blob:
        values.append("gudauta")
    if "лдзаа" in blob:
        values.append("ldzaa")
    if "пицунда" in blob:
        values.append("pitsunda")
    if "алахадз" in blob:
        values.append("alakhadzy")
    if "гагра" in blob:
        values.append("gagra")
    if "цандрипш" in blob:
        values.append("tsandripsh")
    return dedupe(values)


def infer_distance(title: str, summary: str, href: str) -> list[str]:
    blob = f"{title} {summary} {href}".lower()
    if re.search(r"0\s*(мин|минут)", blob) or re.search(r"на первой линии|прямо на пляже|на берегу", blob):
        return ["beachfront"]
    m = re.search(r"(\d{1,2})\s*(мин|минут)", blob)
    if not m:
        return []
    value = int(m.group(1))
    if value <= 5:
        return ["up-to-5"]
    if value <= 10:
        return ["up-to-10"]
    return ["over-10"]


def infer_beach(title: str, summary: str, href: str, cities: list[str]) -> list[str]:
    blob = f"{title} {summary} {href}".lower()
    if "соснов" in blob:
        return [BEACH_FILTERS["PINE_PEBBLE_LDZAA_PITSUNDA"]]
    if "пицунд" in blob and "бухт" in blob:
        return [BEACH_FILTERS["PITSUNDA_BAY_MIXED"]]
    if "песч" in blob:
        return [
            BEACH_FILTERS["SAND_SUKHUM"]
            if "sukhum" in cities
            else BEACH_FILTERS["SAND_LDZAA"]
        ]
    if "галеч" in blob:
        return [BEACH_FILTERS["PEBBLE"]]
    return []


def infer_room(title: str, summary: str, href: str) -> list[str]:
    blob = f"{title} {summary} {href}".lower()
    values = []
    if "вид на море" in blob:
        values.append("sea-view")
    if "прямо на берегу" in blob or "на первой линии" in blob:
        values.append("beachfront-room")
    if "бассейн" in blob:
        values.append("pool")
    if "балкон" in blob:
        values.append("balcony")
    if "террас" in blob:
        values.append("terrace")
    if "кухн" in blob:
        values.append("kitchen")
    if re.search(r"(пять|5)\s*гост", blob):
        values.append("five-plus")
    if "2к" in blob or "две комнат" in blob:
        values.append("two-room-plus")
    return dedupe(values)


def normalize_card_group_beach(raw: str, dataset_city: str, title: str, summary: str) -> list[str]:
    source = to_filter_array(raw)
    if not source:
        return []
    city_values = to_filter_array(dataset_city)
    if not city_values:
        text = f"{title} {summary}".lower()
        if "сухум" in text:
            city_values.append("sukhum")
        if "лдзаа" in text:
            city_values.append("ldzaa")
        if "пицунда" in text:
            city_values.append("pitsunda")
    return dedupe([normalize_beach_value(x, city_values) for x in source])


def parse_values_card(ds: dict[str, str], title: str, summary: str, href: str) -> dict[str, set[str]]:
    """Как parseValues в scripts.js: при непустом dataset группы — только нормализация; иначе infer."""
    out: dict[str, set[str]] = defaultdict(set)

    # distance
    raw_d = ds.get("distance", "")
    d_vals = to_filter_array(raw_d)
    if d_vals:
        for x in d_vals:
            out["distance"].add(x)
    else:
        for x in infer_distance(title, summary, href):
            out["distance"].add(x)

    # food — только dataset (infer нет)
    for x in to_filter_array(ds.get("food", "")):
        out["food"].add(x)

    # price
    raw_p = ds.get("price", "")
    p_vals = dedupe([normalize_price(x) for x in to_filter_array(raw_p)])
    for x in p_vals:
        out["price"].add(x)

    # city
    raw_c = ds.get("city", "")
    c_vals = to_filter_array(raw_c)
    if c_vals:
        for x in c_vals:
            out["city"].add(x)
    else:
        for x in infer_city(title, summary, href):
            out["city"].add(x)

    # beach
    raw_b = ds.get("beach", "")
    if raw_b:
        for x in normalize_card_group_beach(raw_b, ds.get("city", ""), title, summary):
            if x:
                out["beach"].add(x)
    else:
        cities = list(out["city"])
        for x in infer_beach(title, summary, href, cities):
            out["beach"].add(x)

    # room — если в разметке есть room, infer из текста не подмешивается
    raw_r = ds.get("room", "")
    if raw_r:
        for x in dedupe([normalize_room_value(v) for v in to_filter_array(raw_r)]):
            if x:
                out["room"].add(x)
    else:
        for x in infer_room(title, summary, href):
            out["room"].add(x)

    # stay — всегда объединение нормализованного dataset и inferStayByCard
    raw_s = ds.get("stay", "")
    for x in dedupe([normalize_stay_value(v) for v in to_filter_array(raw_s)]):
        if x:
            out["stay"].add(x)
    for x in infer_stay_by_card(title, summary, href):
        out["stay"].add(x)

    return out


CARD_RE = re.compile(
    r'<a class="catalog-card"\s([^>]*?)href="/hotels/([^/]+)/"',
    re.IGNORECASE | re.DOTALL,
)


def strip_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text)


def parse_catalog_cards(index_text: str) -> list[dict[str, Any]]:
    cards = []
    for m in CARD_RE.finditer(index_text):
        attrs, slug = m.group(1), m.group(2)
        end = index_text.find("</a>", m.end())
        body = index_text[m.end() : end if end != -1 else m.end()]
        h3_m = re.search(r"<h3>(.*?)</h3>", body, re.DOTALL | re.IGNORECASE)
        p_m = re.search(r"<p>(.*?)</p>", body, re.DOTALL | re.IGNORECASE)
        title = html_lib.unescape(strip_tags(h3_m.group(1) if h3_m else "")).strip()
        summary = html_lib.unescape(strip_tags(p_m.group(1) if p_m else "")).strip()
        ds = {}
        for am in re.finditer(r'data-filter-([a-z-]+)="([^"]*)"', attrs, re.I):
            ds[am.group(1)] = am.group(2)
        cards.append({"slug": slug, "title": title, "summary": summary, "buckets": parse_values_card(ds, title, summary, f"/hotels/{slug}/")})
    return cards


QUOTE_RE = re.compile(
    r'(?:[«\"\u201c\u201e])\s*([^»\"\u201d]{2,}?)\s*(?:[»\"\u201d])'
)


def extract_hotel_labels(site_txt: str) -> list[str]:
    names = []
    for line in site_txt.splitlines():
        line = line.strip()
        if not line or line.startswith("Наш сайт"):
            continue
        for m in QUOTE_RE.finditer(line):
            name = m.group(1).strip()
            if len(name) >= 2 and not name.startswith("http"):
                names.append(name)
    return names


def simp(s: str) -> str:
    s = s.upper().replace("Ё", "Е")
    s = re.sub(r'[«»""„‚❝❞]', "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def quoted_part_title(title: str) -> str:
    """Как короткое имя объекта на сайте — текст между первыми « »."""
    m = re.search(r"«([^»]+)»", title)
    return simp(m.group(1)) if m else simp(title)


def match_cards(query: str, cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Совпадение по имени в кавычках подборки и имени в «ёлочках» на карточке (полное равенство)."""
    q = simp(query)
    if not q:
        return []
    hits = []
    for c in cards:
        qp = quoted_part_title(c["title"])
        if qp == q:
            hits.append(c)
    return hits


# Ожидаемые токены по названию папки подборки
def rules_for_folder(folder_name: str) -> tuple[dict[str, Any] | None, str]:
    """
    Возвращает (rule, описание).
    rule = {"any": [ {"room": {"pool"}}, ...]} для ИЛИ;
           или {"room": {"pool"}, "price": {...}} для И между группами.
    """
    fn = unicodedata.normalize("NFC", folder_name.strip().lower())

    def simple(**kwargs: set[str]) -> dict[str, Any]:
        return dict(kwargs)

    if "бассейн" in fn:
        return simple(room={"pool"}), "Чип «Бассейн» (группа «Особенности номера», token pool)"
    if fn.startswith("балкон"):
        return simple(room={"balcony"}), "Чип «С балконом»"
    if "вид на море" in fn:
        return simple(room={"sea-view"}), "Чип «Вид на море»"
    if "берег моря" in fn:
        return (
            {"any": [{"distance": {"beachfront"}}, {"room": {"beachfront-room"}}]},
            "«Береговая зона» ИЛИ «Прямо на берегу»",
        )
    if "до 5 тр" in fn or "эконом" in fn:
        return simple(price={"economy"}), "Бюджет до 5000"
    if "5-12 тр" in fn or "средняк" in fn:
        return simple(price={"midrange"}), "Средний бюджет до 10000"
    if "дороже 12" in fn or "премиум" in fn:
        return simple(price={"premium"}), "Премиум-сегмент"
    if "веранда" in fn:
        return simple(room={"terrace"}), "Чип «С террасой» (веранда → terrace)"
    if "горы" in fn:
        return (
            None,
            "Отдельного фильтра «горы» на сайте нет; в тексте карточек обычно есть «горы»/«глэмпинг». Сверка только по названию.",
        )
    if "домики все" in fn:
        return simple(stay={"cottages"}), "«Домики и коттеджи»"
    if "квартиры все" in fn:
        return simple(stay={"apartments"}), "«Квартиры»"
    if "дома под ключ" in fn:
        return simple(stay={"turnkey-house"}), "«Дома под ключ»"
    if "собаки" in fn:
        return simple(stay={"pets"}), "«Можно с животными»"
    if "двухкомнатные" in fn:
        return simple(room={"two-room-plus"}), "«Две комнаты и более» (two-room-plus)"
    if "пятеро" in fn or "пятёр" in fn:
        return simple(room={"five-plus"}), "«Пять гостей и более»"
    if "своя кухня" in fn:
        return simple(room={"kitchen"}), "«Своя кухня в номере»"
    if "сосновый пляж" in fn:
        return (
            simple(beach={BEACH_FILTERS["PINE_PEBBLE_LDZAA_PITSUNDA"]}),
            "Пляж «Сосновый галечный берег Лдзаа и Пицунда»",
        )
    if "песчаный пляж сухум" in fn:
        return simple(beach={BEACH_FILTERS["SAND_SUKHUM"]}), "Песчаный пляж Сухум"
    if "питание" in fn or "кафе" in fn:
        return (
            {"food_any": {"breakfast", "half-board", "full-board", "cafe"}},
            "Хотя бы одно из питания: завтрак / полупансион / полный / кафе (не «без питания»)",
        )
    if "алахадзы все" in fn:
        return simple(city={"alakhadzy"}), "Город Алахадзы"
    if "гагра все" in fn:
        return simple(city={"gagra"}), "Город Гагра"
    if "гудаута все" in fn:
        return simple(city={"gudauta"}), "Город Гудаута"
    if "лдзаа все" in fn:
        return simple(city={"ldzaa"}), "Город Лдзаа"
    if "новый афон" in fn:
        return simple(city={"new-afon"}), "Город Новый Афон"
    if "пицунда все" in fn:
        return simple(city={"pitsunda"}), "Город Пицунда"
    if "сухум все" in fn:
        return simple(city={"sukhum"}), "Город Сухум"

    return None, "Правило не задано"


def check_rule(buckets: dict[str, set[str]], rule: dict[str, Any] | None) -> tuple[bool, str]:
    if rule is None:
        return True, "—"
    if "any" in rule:
        parts = rule["any"]
        ok_any = False
        notes = []
        for part in parts:
            o, n = check_rule(buckets, part)
            ok_any = ok_any or o
            notes.append(n)
        return ok_any, " ИЛИ ".join(notes)
    if "food_any" in rule:
        allowed = rule["food_any"]
        got = buckets.get("food", set())
        if not got:
            return False, "В карточке не заполнен data-filter-food — фильтр питания не сработает"
        if got <= {"no-food"}:
            return False, "Только «без питания»"
        if got & allowed:
            return True, f"food ∩ {sorted(got & allowed)}"
        return False, f"food={sorted(got)} не пересекается с {sorted(allowed)}"

    for group, need in rule.items():
        if group in ("any", "food_any"):
            continue
        got = buckets.get(group, set())
        inter = got & need
        if not inter:
            return False, f"нет {group} из {sorted(need)}, есть {sorted(got)}"
    parts_ok = []
    for group, need in rule.items():
        if group in ("any", "food_any"):
            continue
        got = buckets.get(group, set())
        inter = got & need
        parts_ok.append(f"{group}∩{sorted(inter)}")
    return True, "; ".join(parts_ok)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--podborki", type=Path, default=DEFAULT_PODBORKI)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    root = args.podborki
    out = args.out or (root / "соответствие_фильтрам_сайта.md")

    if not INDEX_HTML.is_file():
        print("Нет index.html", file=sys.stderr)
        return 1
    index_text = INDEX_HTML.read_text(encoding="utf-8")
    cards = parse_catalog_cards(index_text)

    site_files = sorted(root.glob("**/*_сайт.txt"))
    site_files = [p for p in site_files if "telegram_export" not in str(p)]

    lines: list[str] = []
    lines.append("# Соответствие подборок фильтрам каталога на сайте")
    lines.append("")
    lines.append(f"Источник подборок: `{root}`")
    lines.append(f"Каталог: `{INDEX_HTML}` ({len(cards)} карточек отелей)")
    lines.append("")
    lines.append(
        "Токены фильтров считаются так же, как в клиентском скрипте: сначала `data-filter-*`, "
        "при пустых значениях — вывод из текста заголовка и описания карточки (infer)."
    )
    lines.append("")

    total_names = 0
    total_matched = 0
    total_ok = 0
    total_fail = 0

    for sf in site_files:
        folder = sf.parent.name
        rule, rule_desc = rules_for_folder(folder)
        body = sf.read_text(encoding="utf-8")
        names = extract_hotel_labels(body)

        lines.append(f"## {folder}")
        lines.append("")
        lines.append(f"- Файл: `{sf.name}`")
        lines.append(f"- Ожидаемое по подборке: {rule_desc}")
        lines.append("")

        if not names:
            lines.append("_Не удалось извлечь названия в кавычках._")
            lines.append("")
            continue

        lines.append("| Название в подборке | Совпадение на сайте | Slug | Фильтр |")
        lines.append("| --- | --- | --- | --- |")

        seen_pairs: set[tuple[str, str]] = set()
        for name in names:
            total_names += 1
            mc = match_cards(name, cards)
            if not mc:
                lines.append(f"| {name} | **нет** | — | — |")
                continue
            total_matched += 1
            for c in mc:
                key = (name, c["slug"])
                if key in seen_pairs:
                    continue
                seen_pairs.add(key)
                ok, msg = check_rule(c["buckets"], rule)
                if rule is not None:
                    if ok:
                        total_ok += 1
                    else:
                        total_fail += 1
                filt = (
                    f"{'✓' if ok else '✗'} `{msg}` "
                    f"| effective: "
                    f"d={sorted(c['buckets']['distance']) or ['—']} "
                    f"f={sorted(c['buckets']['food']) or ['—']} "
                    f"p={sorted(c['buckets']['price']) or ['—']} "
                    f"c={sorted(c['buckets']['city']) or ['—']} "
                    f"b={sorted(c['buckets']['beach']) or ['—']} "
                    f"r={sorted(c['buckets']['room']) or ['—']} "
                    f"s={sorted(c['buckets']['stay']) or ['—']}"
                )
                lines.append(f"| {name} | {c['title']} | `{c['slug']}` | {filt} |")

        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Итого")
    lines.append("")
    lines.append(f"- Упоминаний отелей в подборках (по строкам с кавычками): **{total_names}**")
    lines.append(f"- Сопоставлено хотя бы с одной карточкой: **{total_matched}**")
    if total_ok + total_fail > 0:
        lines.append(f"- Проверок фильтра (где правило задано): **{total_ok}** ок / **{total_fail}** расхождение")
    lines.append("")

    out_text = "\n".join(lines)
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(out_text, encoding="utf-8")
        print(out)
    except OSError as e:
        # fallback в репозиторий
        alt = REPO_ROOT / "podbori_filter_audit.md"
        alt.write_text(out_text, encoding="utf-8")
        print(f"{e}\nЗаписано в {alt}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
