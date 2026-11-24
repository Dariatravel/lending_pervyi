"""Отличать служебные посты от карточек с общими ссылками в конце."""
from __future__ import annotations
import html
import re

SERVICE_MARKERS = (
    'кто я и почему выгодно бронировать',
    'отзывы гостей',
    'друзья, в этой группе собраны варианты',
    'здесь вы найдёте квартиры',
    'здесь вы найдете квартиры',
    'общение в группе',
)


def is_service_text(text: str) -> bool:
    raw = html.unescape(text or '').strip().casefold()
    sample = re.sub(r'\s+', ' ', raw)
    if not any(marker in sample for marker in SERVICE_MARKERS):
        return False
    heading = next((line.strip() for line in raw.splitlines() if line.strip()), '')
    heading = re.sub(r'\s+', ' ', heading)
    if any(marker in heading for marker in SERVICE_MARKERS):
        return True
    # В карточках есть адрес и характеристики жилья. Общие ссылки «Кто я» /
    # «Отзывы гостей» после описания не превращают их в служебное сообщение.
    if '📍' in sample and any(marker in sample for marker in ('👥', '🏖', '🏝', '✔', 'цены', 'стоимость')):
        return False
    return True
