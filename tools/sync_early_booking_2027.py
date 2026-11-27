"""Refresh catalogue badges from Alina's workbook without changing prices."""
import json
import sys
from io import BytesIO
from pathlib import Path
from urllib.request import urlopen

from openpyxl import load_workbook

URL = "https://drive.google.com/uc?export=download&id=1kIJHcCd7PWx9yn9EEgaY2iYYpl_-rtx1"
DATA = Path(__file__).resolve().parents[1] / "data"


def normalized(value):
    return " ".join(str(value or "").casefold().split()).replace("ё", "е")


def read_statuses(book):
    sheet = book["Лист1"]
    rows = iter(sheet.values)
    headers = [normalized(value) for value in next(rows)]
    name, status = headers.index("отель"), next(index for index, value in enumerate(headers) if value in {"2027", "2027.0"})
    statuses = {}
    duplicates = set()
    for row in rows:
        key = normalized(row[name])
        if not key:
            continue
        if key in statuses:
            duplicates.add(key)
        statuses[key] = normalized(row[status] if status < len(row) else None)
    return {key: value for key, value in statuses.items() if key not in duplicates}


def refresh(statuses, mapping, previous):
    mapped_names = {normalized(name) for names in mapping.values() for name in names}
    if len(mapped_names & statuses.keys()) < len(mapped_names) * 0.9:
        raise ValueError("Таблица неполная или изменилась структура названий")
    confirmed = {"да, цены есть", "цены есть"}
    result = set(previous)
    missing = []
    for slug, names in mapping.items():
        keys = [normalized(name) for name in names]
        if any(key not in statuses for key in keys):
            missing.append(slug)
            continue
        if all(statuses[key] in confirmed for key in keys):
            result.add(slug)
        else:
            result.discard(slug)
    return sorted(result), missing


def main():
    with urlopen(URL, timeout=35) as response:
        workbook = load_workbook(BytesIO(response.read(8 * 1024 * 1024)), read_only=True, data_only=True)
    try:
        statuses = read_statuses(workbook)
    finally:
        workbook.close()
    mapping = json.loads((DATA / "early-booking-2027-mapping.json").read_text())
    path = DATA / "early-booking-2027.json"
    previous = json.loads(path.read_text())
    result, missing = refresh(statuses, mapping, previous)
    print(f"Сопоставлено карточек: {len(mapping) - len(missing)}. Плашек: {len(result)}.")
    print(f"Добавить: {len(set(result) - set(previous))}. Снять: {len(set(previous) - set(result))}.")
    if missing:
        print("::warning::Нужно сверить названия: " + ", ".join(missing))
    if "--check" not in sys.argv:
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
