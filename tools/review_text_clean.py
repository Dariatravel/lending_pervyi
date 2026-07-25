#!/usr/bin/env python3
"""Очистка OCR-текста отзывов от артефактов интерфейса Telegram и агрегаторов."""

from __future__ import annotations

import re

# Слова, с которых обычно начинается сам отзыв, а не имя автора в шапке скрина.
_REVIEW_START_WORDS = (
    'отдыхали',
    'отель',
    'отели',
    'мы',
    'в ',
    'на ',
    'прекрас',
    'удобн',
    'чист',
    'понрав',
    'рекоменд',
    'ехали',
    'приехали',
    'бронировали',
    'остановились',
    'жили',
    'вернусь',
    'вернемся',
    'планируем',
    'искали',
    'выбрали',
    'побывали',
    'провели',
    'остались',
    'получили',
    'всё',
    'все ',
    'есть ',
    'очень ',
    'шикар',
    'замечат',
    'отличн',
    'хорош',
    'уютн',
    'гостеприим',
    'территор',
    'номер',
    'море',
    'пляж',
    'бассейн',
    'персонал',
    'хозяйк',
    'администрац',
    'расположен',
    'рядом',
    'до моря',
    '1 ',
    '2 ',
    '3 ',
    '4 ',
    '5 ',
    '6 ',
    '7 ',
    '8 ',
    '9 ',
    '10 ',
    '11 ',
    '12 ',
)

_GREETING_AFTER_NAME = re.compile(
    r'^(?:спасибо|добрый|даша|дарья|здравствуйте|хочу|ну\s+вот|нам\s|'
    r'большое\s+спасибо|огромное\s+спасибо)',
    re.I,
)

_CYR_NAME = r'[А-ЯЁ][а-яё]+'
_LATIN_NAME = r'[A-Z][A-Za-z]{1,}(?:-[A-Z][A-Za-z]{1,})?'
_NAME_TOKEN = rf'(?:{_CYR_NAME}|{_LATIN_NAME})'
_GREETING_LOOKAHEAD = (
    r'(?i:спасибо|добрый|даша|дарья|здравствуйте|хочу|ну\s+вот|нам\s|'
    r'большое\s+спасибо|огромное\s+спасибо)'
)
_NAME_PREFIX = re.compile(
    rf'^\s*(?:ОБ\s+)?(?:{_NAME_TOKEN}(?:\s+{_NAME_TOKEN}){{0,2}})\s+(?={_GREETING_LOOKAHEAD})',
)

_SOCIAL_SPAM = re.compile(
    r'(?:Abhazize|Alkhaziae|ОТЕЛИ\|ЖИЛЬЕ\|СНЯТ[ЫЬ]ОТ|G Google|захарод в сервисе)',
    re.I,
)

_OWNER_REPLY = re.compile(
    r'(?:^|[.!?…]\s+)(?:[А-ЯЁ][а-яё]+),?\s*здравствуйте!\s*Большое спасибо за отзыв!?',
    re.I,
)

_YMONTH = (
    r'(?:январ|феврал|март|апрел|ма[йя]|июн|июл|август|сентябр|октябр|ноябр|декабр)\w*'
)
_PREFIX_PATTERNS = [
    re.compile(r'^\s*[+»«"\']+\s*', re.I),
    re.compile(r'^\s*\*{2,}\s*\d?\s*'),                   # звёзды-рейтинг «*****», «****1»
    re.compile(r'^\s*\*\s+(?=\d)', re.I),                 # одиночная «*» перед датой
    # имя автора (1–3 слова) перед датой-словом: «Иван Драгов 17 июня»
    re.compile(rf'^\s*[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+){{1,2}}\s+\*?\s*\d{{1,2}}\s+{_YMONTH}(?:\s+20\d{{2}})?\s*', re.I),
    # дата-слово с годом: «17 июня 2024»
    re.compile(rf'^\s*\d{{1,2}}\s+{_YMONTH}\s+20\d{{2}}\s*', re.I),
    re.compile(r'^\s*20\d{2}\s+(?=[А-ЯЁ])'),              # осиротевший год «2024 Шикарное»
    re.compile(r'^\s*\d{1,2}\s*(?:превосходно|отлично|хорошо|супер)\s*', re.I),
    re.compile(r'^\s*\d{1,2}\s+[а-яё]+\s*', re.I),
    re.compile(r'^\s*\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\s*', re.I),
    re.compile(
        r'^\s*[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+){0,2}\s+\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\s*',
        re.I,
    ),
    re.compile(
        r'^\s*[А-ЯЁ][а-яё]+[:,]?\s*добрый\s+(?:день|вечер|утро),?\s*дарья!?\.?\s*',
        re.I,
    ),
    re.compile(r'^\s*добрый\s+(?:день|вечер|утро),?\s*дарья!?\.?\s*', re.I),
    re.compile(r'^\s*[А-ЯA-Z]\s+(?=[А-ЯЁ][а-яё]+)', re.I),
    re.compile(r'^\s*ОБ\s+\d{1,2}\s+[а-яё]+\s*', re.I),
]

