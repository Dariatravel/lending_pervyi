#!/usr/bin/env python3
"""Скрытый раздел «Экскурсии» (/vezu/) из канала @abhazbereg_vezu.

Аналог блога: одна публикация канала = одна страница vezu/<slug>/.
Раздел нигде на сайте не упоминается (нет ссылок в навигации, главной
и sitemap) — клиенты получают короткую ссылку абхазберег.рф/vezu/.

Запуск на Mac (нужна tg_session):
  python3 scripts/sync_vezu_from_telegram.py            # все посты канала
  TARGET_VEZU_POST_IDS=246,255 python3 scripts/sync_vezu_from_telegram.py
"""
from __future__ import annotations

import html
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from telegram_runtime import connected_telegram_client, run_async_entrypoint  # noqa: E402
from sync_blog_from_abhazbereg import (  # noqa: E402
    API_HASH,
    API_ID,
    SESSION,
    YANDEX_MEDIA_BASE,
    BLOG_ARTICLE_IMAGE_SIZES,
    BLOG_CARD_IMAGE_SIZES,
    blog_image_srcset,
    clean_title_line,
    estimate_reading_min,
    ru_date,
    telegram_text_to_sections_html,
)

CHANNEL = "abhazbereg_vezu"
VEZU_DIR = ROOT / "vezu"
MEDIA_DIR = ROOT / "media" / "vezu"
SOURCES_DIR = ROOT / "scripts" / "vezu_telegram_sources"
MANIFEST_PATH = ROOT / "data" / "vezu-posts.json"
SKIP_PATH = ROOT / "data" / "vezu-skip.json"  # post_id служебных постов — не публикуем
# Временно: посты старше этой даты не показываются в списке /vezu/
# (страницы постов остаются доступны по прямым ссылкам). Чтобы вернуть —
# поставить None. Решение Дарьи от 17.07.2026.
INDEX_MIN_DATE: str | None = "2026-01-01"
CSS_VERSION = (ROOT / "data" / "asset-version.txt").read_text(encoding="utf-8").strip()
MIN_POST_CHARS = 200  # служебные/короткие посты канала не становятся страницами


MAX_RAW_VIDEO_UPLOAD_MB = 95  # без ffmpeg заливаем исходник только до этого размера


def publish_vezu_video(video_path: "Path", video_name: str) -> str:
    """Залить видео экскурсии в бакет; вернуть публичный URL или '' при отказе.

    При наличии ffmpeg видео сжимается в web-вариант (960px/1200k, как в
    основном синке каталога); без ffmpeg исходник заливается как есть,
    но только если он не тяжелее MAX_RAW_VIDEO_UPLOAD_MB.
    """
    import shutil as _shutil

    if not video_path.exists() or video_path.stat().st_size == 0:
        return ""
    upload_candidate = video_path
    if _shutil.which("ffmpeg"):
        web_path = video_path.with_name(video_path.stem + "-web.mp4")
        if not web_path.exists() or web_path.stat().st_size == 0:
            from sync_catalog_from_telegram import transcode_video

            transcode_video(video_path, web_path, "1200k")
        if web_path.exists() and web_path.stat().st_size > 0:
            upload_candidate = web_path
    if upload_candidate == video_path and video_path.stat().st_size > MAX_RAW_VIDEO_UPLOAD_MB * 1024 * 1024:
        print(f"[warn] видео {video_name} слишком большое без ffmpeg — оставляем telegram-встройку", file=sys.stderr)
        return ""
    from yandex_storage import upload_file

    return upload_file(upload_candidate, f"media/vezu/{video_name}", "video/mp4")


def is_video_message(msg: object) -> bool:
    file_obj = getattr(msg, "file", None)
    mime_type = str(getattr(file_obj, "mime_type", "") or "")
    return bool(getattr(msg, "video", None)) or mime_type.startswith("video/")


def is_photo_message(msg: object) -> bool:
    return bool(getattr(msg, "photo", None))


