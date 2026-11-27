"""Обновить только публичные блоки Киры, сохраняя остальную готовую страницу."""
import argparse
import json
import re
from collections import Counter
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import urlopen
from uuid import UUID

from bs4 import BeautifulSoup
from public_guest_layout import PUBLIC_CONDITIONS, media_group

ROOT = Path(__file__).resolve().parents[1]
HOTEL = "73976495-c594-4497-b1e8-a84aac611e69"
SLUG = "kira-gostevoy-kompleks-2725"
SNAPSHOT = ROOT / "data" / "hotel-public-layout" / (SLUG + ".json")
PAGE = ROOT / "hotels" / SLUG / "index.html"
API = "https://abhazbereg.online/api/public/kira-layout"


def schema(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError("Неожиданные поля гостевой выгрузки")


def strings(row, keys):
    schema(row, keys)
    if not all(isinstance(value, str) for value in row.values()):
        raise ValueError("Гостевая строка имеет неверный тип")


def validate(data):
    schema(data, ("hotel_id", "slug", "guest_title", "guest_address", "guest_description", "guest_nearby", "conditions", "media", "groups", "prices"))
    if data["hotel_id"] != HOTEL or data["slug"] != SLUG:
        raise ValueError("Неверная привязка карточки")
    for key in ("guest_title", "guest_address", "guest_description", "guest_nearby"):
        if data[key] is not None and not isinstance(data[key], str):
            raise ValueError("Неверное название или адрес")
    schema(data["conditions"], PUBLIC_CONDITIONS)
    if any(value is not None and type(value) not in (str, int) for value in data["conditions"].values()):
        raise ValueError("Некорректные условия")
    if not isinstance(data["groups"], list) or not isinstance(data["media"], list):
        raise ValueError("Некорректный состав галереи")
    for group in data["groups"]:
        strings(group, ("title", "badge"))
    if len({g["title"] for g in data["groups"]}) != len(data["groups"]):
        raise ValueError("Повтор группы")
    for row in data["media"]:
        strings(row, ("id", "key", "kind", "group"))
        UUID(row["id"])
        if row["kind"] not in ("photo", "video") or not re.fullmatch("media/(?:videos/)?hotels/" + SLUG + r"/[\w.%-]+", row["key"]):
            raise ValueError("Недопустимый ключ медиа")
    if len({m["id"] for m in data["media"]}) != len(data["media"]):
        raise ValueError("Повтор файла")
    prices = data["prices"]
    if prices is not None:
        schema(prices, ("description", "groups"))
        if not isinstance(prices["description"], str) or not isinstance(prices["groups"], list):
            raise ValueError("Некорректный тариф")
        for group in prices["groups"]:
            schema(group, ("title", "note", "mode", "freeText", "rows"))
            if (group["mode"] not in ("text", "rows") or not isinstance(group["rows"], list)
                    or not all(isinstance(group[k], str) for k in ("title", "note", "freeText"))):
                raise ValueError("Некорректный блок цен")
            for row in group["rows"]:
                strings(row, ("amount", "period", "note"))
    return data


def media_key(item):
    file = item if item.name == "img" else item.find("source")
    url = urlsplit(file.get("src", "") if file else "")
    path = url.path.lstrip("/")
    if url.scheme == "https" and url.hostname == "media.xn--80aacbklan7f0b.xn--p1ai":
        return path
    if url.scheme == "https" and url.hostname == "storage.yandexcloud.net" and path.startswith("abhazbereg-media/"):
        return path.split("/", 1)[1]
    return None


def gallery(frame, data):
    files = [item for grid in frame.select(".media-grid") for item in grid.find_all(recursive=False)]
    if not files or not data["media"]:
        return str(frame)
    rows = data["media"]
    by_id = {m["id"]: m for m in rows}
    by_key = {m["key"]: m for m in rows}
    counts = Counter(m["key"] for m in rows)
    page_counts = Counter(media_key(f) for f in files)
    groups = {m["title"]: [] for m in data["groups"]}
    badges = {m["title"]: m["badge"] for m in data["groups"]}
    matched = {}
    unmatched = []
    for item in files:
        key = media_key(item)
        explicit = item.get("data-crm-media-id")
        row = by_id.get(explicit) if explicit else by_key.get(key) if counts[key] == page_counts[key] == 1 else None
        kind = "photo" if item.name == "img" else "video"
        if row and row["key"] == key and row["kind"] == kind and row["id"] not in matched:
            item["data-crm-media-id"] = row["id"]
            matched[row["id"]] = str(item)
        else:
            unmatched.append(str(item))
    if not matched:
        return str(frame)
    for row in rows:
        if row["id"] in matched:
            groups.setdefault(row["group"], []).append(matched[row["id"]])
    groups.setdefault("", []).extend(unmatched)
    return '<div class="media-group-frame">' + "".join(
        media_group(name, badges.get(name, ""), "\n".join(items))
        for name, items in groups.items() if items
    ) + "</div>"


class TagEnd(HTMLParser):
    """Граница выбранного блока. Окружающий HTML остаётся побайтно прежним."""
    def __init__(self, text, name):
        super().__init__(convert_charrefs=False)
        self.depth, self.end, self.name = 0, None, name
        self.offsets = [0] + [m.end() for m in re.finditer("\n", text)]
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        if self.end is None and tag == self.name:
            self.depth += 1

    def handle_endtag(self, tag):
        if self.end is None and tag == self.name:
            self.depth -= 1
            if self.depth == 0:
                line, col = self.getpos()
                self.end = self.offsets[line - 1] + col + len(tag) + 3


INLINE = re.compile(
    r"\*\*([^*\n]+)\*\*|\*([^*\n]+)\*|\[([^\]\n]+)\]\((https?://[^\s()<>\\]+)\)"
    r"|\[\[(u|q)\|([^\]\n]+)\]\]|~~([^~\n]+)~~|`([^`\n]+)`|\|\|([^|\n]+)\|\|"
)


def guest_inline(line):
    parts, pos = [], 0
    for match in INLINE.finditer(line):
        parts.append(escape(line[pos:match.start()]))
        strong, italic, label, url, kind, special, deleted, code, hidden = match.groups()
        if url:
            parts.append(f'<a href="{escape(url)}" rel="noopener noreferrer">{escape(label)}</a>')
        elif hidden:
            parts.append(f'<button type="button" class="guest-spoiler" aria-label="Показать скрытый текст">{escape(hidden)}</button>')
        else:
            tag = kind or ("strong" if strong else "em" if italic else "s" if deleted else "code")
            parts.append(f"<{tag}>{escape(strong or italic or special or deleted or code)}</{tag}>")
        pos = match.end()
    return "".join(parts) + escape(line[pos:])


def render_prices(doc):
    lines = ['<h2 class="price-card__heading">ЦЕНЫ:</h2>']
    if doc["description"]:
        lines.append('<p class="price-card__description">' + escape(doc["description"]) + '</p>')
    for group in doc["groups"]:
        rows = [(" - ".join(filter(None, ((r["amount"] + "₽") if r["amount"] else "", r["period"]))), r["note"]) for r in group["rows"]]
        if group["mode"] == "text":
            def price_key(text):
                return re.sub(r"\s+", "", text).replace("–", "-").replace("—", "-")
            notes = {price_key(line): note for line, note in rows}
            rows = [(line, notes.get(price_key(line), "")) for line in group["freeText"].splitlines()]
        title = '<h3 class="price-card__group">' + escape(group["title"]) + '</h3>'
        note = '<p>' + escape(group["note"]) + '</p>' if group["note"] else ""
        lines.append('<div class="price-card__tariff-group">' + title + note + '<ul class="price-card__seasons">' +
                     "".join('<li class="price-card__season-line">' + escape(v) + (' · ' + escape(n) if n else '') + '</li>' for v, n in rows if v.strip()) + '</ul></div>')
    return '<section id="prices" class="section hotel-price-section hotel-site-concept__detail-section"><article class="card price-card">' + "".join(lines) + '</article></section>'


def apply_snapshot(page, data):
    validate(data)
    soup = BeautifulSoup(page, "html.parser")
    frame = soup.select_one(".hotel-media-section .media-group-frame")
    if not frame:
        raise ValueError("Нет галереи рабочей Киры")
    replacements = [(frame, gallery(frame, data))]
    facts = "".join("<div><dt>" + escape(label) + ":</dt> <dd>" + escape(str(data["conditions"][label])) + "</dd></div>"
                    for label in PUBLIC_CONDITIONS if data["conditions"][label] not in (None, ""))
    conditions = soup.select_one(".guest-conditions")
    if not conditions:
        raise ValueError("Нет блока условий")
    replacements.append((conditions, '<section class="section card guest-conditions"' + ('' if facts else ' hidden') +
                         '><h2>Условия проживания</h2><dl class="study-facts">' + facts + '</dl></section>'))
    if data["prices"] is not None:
        prices = soup.select_one("#prices")
        if prices:
            replacements.append((prices, render_prices(data["prices"])))
        else:
            replacements[-1] = (conditions, render_prices(data["prices"]) + replacements[-1][1])
    if data["guest_title"]:
        title = soup.select_one("h1")
        if not title:
            raise ValueError("Не найден заголовок карточки")
        title.string = data["guest_title"]
        replacements.append((title, str(title)))
    if data["guest_address"]:
        location = soup.select_one("p.location")
        if not location:
            raise ValueError("Не найдена строка адреса")
        first = location.find(string=lambda value: str(value).strip().startswith("📍"))
        if first:
            first.replace_with("📍 " + data["guest_address"])
        else:
            location.insert(0, soup.new_tag("br"))
            location.insert(0, "📍 " + data["guest_address"])
        replacements.append((location, str(location)))
    line_offsets = [0] + [m.end() for m in re.finditer("\n", page)]
    patches = []
    for key, label in (("guest_description", "Об объекте"), ("guest_nearby", "Рядом")):
        value = data[key]
        if value is None:
            continue
        details = []
        for block in soup.select("section.hotel-site-concept__detail-section"):
            heading = block.find("h2")
            if not heading or not block.select_one(".paragraph-blocks"):
                continue
            title = heading.get_text(strip=True).strip("✔️: ").casefold()
            if (title == "рядом" if key == "guest_nearby" else title not in ("важно", "рядом")):
                details.append(block)
        body = "".join("<p>" + guest_inline(line) + "</p>" for line in value.splitlines() if line.strip())
        html = ('<section class="section hotel-site-concept__detail-section"><article class="card"><h2>' +
                label + '</h2><div class="paragraph-blocks">' + body + '</div></article></section>') if body else ""
        if details:
            replacements.extend((detail, html if i == 0 else "") for i, detail in enumerate(details))
        elif html:
            offset = line_offsets[conditions.sourceline - 1] + conditions.sourcepos
            patches.append((offset, offset, html))
    for tag, replacement in replacements:
        offset = line_offsets[tag.sourceline - 1] + tag.sourcepos
        end = TagEnd(page[offset:], tag.name).end
        if not end:
            raise ValueError("Незакрытый блок")
        patches.append((offset, offset + end, replacement))
    for start, end, replacement in sorted(patches, reverse=True):
        page = page[:start] + replacement + page[end:]
    return page


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    with urlopen(API, timeout=20) as result:
        data = validate(json.loads(result.read(2_000_000)))
    html = apply_snapshot(PAGE.read_text(), data)
    if args.apply:
        SNAPSHOT.parent.mkdir(exist_ok=True)
        SNAPSHOT.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
        PAGE.write_text(html)


if __name__ == "__main__":
    main()
