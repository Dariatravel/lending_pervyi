#!/usr/bin/env python3
"""Синхронизация статей блога из канала @abhazbereg (Telethon → media + HTML)."""

from __future__ import annotations

import asyncio
import html
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from telegram_runtime import connected_telegram_client, run_async_entrypoint  # noqa: E402

API_ID = 32916166
API_HASH = "eefdec49605521b061de4bdf62ef784e"
SESSION = os.getenv("TG_SESSION", str(ROOT / "tg_session"))
CHANNEL = "abhazbereg"
MEDIA_DIR = ROOT / "media" / "blog"
SOURCES_DIR = ROOT / "scripts" / "blog_telegram_sources"
BLOG_DIR = ROOT / "blog"
CSS_VERSION = (ROOT / "data" / "asset-version.txt").read_text(encoding="utf-8").strip()
YANDEX_MEDIA_BASE = "https://storage.yandexcloud.net/abhazbereg-media"
BLOG_CARD_IMAGE_SIZES = "(max-width: 760px) 100vw, 220px"
BLOG_ARTICLE_IMAGE_SIZES = "(max-width: 760px) 100vw, 320px"


def blog_image_srcset(src: str) -> str:
    clean = src.split("?", 1)[0]
    stem, dot, ext = clean.rpartition(".")
    if not dot or ext.lower() not in {"jpg", "jpeg", "png", "webp"}:
        return ""
    return ", ".join(f"{stem}-{width}.webp {width}w" for width in (480, 960, 1440))

POST_IDS = [
    2119, 2149, 2166, 2213, 2218, 2240, 2245, 2256, 2261, 2266, 2294, 2313, 2325, 2327, 2336, 2337,
    2383, 2385, 2392, 2411, 2421, 2422, 2423, 2458, 2460, 2461,
]

