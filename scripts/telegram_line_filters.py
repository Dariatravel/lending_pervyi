"""Очистка телеграм-хвостов в текстах постов перед публикацией на сайте.

В Telegram слово «тут»/«здесь» — ссылка на обзор, а стрелки 👇 указывают на
медиа под сообщением. На сайте ссылка и контекст теряются, и строка выглядит
мусором: «ОБЗОРЫ НОМЕРОВ ТУТ», «Фото в комментариях», «Разбираемся👇».
(Жалоба Дарьи 17.09.2026 по «Берегу Святой Софии» и «Киараз Резорт».)

Три действия:
  * строку-ссылку убираем целиком  — is_link_stub_line
  * хвост в полезной строке обрезаем — clean_line_for_site
  * указатели-стрелки вычищаем, текст оставляем

Осторожно со словами, внутри которых есть «тут»: «батут», «институт»,
«Аватут» — поэтому везде границы слова (\b).
"""
from __future__ import annotations

import re

# Стрелки-указатели из Telegram (вниз/вверх/вправо) вместе с вариационными
# селекторами эмодзи.
POINTER_EMOJI = re.compile(r"[\U0001F447\U0001F446\U0001F449\U0001F448⬇⬆➡]️?")

_MEDIA_WORD = r"(?:фото|видео|обзор\w*|тур\b|виртуальн\w+ тур|прайс\w*|отзыв\w*)"

# Вся строка — отсылка к ссылке: «ОБЗОРЫ НОМЕРОВ ТУТ», «ПОДРОБНЕЕ ФОТО ЗДЕСЬ».
LINK_STUB_LINE = re.compile(
    rf"^[^.!?\n]{{0,70}}\b{_MEDIA_WORD}[^.!?\n]{{0,45}}\b(?:тут|здесь|по ссылке)\b\s*[.!?]*$",
    re.IGNORECASE,
)

# Хвост в конце полезной строки: «…диван двухместный. Обзор номера тут».
LINK_STUB_TAIL = re.compile(
    rf"\s*[.;]?\s*[^.!?\n]{{0,45}}\b{_MEDIA_WORD}[^.!?\n]{{0,45}}\b(?:тут|здесь|по ссылке)\b\s*[.!?]*$",
    re.IGNORECASE,
)

# Отсылки к комментариям поста: на сайте комментариев нет.
COMMENTS_LINE = re.compile(
    r"\b(?:коммент\w+)\b", re.IGNORECASE
)
COMMENTS_CALL = re.compile(
    r"\b(?:пишите|напишите|расскажите|спрашивайте|контакты|фото|видео|подборк\w*|смотрите)\b",
    re.IGNORECASE,
)
COMMENTS_TAIL = re.compile(
    r"\s*[.;,]?\s*[^.!?\n]{0,50}\bв\s+коммент\w+\b[^.!?\n]{0,20}[.!?]*$", re.IGNORECASE
)


def strip_pointer_emoji(line: str) -> str:
    """Убирает стрелки-указатели, оставляя текст."""
    text = re.sub(r"\s+", " ", POINTER_EMOJI.sub("", line or ""))
    # После удаления значка не должно оставаться «в медиа ):» и «текст ,».
    text = re.sub(r"\s+([)\]»,.;:!?])", r"\1", text)
    text = re.sub(r"([(\[«])\s+", r"\1", text)
    return text.strip()


def is_link_stub_line(line: str) -> bool:
    """Строка целиком бессмысленна без телеграм-ссылки."""
    text = strip_pointer_emoji(line).strip(" •—-–")
    if not text:
        return False
    if LINK_STUB_LINE.match(text):
        return True
    if COMMENTS_LINE.search(text) and COMMENTS_CALL.search(text):
        # «Фото в комментариях», «напишите в комментариях…» — целиком лишнее.
        return True
    return False


def clean_line_for_site(line: str) -> str:
    """Возвращает строку для сайта; пустая строка — строку публиковать не нужно.

    Правило узкое: трогаем ТОЛЬКО телеграм-хвосты. Маркеры списков, запятые,
    переносы и прочее оформление автора остаются как есть — это его текст.
    """
    if line is None:
        return ""
    text = str(line)
    if not text.strip():
        return ""

    # 1. Указатели-стрелки: убираем значок и следы от него.
    if POINTER_EMOJI.search(text):
        text = strip_pointer_emoji(text)
        if not text:
            return ""

    # 2. Строка целиком бессмысленна без телеграм-ссылки.
    if is_link_stub_line(text):
        return ""

    # 3. Хвост в конце полезной строки — обрезаем только хвост.
    for pattern in (LINK_STUB_TAIL, COMMENTS_TAIL):
        trimmed = pattern.sub("", text)
        if trimmed.strip() and trimmed != text:
            text = trimmed.rstrip(" ,;")

    if not re.search(r"[A-Za-zА-Яа-яЁё0-9]", text):
        return ""
    return text


def clean_lines_for_site(lines) -> list[str]:
    cleaned = []
    for line in lines or []:
        value = clean_line_for_site(line)
        if value:
            cleaned.append(value)
    return cleaned
