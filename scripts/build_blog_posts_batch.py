#!/usr/bin/env python3
"""Сборка статей раздела «Полезно узнать» из текстов Telegram (scripts/blog_telegram_sources/<id>.txt)."""

from __future__ import annotations

import html
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSET_VERSION = '202607102046'
YANDEX_MEDIA_BASE = 'https://storage.yandexcloud.net/abhazbereg-media/media'


def telegram_chunks_to_ps(raw: str) -> str:
    raw = raw.strip()
    parts: list[str] = []
    for chunk in raw.split('\n\n'):
        chunk = chunk.strip()
        if not chunk:
            continue
        inner = '<br />\n'.join(html.escape(line) for line in chunk.split('\n'))
        parts.append(f'        <p>{inner}</p>')
    return '\n\n'.join(parts)


def ru_date(iso_d: str) -> str:
    y, m, d = iso_d.split('-')
    months = (
        '', 'января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
        'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря',
    )
    return f'{int(d)} {months[int(m)]} {y}'


ARTICLES = [
    {
        'id': 2572,
        'slug': 'znakomstvo-darya-bronirovanie-abhaziya',
        'iso_date': '2026-01-08',
        'title': 'Давайте знакомиться: почему надёжнее бронировать отдых в Абхазии со мной',
        'title_short': 'Знакомство и бронирование с Дарьей',
        'breadcrumb': 'О проекте',
        'eyebrow': 'О проекте',
        'lead': 'Дарья рассказывает, как устроен каталог АБХАЗБЕРЕГ и в чём разница между личным подбором и агрегатором.',
        'tags': ('о проекте', 'бронирование', 'каталог'),
        'meta_desc': 'Дарья об АБХАЗБЕРЕГ: личная проверка отелей, фиксированные цены, сопровождение до и во время поездки и честный подбор жилья в Абхазии.',
        'aside_about': 'Если хотите понять логику каталога до того, как писать в мессенджер — этот текст как раз про это.',
        'reading_min': 7,
        'src': ROOT / 'scripts/blog_telegram_sources/2572.txt',
    },
    {
        'id': 3821,
        'slug': 'mobilnaya-svyaz-i-internet-abkhaziya',
        'iso_date': '2026-03-24',
        'title': 'Что важно знать про связь в Абхазии',
        'title_short': 'Связь и интернет в Абхазии',
        'breadcrumb': 'Связь в Абхазии',
        'eyebrow': 'Практика',
        'lead': 'Роуминг российских SIM, местные операторы, eSIM, Wi‑Fi и что сделать сразу после границы.',
        'tags': ('связь', 'интернет', 'первая поездка'),
        'meta_desc': 'Мобильная связь и интернет в Абхазии: роуминг, A-Mobile и Аквафон, тарифы, eSIM и советы туристам.',
        'aside_about': 'Как не потратить лишнее на роуминге и где ловит местная сеть.',
        'reading_min': 6,
        'src': ROOT / 'scripts/blog_telegram_sources/3821.txt',
    },
    {
        'id': 3758,
        'slug': 'pravila-poezdki-s-detmi-abkhaziya-2026',
        'iso_date': '2026-03-15',
        'title': 'Важные правила поездки в Абхазию с детьми в 2026 году',
        'title_short': 'Поездка с детьми: документы в 2026',
        'breadcrumb': 'Поездка с детьми',
        'eyebrow': 'Документы',
        'lead': 'Загранпаспорт, билеты до городов Абхазии, сопровождение и нотариальное согласие — по шагам.',
        'tags': ('дети', 'документы', 'граница'),
        'meta_desc': 'Правила въезда в Абхазию с детьми в 2026 году: загранпаспорт, билеты, сопровождение и запреты.',
        'aside_about': 'Проверьте документы заранее, чтобы не зависнуть на КПП.',
        'reading_min': 7,
        'src': ROOT / 'scripts/blog_telegram_sources/3758.txt',
    },
    {
        'id': 3613,
        'slug': 'kak-vybrat-kurort-abkhaziya-pervyy-raz',
        'iso_date': '2026-02-27',
        'title': 'Едете в Абхазию впервые? Как выбрать место для отдыха',
        'title_short': 'Как выбрать курорт в Абхазии',
        'breadcrumb': 'Выбор курорта',
        'eyebrow': 'Первый раз',
        'lead': 'Пицунда и Лдзаа, Гагра, Сухум, Алахадзы, Новый Афон, Гудаута и Цандрипш — чем отличаются.',
        'tags': ('курорты', 'первый раз', 'гид'),
        'meta_desc': 'Краткий гид по курортам Абхазии для первой поездки: море, инфраструктура и атмосфера.',
        'aside_about': 'Сравните форматы отдыха и выберите локацию под свой темп.',
        'reading_min': 8,
        'src': ROOT / 'scripts/blog_telegram_sources/3613.txt',
    },
]

