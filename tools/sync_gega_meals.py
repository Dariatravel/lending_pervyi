"""Перенос условий питания из публичного поста Геги в данные сайта."""
import calendar
import json
import re
from datetime import date
from pathlib import Path
from urllib.request import urlopen

from bs4 import BeautifulSoup

OUTPUT = Path(__file__).resolve().parents[1] / "assets/gega-meals.json"
MONTHS = ("января", "февраля", "марта", "апреля", "мая", "июня",
          "июля", "августа", "сентября", "октября", "ноября", "декабря")
MONTH = "|".join(MONTHS)
PERIOD = re.compile(
    rf"^[сc]\s+(\d{{1,2}})(?:\s+({MONTH}))?(?:\s+(20\d{{2}}))?"
    rf"(?:\s*(?:по|до|[-–—])\s*(\d{{1,2}})\s+({MONTH})(?:\s+(20\d{{2}}))?)?(.*)$",
    re.I,
)


def meal(text):
    if re.search(r"без\s+ужин", text, re.I) and re.search(r"с\s+завтрак", text, re.I):
        return "С завтраком, без ужина"
    for pattern, label in (
        (r"без\s+питан", "Без питания"),
        (r"без\s+завтрак", "Без завтрака"),
        (r"завтрак.*ужин", "Завтрак и ужин"),
        (r"\bс\s+завтрак", "С завтраком"),
        (r"тр[её]хразов", "Трёхразовое питание"),
    ):
        if re.search(pattern, text, re.I):
            return label
    return ""


def periods(lines, published):
    season = published.year - (published.month < 9)
    section = False
    result = []
    for line in lines:
        if re.match(r"^[^\w]*ЦЕНЫ\b", line, re.I):
            section = True
            continue
        if re.match(r"^[✔✓✅]", line):
            section = False
        if not section:
            continue
        if re.search(r"₽|руб|доп.?\s*мест|сауна", line, re.I):
            continue
        match = PERIOD.fullmatch(line)
        if not match:
            continue
        day, month, year, last_day, last_month, last_year, suffix = match.groups()
        month = month or last_month
        if not month:
            continue
        start_month = MONTHS.index(month.lower()) + 1
        start = date(int(year) if year else season + (start_month < 9), start_month, int(day))
        if last_month:
            end_month = MONTHS.index(last_month.lower()) + 1
            end = date(int(last_year) if last_year else start.year + (end_month < start_month),
                       end_month, int(last_day))
            if not year and last_year and end.year != start.year + (end_month < start_month):
                start = start.replace(year=end.year - (end_month < start_month))
        else:
            extra = re.match(r"^\s*,\s*февраль\s*,\s*март\b", suffix, re.I)
            through = re.match(r"^\s*по\s+март\b", suffix, re.I)
            if not (extra or through) or start_month != 1:
                continue
            end = date(start.year, 3, calendar.monthrange(start.year, 3)[1])
        if end < start:
            continue
        result.append(dict(start=start.isoformat(), end=end.isoformat(), meal=meal(suffix)))
    return result


def main():
    with urlopen("https://t.me/abhazbooking/5510?embed=1", timeout=25) as response:
        doc = BeautifulSoup(response.read(), "html.parser")
    post = doc.select_one('[data-post="abhazbooking/5510"]')
    if not post or not post.select_one(".js-message_text") or not post.select_one("time[datetime]"):
        raise SystemExit("Не удалось прочитать публикацию Геги")
    # Telegram использует br для строк, а b/i для выделения частей строки.
    content = post.select_one(".js-message_text")
    for br in content.find_all("br"):
        br.replace_with("\n")
    lines = [line.strip() for line in content.get_text().splitlines()]
    published = date.fromisoformat(post.select_one("time")["datetime"][:10])
    OUTPUT.write_text(json.dumps(periods(lines, published), ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