def render_media_gallery(media_items: list[dict[str, str]]) -> str:
    if not media_items:
        return ""
    cards: list[str] = []
    for item in media_items:
        kind = item.get("kind", "")
        src = html.escape(item.get("src", ""), quote=True)
        alt = html.escape(item.get("alt", "Фото экскурсии"), quote=True)
        if not src:
            continue
        if kind == "telegram":
            post_ref = html.escape(item.get("telegram_post", ""), quote=True)
            if not post_ref:
                continue
            cards.append(
                "            <figure class=\"blog-article__media-item blog-article__media-item--telegram\">"
                f"<script async src=\"https://telegram.org/js/telegram-widget.js?22\" data-telegram-post=\"{post_ref}\" data-width=\"100%\" data-userpic=\"false\" data-single=\"1\"></script>"
                "</figure>"
            )
            continue
        if kind == "video":
            poster = item.get("poster", "")
            poster_attr = f' poster="{html.escape(poster, quote=True)}"' if poster else ""
            cards.append(
                "            <figure class=\"blog-article__media-item blog-article__media-item--video\">"
                # Видео в статье идут ниже текста — грузим их только по клику,
                # чтобы не отнимать сеть у самой страницы.
                f"<video controls preload=\"none\" playsinline{poster_attr}>"
                f"<source src=\"{src}\" type=\"video/mp4\" />"
                "</video></figure>"
            )
        else:
            srcset = item.get("srcset", "")
            srcset_attr = f' srcset="{html.escape(srcset, quote=True)}"' if srcset else ""
            cards.append(
                "            <figure class=\"blog-article__media-item\">"
                f"<img src=\"{src}\"{srcset_attr} sizes=\"(max-width: 760px) 100vw, 360px\" alt=\"{alt}\" loading=\"lazy\" decoding=\"async\" />"
                "</figure>"
            )
    if not cards:
        return ""
    return "\n          <div class=\"blog-article__media-gallery\" aria-label=\"Фото и видео экскурсии\">\n" + "\n".join(cards) + "\n          </div>\n"


_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh",
    "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "ts",
    "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu",
    "я": "ya",
}


def slugify(value: str, *, max_len: int = 60) -> str:
    value = re.sub(r"\s+", " ", value or "").strip().lower()
    value = "".join(_TRANSLIT.get(ch, ch) for ch in value)
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return (value or "excursion")[:max_len].strip("-")


PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="ru" id="top">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{html_title}</title>
  <meta name="description" content="{meta_desc}" />
  <link rel="canonical" href="https://абхазберег.рф/vezu/{slug}/" />
  <meta property="og:type" content="article" />
  <meta property="og:title" content="{og_title}" />
  <meta property="og:description" content="{og_desc}" />
  <meta property="og:url" content="https://абхазберег.рф/vezu/{slug}/" />
  <meta property="og:image" content="{image_src}" />
  <link rel="preconnect" href="https://media.xn--80aacbklan7f0b.xn--p1ai" />
  <link rel="preconnect" href="https://media.xn--80aacbklan7f0b.xn--p1ai" crossorigin />
  <link rel="icon" type="image/png" href="{yandex_media_base}/media/branding/favicon-48.png" />
  <link rel="stylesheet" href="../../styles.min.css?v={css_version}" />