# slug и SEO-поля; title/lead дополняются из текста поста при необходимости
POST_META: dict[int, dict[str, object]] = {
    2119: {
        "slug": "chego-boyatsya-v-abhazii",
        "title": "Чего бояться в Абхазии: честный разбор страхов туристов",
        "lead": "Разбираем типичные тревоги перед первой поездкой — без пугалок и без розовых очков.",
        "breadcrumb": "Страхи туристов",
        "eyebrow": "Первый раз",
        "tags": ("первая поездка", "безопасность", "мифы"),
        "card_tag": "мифы",
    },
    2149: {
        "slug": "rotavirus-mify-otdyh-more",
        "title": "Ротавирус и отдых у моря: что правда, а что миф",
        "lead": "Разбираем популярные страхи про ротавирус в Абхазии и как снизить риски на отдыхе.",
        "breadcrumb": "Ротавирус",
        "eyebrow": "Здоровье",
        "tags": ("здоровье", "дети", "море"),
        "card_tag": "здоровье",
    },
    2166: {
        "slug": "kak-projti-granicu-psou",
        "title": "Как пройти границу Россия — Абхазия на КПП Псоу",
        "lead": "Пеший переход, авто, автобус, документы, очереди, туалеты и Duty Free — по шагам.",
        "breadcrumb": "Граница Псоу",
        "eyebrow": "Граница",
        "tags": ("граница", "документы", "КПП Псоу"),
        "card_tag": "граница",
    },
    2213: {
        "slug": "dengi-i-oplata-v-abhazii",
        "title": "Деньги и оплата в Абхазии: что взять с собой",
        "lead": "Рубли, карты, банкоматы, обмен и на что рассчитывать в магазинах и на пляже.",
        "breadcrumb": "Деньги",
        "eyebrow": "Практика",
        "tags": ("деньги", "оплата", "банкоматы"),
        "card_tag": "деньги",
    },
    2218: {
        "slug": "peschanye-plyazhi-abhazii",
        "title": "Где в Абхазии песчаные пляжи",
        "lead": "Пицунда, Гагра, Сухум и другие локации — где мелкий песок и кому какой берег подойдёт.",
        "breadcrumb": "Песчаные пляжи",
        "eyebrow": "Пляжи",
        "tags": ("пляжи", "песок", "курорты"),
        "card_tag": "пляжи",
    },
    2240: {
        "slug": "goryachie-istochniki-abhazii",
        "title": "Горячие источники в Абхазии: куда поехать и что учесть",
        "lead": "Куам, Кындыг, Адзюбжа и другие точки — как добраться и на что обратить внимание.",
        "breadcrumb": "Горячие источники",
        "eyebrow": "Экскурсии",
        "tags": ("источники", "экскурсии", "Рица"),
        "card_tag": "источники",
    },
    2245: {
        "slug": "shtraf-za-kupalnik-v-abhazii",
        "title": "Штраф за купальник в Абхазии: что грозит туристам",
        "lead": "Разбираем, где действуют ограничения, какие суммы называют и как не попасть впросак.",
        "breadcrumb": "Штраф за купальник",
        "eyebrow": "Правила",
        "tags": ("правила", "пляж", "штрафы"),
        "card_tag": "правила",
    },
    2256: {
        "slug": "prava-i-shtrafy-avto-abhaziya",
        "title": "ПДД и штрафы на машине в Абхазии",
        "lead": "Скорость, ремни, телефон, алкоголь, парковка и типичные суммы по сообщениям туристов.",
        "breadcrumb": "ПДД и штрафы",
        "eyebrow": "Авто",
        "tags": ("авто", "ПДД", "штрафы"),
        "card_tag": "авто",
    },
    2261: {
        "slug": "marshrutki-ot-granitsy-psou",
        "title": "Маршрутки от границы Псоу: куда едут и сколько стоят",
        "lead": "Как добраться до Гагры, Пицунды, Сухума и других курортов сразу после КПП.",
        "breadcrumb": "Маршрутки",
        "eyebrow": "Транспорт",
        "tags": ("транспорт", "граница", "маршрутки"),
        "card_tag": "транспорт",
    },
    2266: {
        "slug": "neft-tuapse-i-more-abhaziya",
        "title": "Нефть у Туапсе и море в Абхазии: что известно туристам",
        "lead": "Актуальная сводка по ситуации с разливом и на что смотреть при планировании отдыха.",
        "breadcrumb": "Нефть и море",
        "eyebrow": "Актуально",
        "tags": ("экология", "море", "новости"),
        "card_tag": "новости",
    },
    2294: {
        "slug": "parom-sochi-suhum-kometa",
        "title": "Паром Сочи — Сухум «Комета»: как добраться морем",
        "lead": "Расписание, билеты, посадка, багаж и практические нюансы морского маршрута.",
        "breadcrumb": "Паром Сочи — Сухум",
        "eyebrow": "Транспорт",
        "tags": ("паром", "Сухум", "Сочи"),
        "card_tag": "паром",
    },
    2313: {
        "slug": "edinyj-bilet-v-abhaziyu",
        "title": "Единый билет в Абхазию: как работает и кому подходит",
        "lead": "Поезд до границы плюс автобус дальше — что входит, где купить и на что обратить внимание.",
        "breadcrumb": "Единый билет",
        "eyebrow": "Транспорт",
        "tags": ("билеты", "поезд", "транспорт"),
        "card_tag": "билеты",
    },
    2325: {
        "slug": "proverka-dolgov-pered-poezdkoj",
        "title": "Собрались в Абхазию? Проверьте долги до поездки",
        "lead": "Почему задолженности могут помешать на границе и как проверить себя заранее.",
        "breadcrumb": "Долги и граница",
        "eyebrow": "Документы",
        "tags": ("долги", "граница", "ФССП"),
        "card_tag": "документы",
    },
    2327: {
        "slug": "poezdka-v-abhaziyu-s-zhivotnym",
        "title": "Поездка в Абхазию с животным: документы и нюансы",
        "lead": "Ветпаспорт, прививки, перевозка в транспорте и что уточнить до выезда.",
        "breadcrumb": "С животными",
        "eyebrow": "Практика",
        "tags": ("животные", "документы", "ветеринар"),
        "card_tag": "с питомцем",
    },
    2336: {
        "slug": "poezda-i-samolet-do-suhuma",
        "title": "Как добраться в Абхазию напрямую: поезда и самолёты до Сухума",
        "lead": "Актуальные маршруты, остановки, билеты и что учесть при планировании дороги.",
        "breadcrumb": "Поезда и самолёты",
        "eyebrow": "Транспорт",
        "tags": ("поезд", "самолёт", "Сухум"),
        "card_tag": "транспорт",
    },
    2337: {
        "slug": "poezd-po-svidetelstvu-rozhdeniya",
        "title": "Поезд в Абхазию по свидетельству о рождении: что изменилось",
        "lead": "РЖД снова принимает свидетельство для детей до 14 лет — при каком условии и до какой даты.",
        "breadcrumb": "Поезд и дети",
        "eyebrow": "Документы",
        "tags": ("дети", "поезд", "документы"),
        "card_tag": "дети",
    },
    2383: {
        "slug": "chto-takoe-citrusovyy-abhaziya",
        "title": "Что такое Цитрусовый в Абхазии: это Пицунда или Алахадзы?",
        "lead": "Разбираем, где на карте находится Цитрусовый, чем отличается от Пицунды и кому подойдёт этот тихий посёлок у моря.",
        "breadcrumb": "Цитрусовый",
        "eyebrow": "Куда поехать",
        "tags": ("курорты", "Пицунда", "пляжи"),
        "card_tag": "курорты",
    },
    2385: {
        "slug": "vremya-v-abhazii-moskovskoe",
        "title": "Сколько времени в Абхазии и почему телефон может показывать другое",
        "lead": "В Абхазии московское время, но смартфон иногда переводит час вперёд — как проверить настройки на границе.",
        "breadcrumb": "Время в Абхазии",
        "eyebrow": "Практика",
        "tags": ("время", "граница", "смартфон"),
        "card_tag": "практика",
    },
    2392: {
        "slug": "zagar-i-spf-na-more-abhaziya",
        "title": "Загар и SPF на море в Абхазии: полезная напоминалка",
        "lead": "Почему на побережье легко обгореть даже в облачную погоду, какой SPF взять и как не испортить отпуск красными плечами.",
        "breadcrumb": "Загар и SPF",
        "eyebrow": "Здоровье",
        "tags": ("здоровье", "пляж", "SPF"),
        "card_tag": "здоровье",
    },
    2411: {
        "slug": "duty-free-na-granitse-psou",
        "title": "Duty Free на границе Россия — Абхазия: где находится и как попасть",
        "lead": "Где расположен магазин на Псоу, как зайти пешком или на машине и чего ждать от цен и режима работы.",
        "breadcrumb": "Duty Free на Псоу",
        "eyebrow": "Граница",
        "tags": ("граница", "Псоу", "Duty Free"),
        "card_tag": "граница",
    },
    2421: {
        "slug": "veyp-i-elektronnye-sigarety-abhaziya",
        "title": "Едем в Абхазию с вейпом: нас пустят?",
        "lead": "Запрет на ввоз, продажу и рекламу электронных сигарет с 2024 года — что это значит для туристов и как обстоят дела с IQOS и glo.",
        "breadcrumb": "Вейпы и электронки",
        "eyebrow": "Правила",
        "tags": ("правила", "вейп", "табак"),
        "card_tag": "правила",
    },
    2422: {
        "slug": "ldzaa-shtil-pitsunda-volny",
        "title": "В Лдзаа штиль, а в Пицунде волны: почему так?",
        "lead": "Почему море в бухте Лдзаа часто спокойнее, чем в открытой Пицунде — и как выбирать курорт под свой формат отдыха.",
        "breadcrumb": "Лдзаа и Пицунда",
        "eyebrow": "Пляжи",
        "tags": ("пляжи", "Лдзаа", "Пицунда"),
        "card_tag": "пляжи",
    },
    2423: {
        "slug": "paraplany-gagra-mamzyshha",
        "title": "Парапланы над Гагрой: полёт с Мамзышхи для туристов",
        "lead": "Как устроен тандемный полёт над Гагрой, сколько длится, где стартуют и от чего зависит цена.",
        "breadcrumb": "Параплан Гагра",
        "eyebrow": "Экскурсии",
        "tags": ("экскурсии", "Гагра", "параплан"),
        "card_tag": "экскурсии",
    },
    2458: {
        "slug": "suhum-ili-sochi-kakoy-reys-vybrat",
        "title": "Сухум или Сочи: какой рейс выбрать для поездки в Абхазию",
        "lead": "Сравниваем дорогу через аэропорты Сочи и Сухума: какой маршрут удобнее для Гагры, Пицунды, Нового Афона и восточной Абхазии.",
        "breadcrumb": "Аэропорты Сухума и Сочи",
        "eyebrow": "Транспорт",
        "tags": ("самолёт", "Сухум", "Сочи"),
        "card_tag": "транспорт",
    },
    2460: {
        "slug": "plyazhi-abhazii-obzor-chast-1",
        "title": "Пляжи Абхазии от границы до Гудауты: большой обзор, часть 1",
        "lead": "Идём вдоль берега от Цандрипша до Гудауты: где широкая галька, где песок, где сосны у воды и куда ехать за тишиной или курортной жизнью.",
        "breadcrumb": "Пляжи: часть 1",
        "eyebrow": "Пляжи",
        "tags": ("пляжи", "Гагра", "Пицунда"),
        "card_tag": "пляжи",
    },
    2461: {
        "slug": "plyazhi-abhazii-obzor-chast-2",
        "title": "Пляжи Абхазии от Гудауты до восточных берегов: обзор, часть 2",
        "lead": "Продолжаем обзор: Новый Афон, городские пляжи Сухума, Мокко и Синопский, а дальше — тихие дикие берега Восточной Абхазии для интровертов.",
        "breadcrumb": "Пляжи: часть 2",
        "eyebrow": "Пляжи",
        "tags": ("пляжи", "Сухум", "Новый Афон"),
        "card_tag": "пляжи",
    },
}