PAGE_TEMPLATE = '''<!DOCTYPE html>
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
  <meta property="og:image" content="https://storage.yandexcloud.net/abhazbereg-media/media/branding/site-cover.jpg" />
  <link rel="preconnect" href="https://storage.yandexcloud.net" crossorigin />
  <link rel="icon" type="image/png" href="{yandex_media_base}/branding/favicon-48.png" />
  <link rel="stylesheet" href="../../styles.min.css?v={asset_version}" />
  <script type="application/ld+json">{json_ld}</script>
</head>
<body>
  <div class="grain" aria-hidden="true"></div>
  <main class="page-shell site-concept blog-page blog-article-page">
    <div class="bg-blur bg-blur--mint" aria-hidden="true"></div>
    <div class="bg-blur bg-blur--sand" aria-hidden="true"></div>

    <header class="site-concept__topbar" role="banner">
      <a class="site-concept__brand" href="/">
        <img class="site-concept__brand-mark" src="{yandex_media_base}/branding/logo-emblem.png" width="80" height="80" alt="АБХАЗБЕРЕГ - жилье напрямую — на главную" decoding="async" />
        <span class="site-concept__brand-copy"><strong>АБХАЗБЕРЕГ - жилье напрямую</strong></span>
      </a>
      <nav class="site-concept__topnav" aria-label="Основная навигация">
        <a href="/">Главная</a>
        <a href="/blog/">Полезно узнать</a>
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
          <div class="blog-article__content blog-article__content--telegram">
        <img class="blog-article__cover-inline" src="{blog_image_url}" alt="{cover_alt_esc}" loading="eager" />
{body_ps}

        <p class="blog-source">Источник: <a href="https://t.me/abhazbooking/{tid}" target="_blank" rel="noopener noreferrer">пост Телеграм @abhazbooking/{tid}</a>.</p>
          </div>
        </div>
        <aside class="blog-article__aside">
          <section class="blog-note-card">
            <h2>О чем материал</h2>
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

  <section class="site-concept__section-block" id="guide">
    <div class="site-concept__section-head">
      <div>
        <p class="site-concept__eyebrow">Как бронировать</p>
        <h2>Выбирай жилье в Абхазии без утомительного поиска и без переплаты</h2>
      </div>
    </div>

    <div class="site-concept__guide-grid">
      <article class="site-concept__guide-card">
        <span>01</span>
        <strong>Говорите, что вам нужно</strong>
        <p>Курорт, даты, сколько человек, какой бюджет и что важно именно вам.</p>
      </article>
      <article class="site-concept__guide-card site-concept__guide-card--accent">
        <span>02</span>
        <strong>Я подбираю подходящие варианты</strong>
        <p>Не всё подряд, а только то, что правда стоит смотреть под ваш запрос.</p>
      </article>
      <article class="site-concept__guide-card site-concept__guide-card--accent">
        <span>03</span>
        <strong>Обсуждаем в удобном формате</strong>
        <p>Можно в мессенджере — спокойно задать вопросы и быстро сузить выбор.</p>
      </article>
      <article class="site-concept__guide-card">
        <span>04</span>
        <strong>Фиксируем бронь</strong>
        <p>Когда вариант подходит, помогаю оформить бронирование и всё подтвердить.</p>
      </article>
    </div>

    <div class="site-concept__guide-footer">
      <p class="site-concept__guide-pitch">Самостоятельный поиск жилья — это десятки сайтов и переписок, где теряется время.</p>
      <p class="site-concept__guide-pitch">Напишите, что вам нужно — я предложу подходящие варианты; если не подойдёт, продолжите искать сами.</p>
      <div class="site-concept__guide-cta">
        <div class="site-concept__guide-messenger-grid" role="group" aria-label="Написать в мессенджер">
          <a class="btn-book site-concept__guide-messenger-btn" href="https://max.ru/abhazbereg" rel="noopener noreferrer" target="_blank">НАПИСАТЬ В МАКС</a>
          <a class="btn-book site-concept__guide-messenger-btn" href="https://vk.cc/cQQnBn" rel="noopener noreferrer" target="_blank">НАПИСАТЬ В ВК-ЧАТ</a>
          <a class="btn-book site-concept__guide-messenger-btn" href="https://t.me/abhazbooking_online" rel="noopener noreferrer" target="_blank">НАПИСАТЬ В ТЕЛЕГРАМ</a>
          <a class="btn-book site-concept__guide-messenger-btn" href="https://wa.me/79409003340" rel="noopener noreferrer" target="_blank">НАПИСАТЬ В ВАТСАП</a>
        </div>
      </div>
    </div>
  </section>

  <section class="section site-concept__reviews" id="reviews">
    <article class="card review-shell">
      <div class="section-heading section-heading--compact">
        <p class="eyebrow">Отзывы гостей</p>
      </div>
      <div aria-label="Лента отзывов" class="reviews-scroller" data-random-reviews="" data-review-count="6"></div>
    </article>
  </section>

  <section class="section site-concept__contacts" id="contacts">
    <article class="cta-block contact-shell">
      <div class="contact-shell__intro">
        <p class="eyebrow">Контакты и бронирование</p>
        <p>
          Проверить наличие номеров и задать вопросы можно по номеру<br />
          <strong class="contact-phone">+7 940 900-33-40</strong><br />
          <span class="contact-messengers">(Ватсап, Телеграм, Макс, ВК-чат)</span>
        </p>
        <p class="note">Только сообщения, обычный звонок не пройдёт.</p>
        <p class="note">Прежде чем написать в МАКС, добавьте номер в контакты (иначе макс не даст ответить на входящее сообщение). Обращайтесь!</p>
      </div>
      <div class="contact-buttons">
        <a class="btn-book" href="https://max.ru/abhazbereg" rel="noopener noreferrer" target="_blank">НАПИСАТЬ В МАКС</a>
        <a class="btn-book" href="https://vk.cc/cQQnBn" rel="noopener noreferrer" target="_blank">НАПИСАТЬ В ВК-ЧАТ</a>
        <a class="btn-book" href="https://t.me/abhazbooking_online" rel="noopener noreferrer" target="_blank">НАПИСАТЬ В ТЕЛЕГРАМ</a>
        <a class="btn-book" href="https://wa.me/79409003340" rel="noopener noreferrer" target="_blank">НАПИСАТЬ В ВАТСАП</a>
      </div>
    </article>
  </section>

</main>
  <script src="../../scripts.min.js?v={asset_version}" defer></script>
  <a class="back-to-top" href="#top" aria-label="Наверх"><span class="back-to-top__icon" aria-hidden="true">↑</span></a>
</body>
</html>
'''