_LEADING_THANKS = re.compile(
    r'^\s*(?:'
    r'спасибо\s+большое\s*!?\s*'
    r'|большое\s+спасибо\s*!?\s*'
    r'|огромное\s+спасибо\s*!?\s*'
    r'|даша,?\s+спасибо\s+вам\s+огромное\s*!+\s*'
    r'|дарья,?\s+'
    r'|добрый\s+(?:день|вечер|утро)[.!?]?\s*'
    r'(?:дарья[!]?[,]?\s*)?'
    r')',
    re.I,
)

_LEADING_PUNCT = re.compile(r'^\s*[.,;:!?…]+\s*')

# Обвязка агрегаторов (Яндекс.Путешествия и похожие площадки).
_AGG_REVIEW_PREFIX = re.compile(r'^\s*Отзыв:\s*[^()]{0,60}\([^)]{0,40}\)\s*[-–—]\s*', re.I)
_AGG_DATE_REPLY_TAIL = re.compile(
    r'\s*\d{1,2}\s+[а-яё]{3,8}\.?\s+20\d{2}\s*(?:г\.?)?\s*(?:в\s+)?Ответить\b.*$',
    re.I | re.S,
)
_AGG_REPLY_TAIL = re.compile(r'\s*Ответить\s*(?:Поделиться)?\s*[O0О]?\s*\d*\s*\.?\s*$', re.I)
_NO_CONS_VALUE = r'(?:нет|не было|у нас их не было|минусов нет|их нет)'
_AGG_LABELS = [
    (re.compile(rf'(?<=[.!?…)»])\s*Недостатки:\s*{_NO_CONS_VALUE}[!.\s]*', re.I), ' '),
    (re.compile(rf'\s*Недостатки:\s*{_NO_CONS_VALUE}[!.\s]*', re.I), '. '),
    (re.compile(r'(?<=[.!?…)»])\s*Достоинства:\s*', re.I), ' '),
    (re.compile(r'\s*Достоинства:\s*', re.I), '. '),
]
# Латинское имя автора (и опц. дата) в начале скрина: «Gala Kolchina Бронировала…»
_LATIN_AUTHOR_PREFIX = re.compile(
    r'^\s*(?:[A-Z][A-Za-z]+\s+[A-Z][A-Za-z]+\s+(?:\d{1,2}[./]\d{1,2}[./]\d{2,4}\s*)?'
    r'|[A-Z][A-Za-z]+\s+\d{1,2}[./]\d{1,2}[./]\d{2,4}\s*)(?:в\s+)?(?=[А-ЯЁ«])'
)
# Кириллическое ФИО автора перед названием в кавычках: «Рания Курбатова «Вилла Любовь»…»
_CYR_AUTHOR_BEFORE_QUOTE = re.compile(r'^\s*[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+\s+(?=«)')


# Рекламная шапка канала в начале скрина: «Абхазия | ОТЕЛИ | ЖИЛЬЕ … ОСТАВЬ СВОЙ ОТЗЫВ»
_AD_HEADER_PREFIXES = [
    re.compile(r'^.{0,160}?ОСТАВЬ\s+СВОЙ\s+ОТ?ЗЫВ\W*', re.I | re.S),
    re.compile(r'^\s*(?:Д\s+)?Все\s+любят\s+читать\s+отзывы\s+от\s*[.…]*\s*', re.I),
    re.compile(r'^\s*[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+\s*\|\s*[А-ЯЁ][а-яё]+\s+[а-яё]+\s+(?=[А-ЯЁ])'),
]