EXISTING_CARDS = [
    {
        "slug": "mobilnaya-svyaz-i-internet-abkhaziya",
        "iso_date": "2026-03-24",
        "card_tag": "связь",
        "title": "Что важно знать про связь в Абхазии",
        "excerpt": "Роуминг российских SIM, местные операторы, eSIM, Wi‑Fi и что сделать сразу после границы.",
        "image": "telegram-3821.jpg",
        "alt": "Связь и интернет в Абхазии",
    },
    {
        "slug": "pravila-poezdki-s-detmi-abkhaziya-2026",
        "iso_date": "2026-03-15",
        "card_tag": "документы",
        "title": "Важные правила поездки в Абхазию с детьми в 2026 году",
        "excerpt": "Загранпаспорт, билеты до городов Абхазии, сопровождение и нотариальное согласие — по шагам.",
        "image": "telegram-3758.jpg",
        "alt": "Поездка с детьми в Абхазию — документы",
    },
    {
        "slug": "inostrannye-pravila-vezda-abkhazia",
        "iso_date": "2026-03-13",
        "card_tag": "въезд и виза",
        "title": "Въезд в Абхазию: для каких стран действуют иностранные правила",
        "excerpt": "Кому нужна виза, как получить разрешение на въезд и где обращаться после прибытия в Абхазию.",
        "image": "telegram-3757.jpg",
        "alt": "Въезд в Абхазию для иностранных граждан",
    },
    {
        "slug": "minusy-otdyha-abkhazia",
        "iso_date": "2026-03-10",
        "card_tag": "честный разбор",
        "title": "Абхазия: минусы отдыха без пугалок и розовых очков",
        "excerpt": "Что может не понравиться в поездке и почему это часто решается правильным выбором района и формата жилья.",
        "image": "telegram-3745.jpg",
        "alt": "Минусы отдыха в Абхазии",
    },
    {
        "slug": "kak-vybrat-kurort-abkhaziya-pervyy-raz",
        "iso_date": "2026-02-27",
        "card_tag": "гид",
        "title": "Едете в Абхазию впервые? Как выбрать место для отдыха",
        "excerpt": "Пицунда и Лдзаа, Гагра, Сухум и другие локации — чем отличаются море, инфраструктура и атмосфера.",
        "image": "telegram-3613.jpg",
        "alt": "Как выбрать курорт в Абхазии",
    },
    {
        "slug": "pamyatka-turistu-abkhazia",
        "iso_date": "2026-02-24",
        "card_tag": "памятка",
        "title": "Памятка туристу в Абхазию",
        "excerpt": "Документы, связь, деньги, транспорт, вывоз товаров и другие важные моменты, которые лучше проверить до поездки.",
        "image": "telegram-3573.jpg",
        "alt": "Памятка туристу в Абхазию",
    },
    {
        "slug": "znakomstvo-darya-bronirovanie-abhaziya",
        "iso_date": "2026-01-08",
        "card_tag": "о проекте",
        "title": "Давайте знакомиться: почему надёжнее бронировать отдых в Абхазии со мной",
        "excerpt": "Дарья о себе, о каталоге жилья и о том, что даёт бронирование напрямую — по тексту поста из Телеграм.",
        "image": "telegram-2572.jpg",
        "alt": "Знакомство и бронирование с Дарьей — АБХАЗБЕРЕГ",
    },
]

EMOJI_PREFIX = re.compile(
    r"^[\s#]*(?:"
    r"[\U0001F300-\U0001FAFF\U00002700-\U000027BF\U00002600-\U000026FF"
    r"❗‼✅⚠️👉💬🚫📍💡✔️🔔☀️💦⛔🙈🙋‍♀🚶‍♀🚗🚌🚾🛍📄📱💰📶📲🕓⏳🚉✈️⚡️😃🤗👍👶💊💵🛒"
    r"]+\s*)+"
)
SKIP_LINE_RE = re.compile(r"(?i)(наш сайт:|abhazbereg\.ru|по бронированию|@abhazbooking)")


def ru_date(iso_d: str) -> str:
    y, m, d = iso_d.split("-")
    months = (
        "",
        "января",
        "февраля",
        "марта",
        "апреля",
        "мая",
        "июня",
        "июля",
        "августа",
        "сентября",
        "октября",
        "ноября",
        "декабря",
    )
    return f"{int(d)} {months[int(m)]} {y}"


def clean_title_line(line: str) -> str:
    line = line.strip()
    line = EMOJI_PREFIX.sub("", line)
    line = re.sub(r"[!?.…]+$", "", line).strip()
    line = re.sub(r"\s+", " ", line)
    return line


def is_section_header(line: str) -> bool:
    raw = line.strip()
    if not raw or len(raw) > 130:
        return False
    if SKIP_LINE_RE.search(raw):
        return False
    if re.match(r"^\d+[\.\)]\s+\S", raw):
        return True
    if EMOJI_PREFIX.match(raw) and len(raw) <= 90:
        return True
    letters = [c for c in raw if c.isalpha()]
    if not letters:
        return False
    upper_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
    if upper_ratio >= 0.72 and len(raw) <= 95:
        return True
    return False


BULLET_RE = re.compile(r"^[\s•\-\*]\s*|^\d+[\.\)]\s+")


def is_bullet_line(line: str) -> bool:
    return bool(BULLET_RE.match(line.strip()))


def strip_bullet(line: str) -> str:
    line = line.strip()
    line = re.sub(r"^[\s•\-\*]\s*", "", line)
    return re.sub(r"^\d+[\.\)]\s+", "", line)


def lines_to_html_chunks(lines: list[str]) -> list[str]:
    chunks: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if is_bullet_line(line):
            items: list[str] = []
            while i < len(lines) and (is_bullet_line(lines[i]) or not lines[i].strip()):
                if lines[i].strip():
                    items.append(f"          <li>{html.escape(strip_bullet(lines[i]))}</li>")
                i += 1
            if items:
                chunks.append("        <ul>\n" + "\n".join(items) + "\n        </ul>")
            continue
        prose: list[str] = []
        while i < len(lines) and lines[i].strip() and not is_bullet_line(lines[i]):
            prose.append(lines[i].strip())
            i += 1
        if prose:
            inner = "<br />\n".join(html.escape(ln) for ln in prose)
            chunks.append(f"        <p>{inner}</p>")
    return chunks


def render_section(title: str, lines: list[str]) -> str:
    body = "\n".join(lines_to_html_chunks(lines))
    if not body:
        return (
            '        <section class="blog-section">\n'
            f"          <h2>{html.escape(title)}</h2>\n"
            "        </section>"
        )
    return (
        '        <section class="blog-section">\n'
        f"          <h2>{html.escape(title)}</h2>\n"
        f"{body}\n"
        "        </section>"
    )


def render_free_block(lines: list[str]) -> str:
    return "\n".join(lines_to_html_chunks(lines))