def main() -> None:
    import json as json_lib

    for art in ARTICLES:
        raw = Path(art['src']).read_text(encoding='utf-8')
        body_ps = telegram_chunks_to_ps(raw)
        tid = art['id']
        slug = art['slug']
        iso_date = art['iso_date']
        title = art['title']
        meta_desc = art['meta_desc'][:300]
        og_desc = meta_desc[:180]
        tags_html = ''.join(f'<span>{html.escape(t)}</span>' for t in art['tags'])
        blog_image_url = f'{YANDEX_MEDIA_BASE}/blog/telegram-{tid}.jpg'
        json_ld = json_lib.dumps(
            {
                '@context': 'https://schema.org',
                '@type': 'Article',
                'headline': title,
                'datePublished': iso_date,
                'dateModified': iso_date,
                'author': {'@type': 'Person', 'name': 'Дарья'},
                'image': [blog_image_url],
                'mainEntityOfPage': f'https://абхазберег.рф/blog/{slug}/',
            },
            ensure_ascii=False,
        )

        html_title = html.escape(f'{art["title_short"]} — АБХАЗБЕРЕГ')
        page = PAGE_TEMPLATE.format(
            html_title=html_title,
            meta_desc=html.escape(meta_desc),
            slug=slug,
            og_title=html.escape(title),
            og_desc=html.escape(og_desc),
            blog_image_url=blog_image_url,
            yandex_media_base=YANDEX_MEDIA_BASE,
            asset_version=ASSET_VERSION,
            tid=tid,
            json_ld=json_ld,
            breadcrumb_esc=html.escape(art['breadcrumb']),
            eyebrow_esc=html.escape(art['eyebrow']),
            h1_esc=html.escape(title),
            lead_esc=html.escape(art['lead']),
            tags_html=tags_html,
            iso_date=iso_date,
            date_ru=ru_date(iso_date),
            reading_min=art['reading_min'],
            cover_alt_esc=html.escape(art['title_short']),
            body_ps=body_ps,
            aside_esc=html.escape(art['aside_about']),
        )
        out_dir = ROOT / 'blog' / slug
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / 'index.html').write_text(page, encoding='utf-8')
        print('wrote', out_dir / 'index.html')


if __name__ == '__main__':
    main()
