"""Виртуальные 3D-туры объектов.

Ссылки на туры хранятся в data/virtual-tours.json (slug -> {url, title}) и
вставляются генераторами в HTML при каждой сборке/пересборке страницы —
так блок переживает авто-синк и не зависит от Telegram-поста.

Режим показа: превью (обложка объекта) + кнопка «Открыть 3D-тур»; сам iframe
тура грузится только по клику (быстрее и без автозвука) — логика в scripts.js.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOURS_PATH = ROOT / "data" / "virtual-tours.json"


def load_tours() -> dict[str, dict]:
    if not TOURS_PATH.is_file():
        return {}
    try:
        data = json.loads(TOURS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _render_section(entry: dict, cover_url: str) -> str:
    url = str(entry.get("url") or "").strip()
    if not url:
        return ""
    title = str(entry.get("title") or "Виртуальный 3D-тур").strip()
    url_a = html.escape(url, quote=True)
    title_a = html.escape(title, quote=True)
    title_t = html.escape(title)
    style = f" style=\"background-image:url('{html.escape(cover_url, quote=True)}')\"" if cover_url else ""
    return (
        '<section class="section hotel-site-concept__detail-section virtual-tour-section" data-virtual-tour>'
        '<article class="card">'
        f'<h2>{title_t}</h2>'
        f'<div class="virtual-tour" data-tour-url="{url_a}" data-tour-title="{title_a}">'
        f'<div class="virtual-tour__preview"{style} role="img" aria-label="{title_a}"></div>'
        '<button type="button" class="virtual-tour__play">'
        '<span class="virtual-tour__badge">360°</span>'
        '<span class="virtual-tour__cta">Открыть 3D-тур</span>'
        '</button>'
        '</div>'
        '</article>'
        '</section>'
    )


def apply_tour_to_page(page_html: str, slug: str, cover_url: str = "") -> str:
    """Вставить блок «Виртуальный 3D-тур» в HTML страницы объекта.

    Идемпотентно: если блок уже есть (data-virtual-tour) или тура для slug нет —
    HTML не меняется. Вставка строковая (без переформатирования всей страницы):
    после секции фото, иначе перед отзывами / первой detail-секцией.
    """
    if "data-virtual-tour" in page_html:
        return page_html
    entry = load_tours().get(slug)
    if not entry:
        return page_html
    section = _render_section(entry, cover_url)
    if not section:
        return page_html

    # 1) после секции «Фото и видео»
    new_html, n = re.subn(
        r'(<section class="section hotel-media-section.*?</section>)',
        lambda m: m.group(1) + section,
        page_html,
        count=1,
        flags=re.S,
    )
    if n:
        return new_html
    # 2) перед блоком отзывов
    new_html, n = re.subn(r'(<section class="reviews-panel)', section + r"\1", page_html, count=1)
    if n:
        return new_html
    # 3) перед первой detail-секцией
    new_html, n = re.subn(r'(<section class="section hotel-site-concept__detail-section)', section + r"\1", page_html, count=1)
    if n:
        return new_html
    return page_html