def telegram_text_to_sections_html(text: str) -> str:
    """Возвращает body_html с разделами."""
    text = text.replace("\r\n", "\n").strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    blocks = [b.strip() for b in text.split("\n\n") if b.strip()]

    start = 0
    if blocks:
        first_lines = [ln.strip() for ln in blocks[0].split("\n") if ln.strip()]
        if len(first_lines) == 1:
            start = 1

    body_parts: list[str] = []
    orphan_blocks: list[list[str]] = []
    saw_section = False
    pending_title: str | None = None

    def flush_pending_title() -> None:
        nonlocal pending_title
        if pending_title:
            rendered = render_section(pending_title, [])
            if rendered:
                body_parts.append(rendered)
            pending_title = None

    def flush_orphans() -> None:
        nonlocal orphan_blocks
        for orphan in orphan_blocks:
            body_parts.append(render_free_block(orphan))
        orphan_blocks = []

    for block in blocks[start:]:
        lines = [ln.strip() for ln in block.split("\n") if ln.strip() and not SKIP_LINE_RE.search(ln)]
        if not lines:
            continue
        if is_section_header(lines[0]):
            flush_orphans()
            title = clean_title_line(lines[0])
            section_body = lines[1:]
            if section_body:
                flush_pending_title()
                rendered = render_section(title, section_body)
                if rendered:
                    body_parts.append(rendered)
                pending_title = None
            else:
                flush_pending_title()
                pending_title = title
            saw_section = True
        elif pending_title:
            rendered = render_section(pending_title, lines)
            if rendered:
                body_parts.append(rendered)
            pending_title = None
        elif not saw_section:
            body_parts.append(render_free_block(lines))
        else:
            orphan_blocks.append(lines)

    flush_pending_title()
    flush_orphans()

    if not body_parts and blocks:
        for block in blocks[start:]:
            lines = [ln.strip() for ln in block.split("\n") if ln.strip() and not SKIP_LINE_RE.search(ln)]
            if lines:
                body_parts.append(render_free_block(lines))

    return "\n\n".join(body_parts)


def estimate_reading_min(text: str) -> int:
    words = len(re.findall(r"\w+", text, flags=re.UNICODE))
    return max(3, min(12, round(words / 180) or 3))


@dataclass
class BuiltArticle:
    post_id: int
    slug: str
    iso_date: str
    title: str
    title_short: str
    meta_desc: str
    lead: str
    breadcrumb: str
    eyebrow: str
    tags: tuple[str, ...]
    card_tag: str
    reading_min: int
    image_name: str
    aside_about: str


PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="ru" id="top">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{html_title}</title>
  <meta name="description" content="{meta_desc}" />
  <meta name="robots" content="index, follow, max-image-preview:large" />
  <link rel="canonical" href="https://абхазберег.рф/blog/{slug}/" />
  <meta property="og:type" content="article" />
  <meta property="og:title" content="{og_title}" />
  <meta property="og:description" content="{og_desc}" />
  <meta property="og:url" content="https://абхазберег.рф/blog/{slug}/" />
  <meta property="og:image" content="https://storage.yandexcloud.net/abhazbereg-media/media/branding/og-banner.png" />
  <link rel="preconnect" href="https://storage.yandexcloud.net" crossorigin />
  <link rel="icon" type="image/png" href="{yandex_media_base}/media/branding/favicon-48.png" />
  <link rel="stylesheet" href="../../styles.min.css?v={css_version}" />
  <script type="application/ld+json">{json_ld}</script>
</head>
<body>
  <div class="grain" aria-hidden="true"></div>
  <main class="page-shell site-concept blog-page blog-article-page">
    <div class="bg-blur bg-blur--mint" aria-hidden="true"></div>
    <div class="bg-blur bg-blur--sand" aria-hidden="true"></div>

    <header class="site-concept__topbar" role="banner">
      <a class="site-concept__brand" href="/">
        <img class="site-concept__brand-mark" src="{yandex_media_base}/media/branding/logo-emblem-160.png" width="80" height="80" alt="АБХАЗБЕРЕГ - жилье напрямую — на главную" decoding="async" />
        <span class="site-concept__brand-copy"><strong>АБХАЗБЕРЕГ - жилье напрямую</strong></span>
      </a>
      <nav class="site-concept__topnav" aria-label="Основная навигация">
        <a href="/">Главная</a>
        <a href="/blog/" aria-current="page">Полезно узнать</a>
        <a href="/#contacts">Контакты</a>
      </nav>
    </header>

    <article class="site-concept__hero-card blog-article">
      <p class="blog-breadcrumbs"><a href="/">Главная</a> / <a href="/blog/">Полезно узнать</a> / {breadcrumb_esc}</p>
      <p class="site-concept__eyebrow">{eyebrow_esc}</p>
      <h1>{h1_esc}</h1>
      <p class="blog-hero__lead">{lead_esc}</p>
      <div class="blog-tags">{tags_html}</div>

      <div class="blog-article__meta-row"><time datetime="{iso_date}">{date_ru}</time><span>Чтение: {reading_min} минут</span></div>

      <div class="blog-article__layout">
        <div class="blog-article__main">
          <div class="blog-article__content blog-article__content--sections">
        <img class="blog-article__cover-inline" src="{image_src}" srcset="{image_srcset}" sizes="{article_image_sizes}" width="480" height="640" alt="{cover_alt_esc}" loading="eager" decoding="async" />
{body_html}

        <p class="blog-source">Источник: <a href="https://t.me/abhazbereg/{post_id}" target="_blank" rel="noopener noreferrer">пост Телеграм @abhazbereg/{post_id}</a>.</p>
          </div>
        </div>
        <aside class="blog-article__aside">
          <section class="blog-note-card">
            <h2>О чём материал</h2>
            <p>{aside_esc}</p>
          </section>
          <section class="blog-note-card">
            <h2>Нужна помощь с выбором?</h2>
            <p>Можно не перебирать десятки вариантов вручную. Напишите мне — подскажу по вашему запросу.</p>
            <a class="btn-book" href="#contacts">Написать мне</a>
          </section>
        </aside>
      </div>
    </article>

  <section class="site-concept__section-block blog-article__similar" data-similar-blog hidden aria-label="Другие статьи блога">
    <div class="blog-article__similar-head">
      <p class="site-concept__eyebrow">Ещё из блога</p>
      <h2>Может быть полезно по теме</h2>
      <p class="blog-article__similar-lead"></p>
    </div>
    <div class="blog-grid blog-article__similar-grid" data-similar-blog-grid></div>
  </section>

  <section class="site-concept__section-block" id="guide">
    <div class="site-concept__section-head">
      <div>
        <p class="site-concept__eyebrow">Как бронировать</p>
        <h2>Выбирай жилье в Абхазии без утомительного поиска и без переплаты</h2>
      </div>
    </div>
    <div class="site-concept__guide-grid">
      <article class="site-concept__guide-card"><span>01</span><strong>Говорите, что вам нужно</strong><p>Курорт, даты, сколько человек, какой бюджет и что важно именно вам.</p></article>
      <article class="site-concept__guide-card site-concept__guide-card--accent"><span>02</span><strong>Я подбираю подходящие варианты</strong><p>Не всё подряд, а только то, что правда стоит смотреть под ваш запрос.</p></article>
      <article class="site-concept__guide-card site-concept__guide-card--accent"><span>03</span><strong>Обсуждаем в удобном формате</strong><p>Можно в мессенджере — спокойно задать вопросы и быстро сузить выбор.</p></article>
      <article class="site-concept__guide-card"><span>04</span><strong>Фиксируем бронь</strong><p>Когда вариант подходит, помогаю оформить бронирование и всё подтвердить.</p></article>
    </div>
    <div class="site-concept__guide-footer">
      <p class="site-concept__guide-pitch">Самостоятельный поиск жилья — это десятки сайтов и переписок, где теряется время.</p>
      <p class="site-concept__guide-pitch">Напишите, что вам нужно — я предложу подходящие варианты; если не подойдёт, продолжите искать сами.</p>
      <div class="site-concept__guide-cta">
        <div class="site-concept__guide-messenger-grid" role="group" aria-label="Написать в мессенджер">
          <a class="btn-book site-concept__guide-messenger-btn" href="https://max.ru/id741113115256_bot" rel="noopener noreferrer" target="_blank">НАПИСАТЬ В МАКС</a>
          <a class="btn-book site-concept__guide-messenger-btn" href="https://vk.cc/cQQnBn" rel="noopener noreferrer" target="_blank">НАПИСАТЬ В ВК-ЧАТ</a>
          <a class="btn-book site-concept__guide-messenger-btn" href="https://t.me/abhazbooking_online" rel="noopener noreferrer" target="_blank">НАПИСАТЬ В ТЕЛЕГРАМ</a>
          <a class="btn-book site-concept__guide-messenger-btn" href="https://wa.me/79409003340" rel="noopener noreferrer" target="_blank">НАПИСАТЬ В ВАТСАП</a>
        </div>
      </div>
    </div>
  </section>

  <section class="section site-concept__reviews" id="reviews">
    <article class="card review-shell">
      <div class="section-heading section-heading--compact"><p class="eyebrow">Отзывы гостей</p></div>
      <div aria-label="Лента отзывов" class="reviews-scroller" data-random-reviews="" data-review-count="6"></div>
    </article>
  </section>

  <section class="section site-concept__contacts" id="contacts">
    <article class="cta-block contact-shell">
      <div class="contact-shell__intro">
        <p class="eyebrow">Контакты и бронирование</p>
        <p>Проверить наличие номеров и задать вопросы можно по номеру<br /><strong class="contact-phone">+7 940 900-33-40</strong><br /><span class="contact-messengers">(max, whatsapp, telegram - только сообщения, обычный звонок не пройдёт)</span></p>
      </div>
      <div class="contact-channel-panel">