</head>
<body>
  <div class="grain" aria-hidden="true"></div>
  <main class="page-shell site-concept blog-page blog-article-page vezu-page">
    <div class="bg-blur bg-blur--mint" aria-hidden="true"></div>
    <div class="bg-blur bg-blur--sand" aria-hidden="true"></div>

    <header class="site-concept__topbar" role="banner">
      <a class="site-concept__brand" href="/">
        <img class="site-concept__brand-mark" src="{yandex_media_base}/media/branding/logo-emblem-160.png" width="80" height="80" alt="АБХАЗБЕРЕГ - жилье напрямую — на главную" decoding="async" />
        <span class="site-concept__brand-copy"><strong>АБХАЗБЕРЕГ - жилье напрямую</strong></span>
      </a>
      <nav class="site-concept__topnav" aria-label="Основная навигация">
        <a href="/vezu/" aria-current="page">Экскурсии</a>
        <a href="#contacts">Контакты</a>
      </nav>
    </header>

    <article class="site-concept__hero-card blog-article">
      <p class="blog-breadcrumbs"><a href="/vezu/">Экскурсии</a> / {breadcrumb_esc}</p>
      <p class="site-concept__eyebrow">Экскурсии по Абхазии</p>
      <h1>{h1_esc}</h1>
      <p class="blog-hero__lead">{lead_esc}</p>

      <div class="blog-article__meta-row"><time datetime="{iso_date}">{date_ru}</time><span>Чтение: {reading_min} минут</span></div>

      <div class="blog-article__layout">
        <div class="blog-article__main">
          <div class="blog-article__content blog-article__content--sections">
        <img class="blog-article__cover-inline" src="{image_src}" srcset="{image_srcset}" sizes="{article_image_sizes}" width="480" height="640" alt="{cover_alt_esc}" loading="eager" decoding="async" />
{body_html}
{media_gallery_html}
          </div>
        </div>
        <aside class="blog-article__aside">
          <section class="blog-note-card">
            <h2>Хотите на эту экскурсию?</h2>
            <p>Напишите мне — расскажу про даты, программу и стоимость, помогу собрать компанию.</p>
            <a class="btn-book" href="#contacts">Написать мне</a>
          </section>
          <section class="blog-note-card">
            <h2>Другие маршруты</h2>
            <p>Все экскурсии и маршруты — в общем списке раздела.</p>
            <a class="btn-book btn-book--soft" href="/vezu/">Смотреть все</a>
          </section>
        </aside>
      </div>
    </article>

  <section class="section site-concept__contacts" id="contacts">
    <article class="cta-block contact-shell">
      <div class="contact-shell__intro">
        <p class="eyebrow">Контакты и запись</p>
        <p>Записаться на экскурсию и задать вопросы можно по номеру<br /><strong class="contact-phone">+7 940 900-33-40</strong><br /><span class="contact-messengers">(max, whatsapp, telegram - только сообщения, обычный звонок не пройдёт)</span></p>
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
  <script src="../../scripts.min.js?v={css_version}" defer></script>
  <a class="back-to-top" href="#top" aria-label="Наверх"><span class="back-to-top__icon" aria-hidden="true">↑</span></a>
</body>
</html>
"""

INDEX_TEMPLATE = """<!DOCTYPE html>
<html lang="ru" id="top">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Экскурсии по Абхазии — АБХАЗБЕРЕГ</title>
  <meta name="description" content="Экскурсии и маршруты по Абхазии от АБХАЗБЕРЕГ: горы, каньоны, озёра и море. Живые описания и запись напрямую." />
  <link rel="canonical" href="https://абхазберег.рф/vezu/" />
  <meta property="og:title" content="Экскурсии по Абхазии — АБХАЗБЕРЕГ" />
  <meta property="og:description" content="Экскурсии и маршруты по Абхазии: горы, каньоны, озёра и море." />
  <meta property="og:url" content="https://абхазберег.рф/vezu/" />
  <link rel="preconnect" href="https://media.xn--80aacbklan7f0b.xn--p1ai" />
  <link rel="preconnect" href="https://media.xn--80aacbklan7f0b.xn--p1ai" crossorigin />
  <link rel="icon" type="image/png" href="{yandex_media_base}/media/branding/favicon-48.png" />
  <link rel="stylesheet" href="../styles.min.css?v={css_version}" />
