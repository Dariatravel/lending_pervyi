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
  <link rel="preconnect" href="https://media.xn--80aacbklan7f0b.xn--p1ai" crossorigin />
  <link rel="icon" type="image/png" href="https://media.xn--80aacbklan7f0b.xn--p1ai/media/branding/favicon-48.png" />
  <link rel="stylesheet" href="../styles.min.css?v={css_version}" />
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
        <a href="/#contacts">Контакты</a>
      </nav>
    </header>

    <article class="site-concept__hero-card">
      <p class="blog-breadcrumbs"><a href="/">Главная</a> / Веб-камеры Абхазии</p>
      <p class="site-concept__eyebrow">Абхазия в прямом эфире</p>
      <!-- Заголовок длинный: базовый размер hero-заголовка выглядит плакатом
           (замечание Дарьи 24.08.2026) — на этой странице он скромнее. -->
      <h1 style="font-size: clamp(1.5rem, 1rem + 2vw, 2.3rem)">Веб-камеры Абхазии онлайн: Гагра, Пицунда, Сухум, Рица и Псоу в реальном времени</h1>
      <p class="blog-hero__lead">{total} камер в 8 локациях: посмотрите море, погоду и очередь на границе до поездки. Снимки на карточках обновляются каждый день, по кнопке открывается живая трансляция.</p>
      <p class="webcam-nav">{nav}</p>
    </article>

{blocks}

{render_faq()}

      <section class="site-concept__section-block" id="about-source">
        <div class="site-concept__section-head"><h2>Откуда трансляции</h2></div>
        <p>Камеры принадлежат двум операторам: <a href="https://apsny.camera/" target="_blank" rel="noopener">APSNY.CAMERA</a> (проект интернет-провайдера ООО «Система») и <a href="https://a-mobile.camera/" target="_blank" rel="noopener">A-MOBILE.CAMERA</a>. Прямые эфиры открываются на их сайтах; снимки на этой странице публикуются с разрешения владельцев и обновляются ежедневно около 15:00.</p>
        <p>Понравилась картинка с камеры? Посмотрите <a href="/#catalog">каталог проверенного жилья</a> в этом городе — фото реальные, бронирование напрямую у Дарьи, без предоплат на карту незнакомцам.</p>
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