<div class="contact-channel-grid">
<a class="contact-channel-card" href="https://vk.cc/cQQnBn" rel="noopener noreferrer" target="_blank">
<span aria-hidden="true" class="contact-channel-card__icon contact-channel-card__icon--vk"></span>
<span class="contact-channel-card__copy"><strong>ВКонтакте</strong><small>Самый быстрый ответ</small></span>
<span aria-hidden="true" class="contact-channel-card__arrow">→</span>
</a>
<a class="contact-channel-card" href="https://max.ru/id741113115256_bot" rel="noopener noreferrer" target="_blank">
<span aria-hidden="true" class="contact-channel-card__icon contact-channel-card__icon--max"></span>
<span class="contact-channel-card__copy"><strong>MAX</strong><small>Только сообщения</small></span>
<span aria-hidden="true" class="contact-channel-card__arrow">→</span>
</a>
<a class="contact-channel-card" href="https://t.me/abhazbooking_online" rel="noopener noreferrer" target="_blank">
<span aria-hidden="true" class="contact-channel-card__icon contact-channel-card__icon--tg"></span>
<span class="contact-channel-card__copy"><strong>Telegram</strong><small>Только сообщения</small></span>
<span aria-hidden="true" class="contact-channel-card__arrow">→</span>
</a>
<a class="contact-channel-card" href="https://wa.me/79409003340" rel="noopener noreferrer" target="_blank">
<span aria-hidden="true" class="contact-channel-card__icon contact-channel-card__icon--whatsapp">
<svg aria-hidden="true" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M12.04 2a9.84 9.84 0 0 0-8.47 14.83L2 22l5.3-1.53A9.96 9.96 0 0 0 12.04 22C17.53 22 22 17.52 22 12S17.53 2 12.04 2Zm0 18.32a8.2 8.2 0 0 1-4.18-1.14l-.3-.18-3.15.91.93-3.07-.2-.32a8.16 8.16 0 0 1-1.26-4.38 8.18 8.18 0 1 1 8.16 8.18Zm4.5-6.12c-.25-.12-1.46-.72-1.69-.8-.23-.09-.4-.13-.56.12-.17.25-.65.8-.8.97-.14.16-.29.18-.53.06-.25-.13-1.04-.39-1.99-1.23a7.45 7.45 0 0 1-1.38-1.72c-.14-.25-.01-.38.11-.5.11-.1.25-.29.37-.43.12-.15.16-.25.25-.42.08-.16.04-.31-.02-.43-.07-.13-.56-1.36-.77-1.86-.2-.49-.41-.42-.56-.43h-.48c-.17 0-.44.06-.67.31-.23.25-.88.86-.88 2.1 0 1.23.9 2.43 1.02 2.6.13.16 1.77 2.7 4.28 3.78.6.26 1.07.41 1.43.53.6.19 1.15.16 1.58.1.48-.08 1.46-.6 1.67-1.18.2-.57.2-1.06.14-1.17-.06-.1-.23-.16-.48-.29Z"/></svg>
</span>
<span class="contact-channel-card__copy"><strong>WhatsApp</strong><small>Только сообщения</small></span>
<span aria-hidden="true" class="contact-channel-card__arrow">→</span>
</a>
</div>
</div>
</div>
    </article>
  </section>

</main>
  <script src="../../scripts.min.js?v=202608111814" defer></script>
  <a class="back-to-top" href="#top" aria-label="Наверх"><span class="back-to-top__icon" aria-hidden="true">↑</span></a>
