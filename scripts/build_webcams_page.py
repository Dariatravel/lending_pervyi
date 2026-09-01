#!/usr/bin/env python3
"""Страница «Веб-камеры Абхазии» (/veb-kamery-abhazii/) из data/webcams.json.

Карточки без встраивания трансляций: обложка-снимок (обновляется ежедневным
воркфлоу webcams-snapshots.yml, разрешение владельцев получено), описание и
кнопка «Смотреть прямой эфир» на сайт владельца камеры. После каждого
городского блока — переходы на подборки каталога и статьи блога.

Запуск: python3 scripts/build_webcams_page.py
Страницу не редактировать руками — только через реестр и этот генератор.
"""

from __future__ import annotations

import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "data" / "webcams.json"
OUT_DIR = ROOT / "veb-kamery-abhazii"
CANON = "https://абхазберег.рф/veb-kamery-abhazii/"
MEDIA = "https://media.xn--80aacbklan7f0b.xn--p1ai/media/webcams"

TITLE = "Веб-камеры Абхазии онлайн: Гагра, Пицунда, Сухум, Рица и Псоу в реальном времени"
DESCRIPTION = (
    "Живые веб-камеры Абхазии: пляжи Гагры и Пицунды, набережная Сухума, озеро Рица, "
    "очередь на границе Псоу, Новый Афон и Гудаута. Свежие снимки каждый день и ссылки на прямые эфиры."
)

FAQ = [
    (
        "Камеры показывают прямой эфир?",
        "На карточках — свежие снимки, которые мы обновляем каждый день. Кнопка «Смотреть прямой эфир» открывает живую трансляцию на сайте владельца камеры.",
    ),
    (
        "Почему трансляция иногда не открывается?",
        "Камеры зависят от электричества и интернета на месте. Если трансляция молчит, попробуйте позже или откройте соседнюю камеру того же города.",
    ),
    (
        "Работают ли камеры зимой?",
        "Да, камеры работают круглый год. Зимой по ним удобно смотреть погоду: в Гагре и Сухуме часто +12…+15 и солнце, когда в России снег.",
    ),
    (
        "Как по камерам оценить очередь на границе Псоу?",
        "Откройте камеры блока «Псоу и граница»: видно автомобильную очередь с обеих сторон и поток на пешеходном переходе. Меньше всего машин обычно рано утром в будни.",
    ),
]


def esc(value: str) -> str:
    return html.escape(str(value), quote=True)


def ru_plural(number: int, one: str, few: str, many: str) -> str:
    """Согласование с числом: 21 камера, 22 камеры, 25 камер."""
    if number % 100 in (11, 12, 13, 14):
        return many
    if number % 10 == 1:
        return one
    if number % 10 in (2, 3, 4):
        return few
    return many


def watch_url(sources: dict, cam: dict) -> str:
    src = sources[cam["source"]]
    return src["watch_base"].replace("{channel}", cam["channel"])


def render_card(sources: dict, city: str, cam: dict) -> str:
    src = sources[cam["source"]]
    cover = f"{MEDIA}/{cam['id']}.jpg"
    url = watch_url(sources, cam)
    return f'''        <article class="blog-card webcam-card">
          <a class="blog-card__image-link" href="{esc(url)}" target="_blank" rel="noopener nofollow">
            <img src="{esc(cover)}" alt="{esc(city)} — {esc(cam['title'])}: снимок с веб-камеры" width="640" height="360" loading="lazy" decoding="async" onerror="this.closest('.blog-card__image-link').style.display='none'" />
          </a>
          <div class="blog-card__body">
            <h3>{esc(cam['title'])}</h3>
            <p>{esc(cam['about'])}</p>
            <p class="blog-card__meta">Источник: {esc(src['label'])} ({esc(src['owner'])})</p>
            <a class="blog-card__cta" href="{esc(url)}" target="_blank" rel="noopener nofollow">Смотреть прямой эфир →</a>
          </div>
        </article>'''


def render_block(sources: dict, block: dict) -> str:
    cards = "\n".join(render_card(sources, block["city"], cam) for cam in block["cams"])
    links = "".join(
        f'<a class="blog-card__cta" href="{esc(l["href"])}">{esc(l["label"])} →</a> '
        for l in block["links"]
    )
    return f'''      <section class="site-concept__section-block blog-listing" id="{esc(block['slug'])}">
        <div class="site-concept__section-head">
          <h2>Веб-камеры: {esc(block['city'])}</h2>
          <p>{esc(block['intro'])}</p>
        </div>
        <div class="blog-grid">
{cards}
        </div>
        <p class="webcam-block-links"><strong>Рядом с камерами:</strong> {links}</p>
      </section>'''


def render_faq() -> str:
    items = "\n".join(
        f'''          <details class="faq-item"><summary>{esc(q)}</summary>
            <p>{esc(a)}</p>
          </details>'''
        for q, a in FAQ
    )
    return f'''      <section class="site-concept__section-block" id="faq">
        <div class="site-concept__section-head"><h2>Частые вопросы о веб-камерах Абхазии</h2></div>
        <div class="faq-list">
{items}
        </div>
      </section>'''


def faq_jsonld() -> str:
    payload = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": q,
                "acceptedAnswer": {"@type": "Answer", "text": a},
            }
            for q, a in FAQ
        ],
    }
    return json.dumps(payload, ensure_ascii=False)


