"""Оформление гостевой страницы по публичным значениям рабочей карточки."""
import json
from html import escape
from pathlib import Path


PUBLIC_CONDITIONS = (
    "Заезд с", "Выезд до", "Минимум ночей", "Дети", "С питомцами",
    "Питание", "Кухня", "Правила проживания", "Удобства", "Парковка",
    "Место для курения", "Депозит", "Курортный сбор",
)
PUBLIC_DATA = Path(__file__).resolve().parents[1] / "data" / "hotel-public-conditions"


def media_group(group, badge, contents):
    marker = f'<p class="media-group-badge">{escape(badge)}</p>' if group and badge else ""
    heading = f"<h3>{escape(group)}</h3>" if group else ""
    return (f'<section class="card media-group-card">{marker}{heading}'
            f'<div class="media-grid">{contents}</div></section>')


def guest_conditions(slug):
    if not slug or Path(slug).name != slug:
        return ""
    path = PUBLIC_DATA / (slug + ".json")
    if not path.is_file():
        return ""
    values = json.loads(path.read_text(encoding="utf-8"))
    rows = "".join(
        f"<div><dt>{escape(label)}:</dt> <dd>{escape(values[label])}</dd></div>"
        for label in PUBLIC_CONDITIONS if isinstance(values.get(label), str) and values[label].strip()
    )
    if not rows:
        return ""
    return ('<section class="section card guest-conditions"><h2>Условия проживания</h2>'
            f'<dl class="study-facts">{rows}</dl></section>')