</head>
<body>
  <div class="grain" aria-hidden="true"></div>
  <main class="page-shell site-concept blog-page">
    <div class="bg-blur bg-blur--mint" aria-hidden="true"></div>
    <div class="bg-blur bg-blur--sand" aria-hidden="true"></div>

    <header class="site-concept__topbar" role="banner">
      <a class="site-concept__brand" href="/">
        <img class="site-concept__brand-mark" src="{yandex_media_base}/media/branding/logo-emblem-160.png" width="80" height="80" alt="АБХАЗБЕРЕГ - жилье напрямую — на главную" decoding="async" />
        <span class="site-concept__brand-copy"><strong>АБХАЗБЕРЕГ - жилье напрямую</strong></span>
      </a>
      <nav class="site-concept__topnav" aria-label="Основная навигация">
        <a href="/vezu/" aria-current="page">Экскурсии</a>
        <a href="#contacts">Контакты</a>
      </nav>
    </header>

    <section class="site-concept__hero-card blog-hero">
      <p class="site-concept__eyebrow">АБХАЗБЕРЕГ ВЕЗУ</p>
      <h1>Экскурсии по Абхазии</h1>
      <p class="blog-hero__lead">Маршруты, которые мы проводим сами: горы, каньоны, озёра и море. Выбирайте — и напишите мне, чтобы записаться.</p>
    </section>

    <section class="site-concept__section-block">
      <div class="blog-grid">
{cards_html}
      </div>
    </section>

  <section class="section site-concept__contacts" id="contacts">
    <article class="cta-block contact-shell">
      <div class="contact-shell__intro">
        <p class="eyebrow">Контакты и запись</p>
        <p>Записаться на экскурсию и задать вопросы можно по номеру<br /><strong class="contact-phone">+7 940 900-33-40</strong><br /><span class="contact-messengers">(max, whatsapp, telegram - только сообщения, обычный звонок не пройдёт)</span></p>
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
  <script src="../scripts.min.js?v={css_version}" defer></script>
  <a class="back-to-top" href="#top" aria-label="Наверх"><span class="back-to-top__icon" aria-hidden="true">↑</span></a>