</body>
</html>
"""


def render_article_page(art: BuiltArticle, body_html: str) -> str:
    tags_html = "".join(f"<span>{html.escape(t)}</span>" for t in art.tags)
    meta_desc = art.meta_desc[:300]
    og_desc = meta_desc[:180]
    json_ld = json.dumps(
        {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": art.title,
            "datePublished": art.iso_date,
            "dateModified": art.iso_date,
            "author": {"@type": "Person", "name": "Дарья"},
            # Яндекс требует издателя, иначе статья не попадает в быстрые
            # ответы Алисы и хуже показывается в поиске.
            "publisher": {
                "@type": "Organization",
                "name": "АБХАЗБЕРЕГ",
                "url": "https://абхазберег.рф/",
            },
            "image": [f"{YANDEX_MEDIA_BASE}/media/blog/{art.image_name}"],
            "mainEntityOfPage": f"https://абхазберег.рф/blog/{art.slug}/",
        },
        ensure_ascii=False,
    )
    image_src = f"{YANDEX_MEDIA_BASE}/media/blog/{art.image_name}"
    return PAGE_TEMPLATE.format(
        html_title=html.escape(f"{art.title_short} — АБХАЗБЕРЕГ"),
        meta_desc=html.escape(meta_desc),
        slug=art.slug,
        og_title=html.escape(art.title),
        og_desc=html.escape(og_desc),
        image_name=art.image_name,
        image_src=image_src,
        image_srcset=blog_image_srcset(image_src),
        article_image_sizes=BLOG_ARTICLE_IMAGE_SIZES,
        css_version=CSS_VERSION,
        json_ld=json_ld,
        breadcrumb_esc=html.escape(art.breadcrumb),
        eyebrow_esc=html.escape(art.eyebrow),
        h1_esc=html.escape(art.title),
        lead_esc=html.escape(art.lead),
        tags_html=tags_html,
        iso_date=art.iso_date,
        date_ru=ru_date(art.iso_date),
        reading_min=art.reading_min,
        cover_alt_esc=html.escape(art.title_short),
        body_html=body_html,
        post_id=art.post_id,
        aside_esc=html.escape(art.aside_about),
        yandex_media_base=YANDEX_MEDIA_BASE,
    )


# Тематические разделы блога: статьи группируются по card_tag, а не свалены
# в одну кучу. Порядок разделов = порядок показа; внутри — по дате (свежие выше).
BLOG_SECTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Дорога в Абхазию", ("поезд", "паром", "билеты", "транспорт", "авто", "дети")),
    ("Граница и документы", ("граница", "документы", "въезд", "животные", "долги")),
    ("Пляжи, курорты и места", ("пляжи", "курорты", "экскурсии", "источники")),
    ("Деньги, связь и правила", ("деньги", "связь", "правила", "время")),
    ("Здоровье и перед поездкой", ("здоровье", "экология", "мифы", "первый раз", "первая поездка", "о проекте")),
)
_BLOG_SECTION_OTHER = "Полезно знать"  # для тем, не попавших в карту выше


def _blog_section_for_tag(tag: str) -> str:
    key = (tag or "").strip().lower()
    for title, tags in BLOG_SECTIONS:
        if key in tags:
            return title
    return _BLOG_SECTION_OTHER


def _render_blog_card(card: dict[str, str]) -> str:
    image_src = f"{YANDEX_MEDIA_BASE}/media/blog/{html.escape(card['image'])}"
    return f"""        <article class="blog-card">
          <a class="blog-card__image-link" href="/blog/{html.escape(card['slug'])}/">
            <img src="{image_src}" srcset="{blog_image_srcset(image_src)}" sizes="{BLOG_CARD_IMAGE_SIZES}" width="480" height="330" alt="{html.escape(card['alt'])}" loading="lazy" decoding="async" />
          </a>
          <div class="blog-card__body">
            <p class="blog-card__meta"><span>{html.escape(card['card_tag'])}</span><time datetime="{html.escape(card['iso_date'])}">{html.escape(ru_date(card['iso_date']))}</time></p>
            <h3><a href="/blog/{html.escape(card['slug'])}/">{html.escape(card['title'])}</a></h3>
            <p>{html.escape(card['excerpt'])}</p>
            <a class="blog-card__cta" href="/blog/{html.escape(card['slug'])}/">Читать статью</a>
          </div>
        </article>"""


def render_blog_index(cards: list[dict[str, str]]) -> str:
    # Раскладываем карточки по разделам, сохраняя порядок BLOG_SECTIONS.
    grouped: dict[str, list[dict[str, str]]] = {}
    for card in cards:
        grouped.setdefault(_blog_section_for_tag(card.get("card_tag", "")), []).append(card)

    section_order = [title for title, _ in BLOG_SECTIONS] + [_BLOG_SECTION_OTHER]
    section_html_parts: list[str] = []
    for position, title in enumerate(section_order, start=1):
        group = grouped.get(title)
        if not group:
            continue
        anchor = str(position)
        cards_block = "\n\n".join(_render_blog_card(c) for c in group)
        section_html_parts.append(
            f"""    <section class="site-concept__section-block blog-listing" aria-labelledby="blog-sec-{anchor}">
      <div class="site-concept__section-head">
        <div>
          <p class="site-concept__eyebrow">Раздел</p>
          <h2 id="blog-sec-{anchor}">{html.escape(title)}</h2>
        </div>
      </div>
      <div class="blog-grid">
{cards_block}
      </div>
    </section>"""
        )
    sections_html = "\n\n".join(section_html_parts)
    hero_image = cards[0]["image"] if cards else "telegram-3821.jpg"

    return f"""<!DOCTYPE html>
<html lang="ru" id="top">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Полезно узнать об отдыхе в Абхазии — АБХАЗБЕРЕГ - жилье напрямую</title>
  <meta name="description" content="Практичные статьи об отдыхе в Абхазии: документы, въезд, нюансы поездки и честные разборы перед бронированием." />
  <meta name="robots" content="index, follow, max-image-preview:large" />
  <link rel="canonical" href="https://абхазберег.рф/blog/" />
  <meta property="og:type" content="website" />
  <meta property="og:title" content="Полезно узнать об отдыхе в Абхазии" />
  <meta property="og:description" content="Статьи и памятки для тех, кто планирует поездку в Абхазию впервые." />
  <meta property="og:url" content="https://абхазберег.рф/blog/" />
  <meta property="og:image" content="https://storage.yandexcloud.net/abhazbereg-media/media/branding/og-banner.png" />
  <link rel="preconnect" href="https://storage.yandexcloud.net" crossorigin />
  <link rel="icon" type="image/png" href="{YANDEX_MEDIA_BASE}/media/branding/favicon-48.png" />
  <link rel="stylesheet" href="../styles.min.css?v={CSS_VERSION}" />
</head>
<body>
  <div class="grain" aria-hidden="true"></div>
  <main class="page-shell site-concept blog-page">
    <div class="bg-blur bg-blur--mint" aria-hidden="true"></div>
    <div class="bg-blur bg-blur--sand" aria-hidden="true"></div>

    <header class="site-concept__topbar" role="banner">
      <a class="site-concept__brand" href="/">
        <img class="site-concept__brand-mark" src="{YANDEX_MEDIA_BASE}/media/branding/logo-emblem-160.png" width="80" height="80" alt="АБХАЗБЕРЕГ - жилье напрямую — на главную" decoding="async" />
        <span class="site-concept__brand-copy"><strong>АБХАЗБЕРЕГ - жилье напрямую</strong></span>
      </a>
      <nav class="site-concept__topnav" aria-label="Основная навигация">
        <a href="/">Главная</a>
        <a href="/">Подбор жилья</a>
        <a href="/blog/" aria-current="page">Полезно узнать</a>
        <a href="/#contacts">Контакты</a>
      </nav>
    </header>

    <section class="site-concept__hero-card blog-hero">
      <p class="site-concept__eyebrow">Полезно узнать</p>
      <h1>Статьи об отдыхе в Абхазии</h1>
      <div class="blog-tags" role="list" aria-label="Темы раздела «Полезно узнать»">
        <span role="listitem">документы</span>
        <span role="listitem">граница</span>
        <span role="listitem">транспорт</span>
        <span role="listitem">пляжи</span>
        <span role="listitem">первая поездка</span>
      </div>
    </section>

