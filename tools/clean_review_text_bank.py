#!/usr/bin/env python3
"""Чистит media/reviews/review_text_bank.json и обновляет reviews-panel в HTML-страницах."""

from __future__ import annotations

import html
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.review_text_clean import clean_ocr_review_text

BANK_PATH = ROOT / 'media' / 'reviews' / 'review_text_bank.json'
PAGE_GLOBS = ('hotels/*/index.html', 'kvartira/*/index.html')


def normalize_review_slug(value: str) -> str:
    value = re.sub(r'-+', '-', (value or '').lower().strip().strip('/').replace('_', '-'))
    return re.sub(r'-\d{3,6}$', '', value)


def review_slug_match_score(source_slug: str, target_slug: str) -> int:
    if not source_slug or not target_slug:
        return 0
    if source_slug == target_slug:
        return 10_000 + len(source_slug)
    if source_slug.startswith(target_slug):
        return 5_000 + len(target_slug)
    if target_slug.startswith(source_slug):
        return 4_000 + len(source_slug)

    source_tokens = source_slug.split('-')
    target_tokens = target_slug.split('-')
    source_set = set(source_tokens)
    common = [token for token in target_tokens if token in source_set]
    if not common:
        return 0
    return round(len(common) / max(len(source_tokens), len(target_tokens)) * 1000) + len(common)


def load_review_bank() -> dict[str, list[dict[str, Any]]]:
    if not BANK_PATH.exists():
        return {}
    payload = json.loads(BANK_PATH.read_text(encoding='utf-8'))
    by_object = payload.get('by_object')
    if not isinstance(by_object, dict):
        return {}
    return {
        str(slug): reviews
        for slug, reviews in by_object.items()
        if slug and isinstance(reviews, list) and reviews
    }


def load_hidden_review_slugs() -> set[str]:
    path = ROOT / 'tools' / 'hidden_listings.json'
    if not path.is_file():
        return set()
    try:
        return set(json.loads(path.read_text(encoding='utf-8')))
    except json.JSONDecodeError:
        return set()