# Яндекс.Карты: бейдж эксперта и элементы интерфейса на скринах отзывов.
_YANDEX_BADGE = re.compile(r'\bзнаток\s+города\s*(?:\d+\s*уровн\w*)?\s*', re.I)
# Только ОДНОЗНАЧНЫЕ элементы интерфейса Яндекс.Карт (в живых отзывах не встречаются).
# «Расположение», «Особенности», «N отзывов» НЕ трогаем — бывают в тексте отзыва.
_YANDEX_UI_TOKENS = re.compile(
    r'\b(?:At\s+the\s+sea|Обзор\s+Фото(?:\s+\d+)*|По\s+умолчани\w*)\b',
    re.I,
)
# Скрин целиком — интерфейс Яндекс.Карт (не отзыв): 2+ однозначных маркеров.
_YANDEX_UI_MARKERS = re.compile(
    r'обзор\s+фото|по\s+умолчани|at\s+the\s+sea|aquafon',
    re.I,
)


def _is_yandex_ui_dump(text: str) -> bool:
    return len(_YANDEX_UI_MARKERS.findall(text)) >= 2


def _strip_aggregator_chrome(text: str) -> str:
    for pattern in _AD_HEADER_PREFIXES:
        text = pattern.sub('', text)
    # Бейдж «Знаток города [N уровня]» и элементы интерфейса Яндекс.Карт.
    text = _YANDEX_BADGE.sub(' ', text)
    text = _YANDEX_UI_TOKENS.sub(' ', text)
    text = _AGG_REVIEW_PREFIX.sub('', text)
    text = _AGG_DATE_REPLY_TAIL.sub('', text)
    text = _AGG_REPLY_TAIL.sub('', text)
    for pattern, repl in _AGG_LABELS:
        text = pattern.sub(repl, text)
    text = _LATIN_AUTHOR_PREFIX.sub('', text)
    text = _CYR_AUTHOR_BEFORE_QUOTE.sub('', text)
    # «Название» -это … → Название -это … (кавычки-обёртка заголовка площадки)
    text = re.sub(r'^\s*«([^»]{1,60})»\s*(?=[-–—])', r'\1 ', text)
    return text.strip()


def _looks_like_review_start(text: str) -> bool:
    lower = text.lower()
    return any(lower.startswith(marker) for marker in _REVIEW_START_WORDS)


def _strip_leading_name_prefix(text: str) -> str:
    while True:
        match = _NAME_PREFIX.match(text)
        if not match:
            break
        remainder = text[match.end() :].lstrip()
        if not remainder or _looks_like_review_start(remainder):
            break
        text = remainder
    return text.strip()


def _truncate_social_noise(text: str) -> str:
    parts = _SOCIAL_SPAM.split(text, maxsplit=1)
    return parts[0].strip()


def _truncate_owner_reply(text: str) -> str:
    match = _OWNER_REPLY.search(text)
    if not match:
        return text
    return text[: match.start()].strip()


def _dedupe_repeated_lead(text: str) -> str:
    words = text.split()
    if len(words) < 12:
        return text
    lead = ' '.join(words[:8]).lower()
    second = text.lower().find(lead, len(lead))
    if second > 40:
        return text[:second].strip()
    return text


def clean_ocr_review_text(value: str, *, ensure_sentence_end: bool = True) -> str:
    text = re.sub(r'\s+', ' ', str(value or '')).strip()
    if not text:
        return ''

    # Скрин целиком — интерфейс Яндекс.Карт (не отзыв): выбрасываем.
    if _is_yandex_ui_dump(text):
        return ''

    text = _strip_aggregator_chrome(text)

    text = re.sub(r'(?:раскрыть\s+детали|что\s+было\s+хорошо|подписаться)', ' ', text, flags=re.I)
    text = re.sub(r'оценка\s*wi[\s-]*fi[^.?!]*[.?!]?', ' ', text, flags=re.I)
    text = re.sub(r'\b\d+\s*уровня\b', ' ', text, flags=re.I)

    changed = True
    while changed:
        changed = False
        for pattern in _PREFIX_PATTERNS:
            cleaned = pattern.sub('', text).strip()
            if cleaned != text:
                text = cleaned
                changed = True

    text = _strip_leading_name_prefix(text)

    changed = True
    while changed:
        changed = False
        cleaned = _LEADING_THANKS.sub('', text).strip()
        if cleaned != text:
            text = cleaned
            changed = True

    text = _truncate_social_noise(text)
    text = _truncate_owner_reply(text)
    text = _dedupe_repeated_lead(text)

    changed = True
    while changed:
        changed = False
        cleaned = _LEADING_PUNCT.sub('', text).strip()
        if cleaned != text:
            text = cleaned
            changed = True

    text = re.sub(r'\s+', ' ', text).strip()

    if not text:
        return ''
    if ensure_sentence_end and not re.search(r'[.!?…]$', text):
        text = f'{text}.'
    return text