{sections_html}

  <section class="site-concept__section-block" id="guide">
    <div class="site-concept__section-head">
      <div><p class="site-concept__eyebrow">Как бронировать</p><h2>Выбирай жилье в Абхазии без утомительного поиска и без переплаты</h2></div>
    </div>
    <div class="site-concept__guide-grid">
      <article class="site-concept__guide-card"><span>01</span><strong>Говорите, что вам нужно</strong><p>Курорт, даты, сколько человек, какой бюджет и что важно именно вам.</p></article>
      <article class="site-concept__guide-card site-concept__guide-card--accent"><span>02</span><strong>Я подбираю подходящие варианты</strong><p>Не всё подряд, а только то, что правда стоит смотреть под ваш запрос.</p></article>
      <article class="site-concept__guide-card site-concept__guide-card--accent"><span>03</span><strong>Обсуждаем в удобном формате</strong><p>Можно в мессенджере — спокойно задать вопросы и быстро сузить выбор.</p></article>
      <article class="site-concept__guide-card"><span>04</span><strong>Фиксируем бронь</strong><p>Когда вариант подходит, помогаю оформить бронирование и всё подтвердить.</p></article>
    </div>
    <div class="site-concept__guide-footer">
      <p class="site-concept__guide-pitch">Самостоятельный поиск жилья — это десятки сайтов и переписок, где теряется время.</p>
      <p class="site-concept__guide-pitch">Напишите, что вам нужно — я предложу подходящие варианты; если не подойдёт, продолжите искать сами.</p>
      <div class="site-concept__guide-cta">
        <div class="site-concept__guide-messenger-grid" role="group" aria-label="Написать в мессенджер">
          <a class="btn-book site-concept__guide-messenger-btn" href="https://max.ru/id741113115256_bot" rel="noopener noreferrer" target="_blank">НАПИСАТЬ В МАКС</a>
          <a class="btn-book site-concept__guide-messenger-btn" href="https://vk.cc/cQQnBn" rel="noopener noreferrer" target="_blank">НАПИСАТЬ В ВК-ЧАТ</a>
          <a class="btn-book site-concept__guide-messenger-btn" href="https://t.me/abhazbooking_online" rel="noopener noreferrer" target="_blank">НАПИСАТЬ В ТЕЛЕГРАМ</a>
          <a class="btn-book site-concept__guide-messenger-btn" href="https://wa.me/79409003340" rel="noopener noreferrer" target="_blank">НАПИСАТЬ В ВАТСАП</a>
        </div>
      </div>
    </div>
  </section>

  <section class="section site-concept__reviews" id="reviews">
    <article class="card review-shell">
      <div class="section-heading section-heading--compact"><p class="eyebrow">Отзывы гостей</p></div>
      <div aria-label="Лента отзывов" class="reviews-scroller" data-random-reviews="" data-review-count="6"></div>
    </article>
  </section>

  <section class="section site-concept__contacts" id="contacts">
    <article class="cta-block contact-shell">
      <div class="contact-shell__intro">
        <p class="eyebrow">Контакты и бронирование</p>
        <p>Проверить наличие номеров и задать вопросы можно по номеру<br /><strong class="contact-phone">+7 940 900-33-40</strong><br /><span class="contact-messengers">(max, whatsapp, telegram - только сообщения, обычный звонок не пройдёт)</span></p>
      </div>
      <div class="contact-channel-panel">
<div class="contact-channel-grid">
<a class="contact-channel-card" href="https://vk.cc/cQQnBn" rel="noopener noreferrer" target="_blank">
<span aria-hidden="true" class="contact-channel-card__icon contact-channel-card__icon--vk"></span>
<span class="contact-channel-card__copy"><strong>ВКонтакте</strong><small>Самый быстрый ответ</small></span>
<span aria-hidden="true" class="contact-channel-card__arrow">→</span>
</a>
<a class="contact-channel-card" href="https://max.ru/id741113115256_bot" rel="noopener noreferrer" target="_blank">
<span aria-hidden="true" class="contact-channel-card__icon contact-channel-card__icon--max"></span>
<span class="contact-channel-card__copy"><strong>MAX</strong><small>Только сообщения</small></span>
<span aria-hidden="true" class="contact-channel-card__arrow">→</span>
</a>
<a class="contact-channel-card" href="https://t.me/abhazbooking_online" rel="noopener noreferrer" target="_blank">
<span aria-hidden="true" class="contact-channel-card__icon contact-channel-card__icon--tg"></span>
<span class="contact-channel-card__copy"><strong>Telegram</strong><small>Только сообщения</small></span>
<span aria-hidden="true" class="contact-channel-card__arrow">→</span>
</a>
<a class="contact-channel-card" href="https://wa.me/79409003340" rel="noopener noreferrer" target="_blank">
<span aria-hidden="true" class="contact-channel-card__icon contact-channel-card__icon--whatsapp">
<svg aria-hidden="true" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M12.04 2a9.84 9.84 0 0 0-8.47 14.83L2 22l5.3-1.53A9.96 9.96 0 0 0 12.04 22C17.53 22 22 17.52 22 12S17.53 2 12.04 2Zm0 18.32a8.2 8.2 0 0 1-4.18-1.14l-.3-.18-3.15.91.93-3.07-.2-.32a8.16 8.16 0 0 1-1.26-4.38 8.18 8.18 0 1 1 8.16 8.18Zm4.5-6.12c-.25-.12-1.46-.72-1.69-.8-.23-.09-.4-.13-.56.12-.17.25-.65.8-.8.97-.14.16-.29.18-.53.06-.25-.13-1.04-.39-1.99-1.23a7.45 7.45 0 0 1-1.38-1.72c-.14-.25-.01-.38.11-.5.11-.1.25-.29.37-.43.12-.15.16-.25.25-.42.08-.16.04-.31-.02-.43-.07-.13-.56-1.36-.77-1.86-.2-.49-.41-.42-.56-.43h-.48c-.17 0-.44.06-.67.31-.23.25-.88.86-.88 2.1 0 1.23.9 2.43 1.02 2.6.13.16 1.77 2.7 4.28 3.78.6.26 1.07.41 1.43.53.6.19 1.15.16 1.58.1.48-.08 1.46-.6 1.67-1.18.2-.57.2-1.06.14-1.17-.06-.1-.23-.16-.48-.29Z"/></svg>
</span>
<span class="contact-channel-card__copy"><strong>WhatsApp</strong><small>Только сообщения</small></span>
<span aria-hidden="true" class="contact-channel-card__arrow">→</span>
</a>
</div>
</div>
</div>
    </article>
  </section>