def build() -> str:
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    sources = data["sources"]
    css_version = (ROOT / "data" / "asset-version.txt").read_text(encoding="utf-8").strip()

    nav = " · ".join(
        f'<a href="#{esc(b["slug"])}">{esc(b["city"])}</a>' for b in data["blocks"]
    )
    blocks = "\n\n".join(render_block(sources, b) for b in data["blocks"])
    total = sum(len(b["cams"]) for b in data["blocks"])

    return f'''<!DOCTYPE html>
<html lang="ru" id="top">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{esc(TITLE)} — АБХАЗБЕРЕГ</title>
  <meta name="description" content="{esc(DESCRIPTION)}" />
  <meta name="robots" content="index, follow, max-image-preview:large" />
  <link rel="canonical" href="{CANON}" />
  <meta property="og:type" content="website" />
  <meta property="og:title" content="{esc(TITLE)}" />
  <meta property="og:description" content="{esc(DESCRIPTION)}" />
  <meta property="og:url" content="{CANON}" />
  <meta property="og:image" content="https://media.xn--80aacbklan7f0b.xn--p1ai/media/branding/og-banner.png" />
  <link rel="preconnect" href="https://media.xn--80aacbklan7f0b.xn--p1ai" />
  <link rel="preconnect" href="https://media.xn--80aacbklan7f0b.xn--p1ai" crossorigin />
  <link rel="icon" type="image/png" href="https://media.xn--80aacbklan7f0b.xn--p1ai/media/branding/favicon-48.png" />
  <link rel="stylesheet" href="../styles.min.css?v={css_version}" />
  <style>
    /* Ровные переносы заголовков: браузер сам балансирует строки,
       чтобы последнее слово не повисало в одиночку (замечание Дарьи 31.08.2026). */
    .site-concept__hero-card h1,
    .site-concept__section-head h2 {{ text-wrap: balance; }}
  </style>
  <script type="application/ld+json">{faq_jsonld()}</script>
</head>
<body>
  <div class="grain" aria-hidden="true"></div>
  <main class="page-shell site-concept blog-page">
    <div class="bg-blur bg-blur--mint" aria-hidden="true"></div>
    <div class="bg-blur bg-blur--sand" aria-hidden="true"></div>

    <header class="site-concept__topbar" role="banner">
      <a class="site-concept__brand" href="/">
        <img class="site-concept__brand-mark" src="https://media.xn--80aacbklan7f0b.xn--p1ai/media/branding/logo-emblem-160.png" width="80" height="80" alt="АБХАЗБЕРЕГ - жилье напрямую — на главную" decoding="async" />
        <span class="site-concept__brand-copy"><strong>АБХАЗБЕРЕГ - жилье напрямую</strong></span>
      </a>
      <nav class="site-concept__topnav" aria-label="Основная навигация">
        <a href="/">Главная</a>
        <a href="/blog/">Полезно узнать</a>
        <a href="#contacts">Контакты</a>
      </nav>
    </header>

    <article class="site-concept__hero-card">
      <p class="blog-breadcrumbs"><a href="/">Главная</a> / Веб-камеры Абхазии</p>
      <p class="site-concept__eyebrow">Абхазия в прямом эфире</p>
      <!-- Заголовок длинный: базовый размер hero-заголовка выглядит плакатом
           (замечание Дарьи 24.08.2026) — на этой странице он скромнее. -->
      <h1 style="font-size: clamp(1.5rem, 1rem + 2vw, 2.3rem)">Веб-камеры Абхазии онлайн: Гагра, Пицунда, Сухум, Рица и Псоу в реальном времени</h1>
      <p class="blog-hero__lead">{total} {ru_plural(total, "камера", "камеры", "камер")} в 8 локациях: посмотрите море, погоду и очередь на границе до поездки. Снимки на карточках обновляются каждый день, по кнопке открывается живая трансляция.</p>
      <p class="webcam-nav">{nav}</p>
    </article>

{blocks}

{render_faq()}

      <section class="site-concept__section-block" id="about-source">
        <div class="site-concept__section-head"><h2>Откуда трансляции</h2></div>
        <p>Камеры принадлежат двум операторам: <a href="https://apsny.camera/" target="_blank" rel="noopener">APSNY.CAMERA</a> (проект интернет-провайдера ООО «Система») и <a href="https://a-mobile.camera/" target="_blank" rel="noopener">A-MOBILE.CAMERA</a>. Прямые эфиры открываются на их сайтах; снимки на этой странице публикуются с разрешения владельцев и обновляются раз в день, в светлое время суток.</p>
        <p>Понравилась картинка с камеры? Посмотрите <a href="/#catalog">каталог проверенного жилья</a> в этом городе — фото реальные, бронирование напрямую у Дарьи, без предоплат на карту незнакомцам.</p>
      </section>

      <section class="section site-concept__contacts" id="contacts">
        <article class="cta-block contact-shell">
          <div class="contact-shell__intro">
            <p class="eyebrow">Контакты и бронирование</p>
            <p>
              Проверить наличие номеров и задать вопросы можно по номеру<br/>
              <strong class="contact-phone">+7 940 900-33-40</strong><br/>
              <span class="contact-messengers">(max, whatsapp, telegram - только сообщения, обычный звонок не пройдёт)</span>
            </p>
          </div>
          <div class="contact-channel-panel" aria-labelledby="contact-channel-title">
            <div class="contact-channel-panel__heading">
              <h2 class="contact-channel-panel__title" id="contact-channel-title">Выберите удобный мессенджер</h2>
              <p class="contact-channel-panel__hint">Все обращения получает один менеджер.</p>
            </div>
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
        </article>
      </section>
  </main>
</body>
</html>
'''


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "index.html").write_text(build(), encoding="utf-8")
    print(f"Собрано: {OUT_DIR.relative_to(ROOT)}/index.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