</body>
</html>
"""

CARD_TEMPLATE = """        <a class="blog-card" href="/vezu/{slug}/">
          <img class="blog-card__cover" src="{image_src}" srcset="{image_srcset}" sizes="{card_image_sizes}" width="220" height="150" alt="{alt_esc}" loading="lazy" decoding="async" />
          <div class="blog-card__body">
            <p class="blog-card__tag">экскурсия</p>
            <h2>{title_esc}</h2>
            <p class="blog-card__excerpt">{excerpt_esc}</p>
            <span class="blog-card__more">Читать</span>
          </div>
        </a>"""


def first_meaningful_paragraph(text: str, title: str) -> str:
    for block in re.split(r"\n\s*\n", text):
        block_clean = re.sub(r"\s+", " ", block).strip()
        if not block_clean or block_clean == title:
            continue
        if len(block_clean) >= 60:
            return block_clean
    return title


async def sync_vezu(post_ids: list[int] | None = None) -> list[dict[str, object]]:
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    SOURCES_DIR.mkdir(parents=True, exist_ok=True)
    VEZU_DIR.mkdir(parents=True, exist_ok=True)

    from sync_catalog_from_telegram import upload_local_image_public_url

    built: list[dict[str, object]] = []
    async with connected_telegram_client(SESSION, API_ID, API_HASH, receive_updates=False) as client:
        entity = await client.get_entity(CHANNEL)

        posts: dict[int, dict[str, object]] = {}
        async for msg in client.iter_messages(entity, limit=1200):
            group_key = int(getattr(msg, "grouped_id", None) or msg.id)
            row = posts.setdefault(group_key, {"text": "", "text_id": 0, "photo_msg": None, "media_msgs": [], "date": None})
            text = (msg.message or "").strip()
            if text and len(text) > len(str(row["text"])):
                row["text"] = text
                row["text_id"] = msg.id
                row["date"] = msg.date
            if is_photo_message(msg) or is_video_message(msg):
                row["media_msgs"].append(msg)
            if row["photo_msg"] is None and is_photo_message(msg):
                row["photo_msg"] = msg

        skip_ids: set[int] = set()
        if SKIP_PATH.exists():
            skip_ids = {int(v) for v in json.loads(SKIP_PATH.read_text(encoding="utf-8"))}

        for group_key in sorted(posts):
            row = posts[group_key]
            text = str(row["text"])
            post_id = int(row["text_id"] or 0)
            if not post_id or len(text) < MIN_POST_CHARS or post_id in skip_ids:
                continue
            if post_ids and post_id not in post_ids:
                continue

            title = clean_title_line(text.split("\n", 1)[0])
            if not title:
                continue
            title_short = title if len(title) <= 72 else title[:69] + "…"
            slug = f"{slugify(title)}-{post_id}"
            (SOURCES_DIR / f"{CHANNEL}-{post_id}.txt").write_text(text + "\n", encoding="utf-8")

            image_name = f"telegram-vezu-{post_id}.jpg"
            image_path = MEDIA_DIR / image_name
            photo_msg = row["photo_msg"]
            image_src = f"{YANDEX_MEDIA_BASE}/media/branding/og-banner.png"
            image_srcset = ""
            media_items: list[dict[str, str]] = []
            if photo_msg is not None:
                if not image_path.exists():
                    await client.download_media(photo_msg, file=str(image_path))
            else:
                # Фото в посте нет — обложкой становится кадр (превью) видео.
                first_video = next((m for m in sorted(row["media_msgs"], key=lambda item: item.id)
                                    if is_video_message(m)), None)
                if first_video is not None and not image_path.exists():
                    try:
                        await client.download_media(first_video, file=str(image_path), thumb=-1)
                    except Exception as error:  # noqa: BLE001
                        print(f"[warn] превью видео не скачалось ({slug}): {error}", file=sys.stderr)
            if image_path.exists():
                upload_local_image_public_url(None, image_path, f"media/vezu/{image_name}")
                image_src = f"{YANDEX_MEDIA_BASE}/media/vezu/{image_name}"
                image_srcset = blog_image_srcset(image_src)

            cover_msg_id = int(getattr(photo_msg, "id", 0) or 0)
            for media_index, media_msg in enumerate(sorted(row["media_msgs"], key=lambda item: item.id), start=1):
                media_msg_id = int(getattr(media_msg, "id", 0) or 0)
                if media_msg_id == cover_msg_id:
                    continue
                if is_photo_message(media_msg):
                    gallery_name = f"telegram-vezu-{post_id}-{media_index:02d}.jpg"
                    gallery_path = MEDIA_DIR / gallery_name
                    if not gallery_path.exists():
                        await client.download_media(media_msg, file=str(gallery_path))
                    if gallery_path.exists():
                        public_url = upload_local_image_public_url(None, gallery_path, f"media/vezu/{gallery_name}")
                        media_items.append(
                            {
                                "kind": "image",
                                "src": public_url,
                                "srcset": blog_image_srcset(public_url),
                                "alt": f"{title_short} — фото {media_index}",
                            }
                        )
                elif is_video_message(media_msg):
                    # Видео публикуем на странице (решение Дарьи 17.07.2026):
                    # скачиваем, при наличии ffmpeg сжимаем в web-вариант,
                    # иначе заливаем как есть (с лимитом размера).
                    video_name = f"telegram-vezu-{post_id}-{media_index:02d}.mp4"
                    video_path = MEDIA_DIR / video_name
                    poster_name = f"telegram-vezu-{post_id}-{media_index:02d}-poster.jpg"
                    poster_path = MEDIA_DIR / poster_name
                    if not video_path.exists():
                        await client.download_media(media_msg, file=str(video_path))
                    if not poster_path.exists():
                        try:
                            await client.download_media(media_msg, file=str(poster_path), thumb=-1)
                        except Exception:  # noqa: BLE001
                            pass
                    published = publish_vezu_video(video_path, video_name)
                    poster_url = ""
                    if poster_path.exists():
                        poster_url = upload_local_image_public_url(
                            None, poster_path, f"media/vezu/{poster_name}"
                        )
                    if published:
                        media_items.append(
                            {
                                "kind": "video",
                                "src": published,
                                "poster": poster_url,
                                "alt": f"{title_short} — видео {media_index}",
                            }
                        )
                    else:
                        # не удалось залить (слишком большое без ffmpeg) —
                        # оставляем встроенный telegram-пост, чтобы видео было
                        media_items.append(
                            {
                                "kind": "telegram",
                                "src": f"https://t.me/{CHANNEL}/{media_msg_id}",
                                "telegram_post": f"{CHANNEL}/{media_msg_id}",
                                "alt": f"{title_short} — видео {media_index}",
                            }
                        )

            lead = first_meaningful_paragraph(text, title)[:220]
            iso_date = row["date"].strftime("%Y-%m-%d") if row["date"] else "2026-01-01"
            body_html = telegram_text_to_sections_html(text)

            page = PAGE_TEMPLATE.format(
                html_title=html.escape(f"{title_short} — экскурсии АБХАЗБЕРЕГ"),
                meta_desc=html.escape(lead[:300]),
                slug=slug,
                og_title=html.escape(title),
                og_desc=html.escape(lead[:180]),
                image_src=image_src,
                image_srcset=image_srcset,
                article_image_sizes=BLOG_ARTICLE_IMAGE_SIZES,
                css_version=CSS_VERSION,
                breadcrumb_esc=html.escape(title_short),
                h1_esc=html.escape(title),
                lead_esc=html.escape(lead),
                iso_date=iso_date,
                date_ru=ru_date(iso_date),
                reading_min=estimate_reading_min(text),
                cover_alt_esc=html.escape(title_short),
                body_html=body_html,
                media_gallery_html=render_media_gallery(media_items),
                yandex_media_base=YANDEX_MEDIA_BASE,
            )
            out_dir = VEZU_DIR / slug
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "index.html").write_text(page, encoding="utf-8")
            built.append(
                {
                    "post_id": post_id,
                    "slug": slug,
                    "title": title,
                    "excerpt": lead,
                    "iso_date": iso_date,
                    "image_src": image_src,
                    "image_srcset": image_srcset,
                    "media_items": media_items,
                }
            )
            print(f"wrote vezu/{slug}/index.html")

    return built


def render_index(cards: list[dict[str, object]]) -> str:
    blocks = [
        CARD_TEMPLATE.format(
            slug=card["slug"],
            image_src=card["image_src"],
            image_srcset=card["image_srcset"],
            card_image_sizes=BLOG_CARD_IMAGE_SIZES,
            alt_esc=html.escape(str(card["title"])),
            title_esc=html.escape(str(card["title"])),
            excerpt_esc=html.escape(str(card["excerpt"])[:160]),
        )
        for card in cards
    ]
    return INDEX_TEMPLATE.format(
        cards_html="\n".join(blocks),
        css_version=CSS_VERSION,
        yandex_media_base=YANDEX_MEDIA_BASE,
    )


async def main_async() -> int:
    only_ids = os.getenv("TARGET_VEZU_POST_IDS", "").strip()
    post_ids = [int(p.strip()) for p in only_ids.split(",") if p.strip()] or None
    built = await sync_vezu(post_ids)

    skip_ids: set[int] = set()
    if SKIP_PATH.exists():
        skip_ids = {int(v) for v in json.loads(SKIP_PATH.read_text(encoding="utf-8"))}

    known: dict[str, dict[str, object]] = {}
    if MANIFEST_PATH.exists():
        for card in json.loads(MANIFEST_PATH.read_text(encoding="utf-8")):
            if int(card.get("post_id") or 0) in skip_ids:
                page = VEZU_DIR / str(card["slug"]) / "index.html"
                page.unlink(missing_ok=True)
                if page.parent.exists() and not any(page.parent.iterdir()):
                    page.parent.rmdir()
                print(f"скрыт служебный пост: vezu/{card['slug']}/")
                continue
            known[str(card["slug"])] = card
    for card in built:
        known[str(card["slug"])] = card
    cards = sorted(known.values(), key=lambda c: (str(c["iso_date"]), int(c.get("post_id") or 0)), reverse=True)

    MANIFEST_PATH.write_text(json.dumps(cards, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    index_cards = cards
    if INDEX_MIN_DATE:
        index_cards = [c for c in cards if str(c.get("iso_date", "")) >= INDEX_MIN_DATE]
    (VEZU_DIR / "index.html").write_text(render_index(index_cards), encoding="utf-8")
    hidden = len(cards) - len(index_cards)
    print(f"обновлён vezu/index.html ({len(index_cards)} экскурсий, скрыто старых: {hidden}); "
          "раздел скрытый — в sitemap не добавляем")
    return 0


def main() -> int:
    return run_async_entrypoint(main_async(), name="sync_vezu_from_telegram", default_timeout=1800)


if __name__ == "__main__":
    raise SystemExit(main())