</main>
  <script src="../scripts.min.js?v=202608111814" defer></script>
  <a class="back-to-top" href="#top" aria-label="Наверх"><span class="back-to-top__icon" aria-hidden="true">↑</span></a>
</body>
</html>
"""


async def resolve_album_message(client, entity, post_id: int, msg) -> tuple[str, object]:
    raw_text = (msg.message or "").strip()
    date_msg = msg
    if raw_text:
        return raw_text, date_msg
    if not msg.grouped_id:
        return raw_text, date_msg
    siblings = await client.get_messages(entity, limit=20, min_id=post_id - 10, max_id=post_id + 10)
    group = [item for item in siblings if item and item.grouped_id == msg.grouped_id]
    for item in sorted(group, key=lambda row: row.id):
        text = (item.message or "").strip()
        if text:
            return text, item
    return raw_text, date_msg


async def download_cover_image(client, entity, post_id: int, msg, image_path: Path) -> None:
    if image_path.is_file():
        return
    if msg.photo:
        await client.download_media(msg, file=str(image_path))
        return
    if not msg.grouped_id:
        return
    siblings = await client.get_messages(entity, limit=20, min_id=post_id - 10, max_id=post_id + 10)
    for item in sorted(
        [row for row in siblings if row and row.grouped_id == msg.grouped_id],
        key=lambda row: row.id,
    ):
        if item.photo:
            await client.download_media(item, file=str(image_path))
            return


async def sync_posts(post_ids: list[int] | None = None) -> list[BuiltArticle]:
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    SOURCES_DIR.mkdir(parents=True, exist_ok=True)

    built: list[BuiltArticle] = []
    target_ids = post_ids or POST_IDS
    async with connected_telegram_client(SESSION, API_ID, API_HASH, receive_updates=False) as client:
        entity = await client.get_entity(CHANNEL)
        messages = await client.get_messages(entity, ids=target_ids)
        by_id = {m.id: m for m in messages if m}

        for post_id in target_ids:
            msg = by_id.get(post_id)
            if not msg:
                print(f"skip missing #{post_id}", file=sys.stderr)
                continue

            raw_text, date_msg = await resolve_album_message(client, entity, post_id, msg)
            if not raw_text:
                print(f"skip empty text #{post_id}", file=sys.stderr)
                continue

            (SOURCES_DIR / f"abhazbereg-{post_id}.txt").write_text(raw_text + "\n", encoding="utf-8")

            image_name = f"telegram-bereg-{post_id}.jpg"
            image_path = MEDIA_DIR / image_name
            await download_cover_image(client, entity, post_id, msg, image_path)

            meta = POST_META[post_id]
            body_html = telegram_text_to_sections_html(raw_text)
            title = str(meta.get("title") or clean_title_line(raw_text.split("\n", 1)[0]))
            lead = str(meta.get("lead") or title)

            iso_date = date_msg.date.strftime("%Y-%m-%d") if date_msg.date else "2026-01-01"
            reading_min = estimate_reading_min(raw_text)
            title_short = title if len(title) <= 72 else title[:69] + "…"
            meta_desc = str(meta.get("lead") or lead)
            if len(meta_desc) < 40:
                meta_desc = f"{title}. {lead}"

            art = BuiltArticle(
                post_id=post_id,
                slug=str(meta["slug"]),
                iso_date=iso_date,
                title=title,
                title_short=title_short,
                meta_desc=meta_desc,
                lead=lead[:220],
                breadcrumb=str(meta["breadcrumb"]),
                eyebrow=str(meta["eyebrow"]),
                tags=tuple(meta["tags"]),  # type: ignore[arg-type]
                card_tag=str(meta["card_tag"]),
                reading_min=reading_min,
                image_name=image_name,
                aside_about=lead[:180],
            )

            out_dir = BLOG_DIR / art.slug
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "index.html").write_text(render_article_page(art, body_html), encoding="utf-8")
            built.append(art)
            print(f"wrote blog/{art.slug}/index.html + media/blog/{image_name}")

    return built


def update_sitemap(slugs: list[str]) -> None:
    sitemap = ROOT / "sitemap.xml"
    if not sitemap.is_file():
        return
    text = sitemap.read_text(encoding="utf-8")
    existing = set(re.findall(r"<loc>(https://абхазберег\.рф/blog/[^<]+)</loc>", text))
    additions = []
    for slug in slugs:
        url = f"https://абхазберег.рф/blog/{slug}/"
        if url in existing:
            continue
        additions.append(f"  <url>\n    <loc>{url}</loc>\n  </url>")
    if not additions:
        return
    text = text.replace("</urlset>", "\n".join(additions) + "\n</urlset>")
    sitemap.write_text(text, encoding="utf-8")


async def main_async() -> int:
    only_ids = os.getenv("TARGET_BLOG_POST_IDS", "").strip()
    post_ids = None
    if only_ids:
        post_ids = [int(part.strip()) for part in only_ids.split(",") if part.strip()]
    built = await sync_posts(post_ids)
    if os.getenv("SKIP_BLOG_INDEX", "").strip().lower() in {"1", "true", "yes", "on"}:
        update_sitemap([art.slug for art in built])
        from build_blog_posts_manifest import main as build_blog_manifest

        build_blog_manifest()
        print(f"synced {len(built)} article(s), blog index skipped")
        return 0
    new_cards = [
        {
            "slug": art.slug,
            "iso_date": art.iso_date,
            "card_tag": art.card_tag,
            "title": art.title,
            "excerpt": art.lead,
            "image": art.image_name,
            "alt": art.title_short,
        }
        for art in built
    ]
    if post_ids:
        from build_blog_posts_manifest import build_manifest

        known_cards = {
            str(card["slug"]): {
                "slug": str(card["slug"]),
                "iso_date": str(card.get("iso_date") or ""),
                "card_tag": str(card.get("card_tag") or ""),
                "title": str(card.get("title") or ""),
                "excerpt": str(card.get("excerpt") or ""),
                "image": str(card.get("image") or ""),
                "alt": str(card.get("title") or card["slug"]),
            }
            for card in build_manifest()
        }
        for card in EXISTING_CARDS:
            known_cards.setdefault(str(card["slug"]), card)
        for card in new_cards:
            known_cards[str(card["slug"])] = card
        all_cards = list(known_cards.values())
    else:
        all_cards = new_cards + EXISTING_CARDS
    all_cards.sort(key=lambda c: c["iso_date"], reverse=True)
    (BLOG_DIR / "index.html").write_text(render_blog_index(all_cards), encoding="utf-8")
    print(f"updated blog/index.html ({len(all_cards)} cards)")
    update_sitemap([c["slug"] for c in new_cards])
    print("sitemap updated")
    from build_blog_posts_manifest import main as build_blog_manifest

    build_blog_manifest()
    return 0


def main() -> int:
    return run_async_entrypoint(main_async(), name="sync_blog_from_abhazbereg", default_timeout=1800)


if __name__ == "__main__":
    raise SystemExit(main())