def reviews_for_slug(slug: str, bank: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    if slug in bank:
        return bank[slug]

    hidden = load_hidden_review_slugs()
    target = normalize_review_slug(slug)
    best_key = ''
    best_score = 0
    for candidate in bank:
        if candidate in hidden:
            continue
        score = review_slug_match_score(normalize_review_slug(candidate), target)
        if score > best_score:
            best_key = candidate
            best_score = score

    if not best_key or best_score < 1200:
        return []
    return bank.get(best_key, [])


def load_design_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        'apply_new_site_design',
        ROOT / 'tools' / 'apply_new_site_design.py',
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def reviews_panel_for_slug(design_mod: Any, slug: str, bank: dict[str, list[dict[str, Any]]]) -> str:
    object_reviews = reviews_for_slug(slug, bank)
    if object_reviews:
        reviews_html = ''
        for review in object_reviews[:2]:
            author = str(review.get('name') or 'Гость').upper()
            body = clean_ocr_review_text(str(review.get('text') or ''), ensure_sentence_end=True)
            if not body:
                continue
            reviews_html += f"""              <article class="review-card">
                <div class="review-card__top">
                  <strong>{html.escape(author)}</strong>
                  <span>Гость</span>
                </div>
                <p>{html.escape(body)}</p>
              </article>"""
        if reviews_html:
            return (
                '<section class="reviews-panel">'
                '<div class="reviews-panel__head">'
                '<div class="reviews-summary"><span>Отзывы гостей</span>'
                '</div></div>'
                f'<div class="reviews-grid">{reviews_html}</div>'
                '</section>'
            )

    spec = importlib.util.spec_from_file_location(
        'sync_abhazbooking_2026',
        ROOT / 'sync_abhazbooking_2026.py',
    )
    sync_mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(sync_mod)

    seed = sum(ord(ch) for ch in slug)
    wrapped = f'<section>{sync_mod.render_reviews(seed)}</section>'
    cards = design_mod.extract_reviews(wrapped)
    if not cards:
        return ''
    reviews_html = ''.join(
        f"""              <article class="review-card">
                <div class="review-card__top">
                  <strong>{html.escape(author)}</strong>
                  <span>{html.escape(kind)}</span>
                </div>
                <p>{html.escape(body)}</p>
              </article>"""
        for author, kind, body in cards[:2]
    )
    return (
        '<section class="reviews-panel">'
        '<div class="reviews-panel__head">'
        '<div class="reviews-summary"><span>Отзывы гостей</span>'
        '</div></div>'
        f'<div class="reviews-grid">{reviews_html}</div>'
        '</section>'
    )


def clean_bank_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
    changed = 0

    def clean_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        nonlocal changed
        cleaned_entries: list[dict[str, Any]] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            original = str(entry.get('text') or '')
            cleaned = clean_ocr_review_text(original, ensure_sentence_end=False)
            if cleaned and cleaned != original:
                changed += 1
            if not cleaned:
                continue
            updated = dict(entry)
            updated['text'] = cleaned
            cleaned_entries.append(updated)
        return cleaned_entries

    global_entries = clean_entries(payload.get('global') or [])
    by_object: dict[str, list[dict[str, Any]]] = {}
    for slug, entries in (payload.get('by_object') or {}).items():
        if not slug or not isinstance(entries, list):
            continue
        cleaned = clean_entries(entries)
        if cleaned:
            by_object[str(slug)] = cleaned

    female_count = sum(1 for review in global_entries if review.get('gender') == 'female')
    male_count = sum(1 for review in global_entries if review.get('gender') == 'male')

    payload['global'] = global_entries
    payload['by_object'] = by_object
    payload['stats'] = {
        'total': len(global_entries),
        'female': female_count,
        'male': male_count,
        'female_ratio': round((female_count / len(global_entries)) if global_entries else 0, 4),
        'male_ratio': round((male_count / len(global_entries)) if global_entries else 0, 4),
        'objects_with_reviews': len(by_object),
    }
    return payload, changed


def extract_slug_from_page(path: Path) -> str:
    return path.parent.name


def replace_reviews_panel(page_html: str, panel_html: str) -> str:
    if not panel_html:
        return page_html
    pattern = re.compile(
        r'<section class="reviews-panel">.*?</section>',
        re.DOTALL,
    )
    if not pattern.search(page_html):
        return page_html
    return pattern.sub(panel_html, page_html, count=1)


def refresh_page_panels(design_mod: Any, bank: dict[str, list[dict[str, Any]]]) -> tuple[int, int]:
    updated_pages = 0
    skipped_pages = 0

    for pattern in PAGE_GLOBS:
        for page_path in sorted(ROOT.glob(pattern)):
            slug = extract_slug_from_page(page_path)
            panel_html = reviews_panel_for_slug(design_mod, slug, bank)
            original = page_path.read_text(encoding='utf-8')
            next_html = replace_reviews_panel(original, panel_html)
            if next_html == original:
                skipped_pages += 1
                continue
            page_path.write_text(next_html, encoding='utf-8')
            updated_pages += 1

    return updated_pages, skipped_pages


def main() -> None:
    if not BANK_PATH.exists():
        raise SystemExit(f'Не найден файл: {BANK_PATH}')

    payload = json.loads(BANK_PATH.read_text(encoding='utf-8'))
    cleaned_payload, changed_texts = clean_bank_payload(payload)
    BANK_PATH.write_text(
        json.dumps(cleaned_payload, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
    print(f'Обновлено текстов в базе: {changed_texts}')
    print(f'Статистика: {cleaned_payload["stats"]}')

    bank = load_review_bank()
    design_mod = load_design_module()
    updated_pages, skipped_pages = refresh_page_panels(design_mod, bank)
    print(f'Обновлено HTML-страниц: {updated_pages}')
    print(f'Без изменений: {skipped_pages}')


if __name__ == '__main__':
    main()
