#!/usr/bin/env python3
import html
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX_FILE = ROOT / "index.html"
HOTEL_FILES = sorted((ROOT / "hotels").glob("*/index.html"))
KVARTIRA_FILES = sorted((ROOT / "kvartira").glob("*/index.html"))
LISTING_PRICE_FILES = sorted(set(HOTEL_FILES) | set(KVARTIRA_FILES))

LISTING_GUEST_REVIEWS_BLOCK = """      <section class="hotel-card__guest-reviews" aria-label="Отзывы гостей">
        <p class="eyebrow">Отзывы гостей</p>
        <div class="reviews-scroller" data-random-reviews="" data-review-count="4" aria-label="Лента отзывов"></div>
      </section>
"""

HOME_SOCIAL_STATS_STRIP = """  <section class="section site-concept__social-strip" aria-label="Наши сообщества в соцсетях">
    <div class="site-concept__social-stats site-concept__social-stats--strip" role="list">
      <a aria-label="Telegram: 13 900 подписчиков, открыть канал" class="site-concept__social-stat" href="https://t.me/abhazbooking" rel="noopener noreferrer" role="listitem" target="_blank">
        <span aria-hidden="true" class="site-concept__social-stat-icon site-concept__social-stat-icon--tg">
          <svg aria-hidden="true" fill="none" height="28" viewBox="0 0 24 24" width="28" xmlns="http://www.w3.org/2000/svg"><path d="M21.5 5.2 3.4 11.9c-1.1.4-1.1 1-.2 1.3l4.6 1.4 1.8 5.5c.2.6.9.8 1.4.4l2.5-2 4.3 3.2c.8.4 1.7.2 2-.6l3-14.2c.4-1.6-.6-2.3-1.8-1.7Z" fill="#fff"/></svg>
        </span>
        <strong>13&#8239;900</strong>
        <span class="site-concept__social-stat-label">подписчиков</span>
      </a>
      <a aria-label="ВКонтакте: 42 000 участников" class="site-concept__social-stat" href="https://vk.com/abhazbereg" rel="noopener noreferrer" role="listitem" target="_blank">
        <span aria-hidden="true" class="site-concept__social-stat-icon site-concept__social-stat-icon--vk">
          <svg aria-hidden="true" fill="none" height="24" viewBox="0 0 24 24" width="24" xmlns="http://www.w3.org/2000/svg"><path d="M15.7 0H8.3C2.8 0 0 2.8 0 8.3v7.4C0 22.2 2.8 24 8.3 24h7.4c5.5 0 8.3-1.8 8.3-7.3V8.3C24 2.8 21.2 0 15.7 0zm4.1 17.3h-1.7c-.7 0-.9-.5-2-1.7-1-1-1.5-1.2-1.7-1.2-.4 0-.5.1-.5.6v1.6c0 .4-.1.7-1.2.7-1.9 0-4-1.1-5.5-3.2-2.2-3.1-2.8-5.2-2.8-5.6 0-.2.2-.5.6-.5h1.7c.4 0 .6.2.8.7.8 2.5 2.3 4.6 2.9 4.6.2 0 .3-.1.3-.7V9.7c-.1-1.2-.7-1.3-.7-1.7 0-.2.2-.4.4-.4h2.7c.3 0 .4.2.4.5v4c0 .3.1.5.3.5.2 0 .3-.1.6-.3 1-1.1 1.7-2.9 1.7-2.9.2-.3.3-.5.7-.5h1.7c.5 0 .6.3.5.7-.2.9-2.1 3.6-2.1 3.6-.2.3-.3.4 0 .7.2.3.7.8.9 1.3.6 1 1.1 2.1 1.2 2.8.1.4-.1.7-.5.7z" fill="#fff"/></svg>
        </span>
        <strong>42&#8239;000</strong>
        <span class="site-concept__social-stat-label">участников</span>
      </a>
      <a aria-label="MAX: 5 500 участников" class="site-concept__social-stat" href="https://max.ru/abhazbereg" rel="noopener noreferrer" role="listitem" target="_blank">
        <span aria-hidden="true" class="site-concept__social-stat-icon site-concept__social-stat-icon--max">
          <svg aria-hidden="true" fill="none" height="26" viewBox="0 0 24 24" width="26" xmlns="http://www.w3.org/2000/svg"><path d="M7 10c0-1.1.9-2 2-2h6c1.1 0 2 .9 2 2v3c0 1.1-.9 2-2 2h-2.5l-2.2 2.2c-.4.4-1 .1-1-.5V15H9c-1.1 0-2-.9-2-2v-3Z" fill="#fff"/></svg>
        </span>
        <strong>5&#8239;500</strong>
        <span class="site-concept__social-stat-label">участников</span>
      </a>
    </div>
  </section>"""

LISTING_PAGE_GUIDE_SECTION = """  <section class="site-concept__section-block" id="guide">
    <div class="site-concept__section-head">
      <div>
        <p class="site-concept__eyebrow">Как бронировать</p>
        <h2>Как найти жильё в Абхазии без утомительного поиска и переплат</h2>
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
        <a class="btn-book site-concept__guide-cta-btn" href="#contacts">Написать мне</a>
      </div>
    </div>
  </section>"""


def listing_catalog_markup(path: Path) -> tuple[str, str, str]:
    """Eyebrow link HTML (for inside <p class=\"eyebrow\">), save-button href, save-button label."""
    if "kvartira" in path.parts:
        return (
            '<a href="/kvartira/"><strong>Каталог квартир</strong></a>',
            "/kvartira/",
            "К каталогу квартир",
        )
    return (
        '<a href="/"><strong>Каталог Абхазберег</strong></a>',
        "/",
        "К каталогу",
    )


def strip_tags(text: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", text or "", flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    return re.sub(r"[ \t]+", " ", text).strip()


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", strip_tags(text)).strip(" :,-")


def clean_html_block(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def format_lead_text(text: str) -> str:
    value = clean_text(text)
    value = re.sub(r"\s*•\s*", " • ", value)
    return re.sub(r"\s+", " ", value).strip(" •")


def truncate_meta_description(text: str, max_len: int = 158) -> str:
    t = re.sub(r"\s+", " ", (text or "").strip())
    if len(t) <= max_len:
        return t
    cut = t[: max_len - 1]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut + "…"


def _merge_lead_and_description_for_meta(lead: str, description: str) -> str:
    """Склеивает лид и описание для meta без повторения предложений, уже входящих в лид."""
    a = (lead or "").strip()
    b = (description or "").strip()
    if not b:
        return a
    if not a:
        return b
    a_low = a.lower()
    extra: list[str] = []
    for sentence in split_sentences(b):
        s = sentence.strip()
        if not s:
            continue
        s_key = s.lower().rstrip(".")
        if len(s_key) >= 12 and s_key in a_low:
            continue
        extra.append(s)
    if not extra:
        return a
    tail = " ".join(extra)
    if a[-1:] in ".!?":
        return f"{a} {tail}".strip()
    return f"{a}. {tail}".strip()


def build_listing_meta_description(lead_text: str, description: str) -> str:
    """Краткое описание для meta/og без эмодзи и служебных ярлыков (аргументы уже проходят sanitize)."""
    a = (lead_text or "").strip()
    b = (description or "").strip()
    if a and b:
        if b.lower().startswith(a.lower()[: min(48, len(a))]):
            merged = b
        elif len(a) >= 24 and a.lower() in b.lower()[: min(len(b), 200)]:
            merged = b
        else:
            merged = _merge_lead_and_description_for_meta(a, b)
    else:
        merged = a or b
    return truncate_meta_description(
        strip_gps_coordinate_clause(sanitize_listing_card_intro_text(merged))
    )


def patch_listing_head_meta_descriptions(page_html: str, meta_text: str) -> str:
    """Подменяет description и og:description в сохранённом <head> листинга."""
    esc = html.escape(meta_text, quote=True)

    def repl_desc(m: re.Match[str]) -> str:
        return f"{m.group(1)}{esc}{m.group(2)}"

    out = re.sub(
        r'(<meta\s+name="description"\s+content=")[^"]*("\s*/?>)',
        repl_desc,
        page_html,
        count=1,
        flags=re.I,
    )
    out = re.sub(
        r'(<meta\s+property="og:description"\s+content=")[^"]*("\s*/?>)',
        repl_desc,
        out,
        count=1,
        flags=re.I,
    )
    return out


_GPS_COORD_CLAUSE_RE = re.compile(
    r"\s*[.;]?\s*Координаты\s*:?\s*\d[\d.\s]*\s*,\s*\d[\d.\s]*",
    re.IGNORECASE,
)


def strip_gps_coordinate_clause(text: str) -> str:
    """Убирает из строки карточки фрагмент «Координаты: …, …» (часто дублируется в лиде, prose и benefits)."""
    if not text:
        return text
    t = _GPS_COORD_CLAUSE_RE.sub("", text)
    t = re.sub(r"\s{2,}", " ", t).strip(" ,.;•")
    t = re.sub(r"\s+\.", ".", t)
    return t


def _is_coordinates_noise_sentence(text: str) -> bool:
    """Предложение только про координаты / пару градусов — не для «Важно для гостя» и не как отдельный абзац."""
    plain = clean_text(text).strip()
    if not plain:
        return False
    low = plain.lower()
    if "координат" in low:
        return True
    return bool(re.search(r"\d{1,2}\.\d{4,}\s*,\s*\d{1,2}\.\d{4,}", plain))


def sanitize_listing_card_intro_text(text: str) -> str:
    """Убирает эмодзи и служебные ярлыки ✔территория: / ✔номера: / ✔цены: из подзаголовка и превью карточки."""
    value = remove_price_clauses(text)
    value = clean_text(value)
    if not value:
        return ""
    value = re.sub(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]", "", value)
    value = value.replace("\ufe0f", "").replace("\u200d", "")
    value = re.sub(r"^[\s\u2714\u2705\u2713\u2611\ufe0f•·\-–—📍🏖🏝👥⭐✨]+", "", value)
    for _ in range(12):
        new = _CARD_INTRO_SECTION_LABEL_RE.sub(" ", value)
        if new == value:
            break
        value = new
    if re.match(r"(?i)^цен[ыы]\s*:\s*\(", value):
        value = re.sub(r"(?i)^цен[ыы]\s*:\s*", "", value, count=1)
    value = re.sub(r"\s{2,}", " ", value).strip(" .,-•")
    return value


def short_location_badge(lead_lines: list[str], title: str) -> str:
    """Короткая строка для плашки: первое предложение, иначе город до запятой (короткий фрагмент), иначе усечение."""
    if not lead_lines:
        return "Абхазия"
    raw = clean_text(lead_lines[0].replace("📍", ""))
    if not raw:
        return title.split()[0] if title else "Абхазия"
    m = re.match(r"^(.+?[.!?])(?:\s|$)", raw)
    if m and len(m.group(1)) >= 8:
        return m.group(1).strip()
    if "," in raw:
        head = raw.split(",")[0].strip()
        if len(head) <= 72:
            return head
    if len(raw) > 100:
        return raw[:97].rsplit(" ", 1)[0] + "…"
    return raw


def should_show_location_under_title(lead: str, description: str) -> bool:
    """Не дублировать подзаголовок, если тот же текст уже в основном описании."""
    lead_n = re.sub(r"\s+", " ", strip_tags(lead).strip()).lower()
    desc_n = re.sub(r"\s+", " ", strip_tags(description).strip()).lower()
    if not lead_n:
        return False
    if not desc_n:
        return True
    if lead_n in desc_n:
        return False
    if len(lead_n) >= 24 and desc_n.startswith(lead_n[: min(len(lead_n), 160)]):
        return False
    return True


def description_to_prose_html(raw: str) -> str:
    """Несколько <p> для читаемости на мобильных; без смены семейств шрифтов."""
    plain = strip_gps_coordinate_clause(sanitize_listing_card_intro_text(raw))
    if not plain:
        return ""
    parts = [p.strip() for p in re.split(r"\n+", plain) if p.strip()]
    if len(parts) == 1:
        parts = [
            s.strip()
            for s in re.split(r"(?<=[\.\!\?])\s+(?=[А-ЯЁA-Z\(«\"„0-9🏖📍✔])", plain)
            if s.strip()
        ]
    if not parts:
        parts = [plain]
    parts = [p for p in parts if not _is_coordinates_noise_sentence(p)]
    parts = [p for p in parts if not is_cross_catalog_spam_plain(p)]
    if not parts:
        return ""
    inner = "".join(f"<p>{html.escape(p)}</p>" for p in parts)
    return f'<div class="hotel-card__prose">{inner}</div>'


def replace_main(text: str, new_main: str) -> str:
    return re.sub(r"(?s)<main.*?</main>", new_main, text, count=1)


def extract_index_section(text: str, anchor: str) -> str:
    match = re.search(rf'(?s)<section\b[^>]*id="{anchor}"[^>]*>.*?</section>', text)
    if not match:
        raise RuntimeError(f"Не найден section #{anchor}")
    return match.group(0)


def add_class_to_tag(markup: str, tag: str, new_class: str) -> str:
    pattern = rf"<{tag}\b([^>]*?)class=\"([^\"]*)\"([^>]*)>"

    def repl(match: re.Match[str]) -> str:
        before, current, after = match.groups()
        classes = current.split()
        if new_class not in classes:
            classes.append(new_class)
        return f'<{tag}{before}class="{" ".join(classes)}"{after}>'

    return re.sub(pattern, repl, markup, count=1)


def extract_header(text: str) -> str:
    patterns = [
        r'(?s)<section class="hotel-site-concept__intro">.*?</section>',
        r'(?s)<header class="hero section hotel-hero-v2">.*?</header>',
        r'(?s)<header class="hero section">.*?</header>',
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(0)
    raise RuntimeError("Не найден header hero")


def extract_sections(text: str) -> list[str]:
    return re.findall(r'(?s)<section class="section(?: cta-block)?[^"]*">.*?</section>', text)


def find_first(patterns: list[str], text: str) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.S)
        if match:
            return match.group(1)
    return ""


def extract_paragraphs(section: str) -> list[str]:
    return [clean_text(item) for item in re.findall(r"<p[^>]*>(.*?)</p>", section, flags=re.S) if clean_text(item)]


BENEFIT_SECTION_HEADINGS = {
    "описание",
    "территория",
    "территория и услуги",
    "номера",
    "номер",
    "в номерах",
    "домики",
    "домик",
    "дома",
    "коттеджи",
    "дом",
    "квартира",
    "квартиры",
    "в квартире",
    "апартаменты",
    "апартамент",
    "размещение",
    "расположение",
    "рядом",
    "удобства",
    "пляж",
    "цены",
    "цена",
    "условия",
    "услуги",
    "в доме",
    "на территории",
    "комнаты",
    "коттедж",
    "студия",
    "отель",
    "домики и апартаменты",
    "домики и номера",
    "домики семейные",
    "домики комфорт",
}

# Служебные вставки вида «✔территория:.» в подзаголовке и коротком описании карточки
_CARD_INTRO_SECTION_LABEL_RE = re.compile(
    r"(?:^|\s)[\u2714\u2705\u2713\u2611]?\ufe0f?\s*"
    r"(описание|территория(?:\s+и\s+услуги)?|номера|номер|в\s+номерах|"
    r"домики(?:\s+и\s+(?:апартаменты|номера)|\s+семейные|\s+комфорт)?|"
    r"домик|дома|коттеджи?|дом|квартира|квартиры|в\s+квартире|"
    r"апартаменты?|размещение|расположение|рядом|удобства|пляж|"
    r"условия|услуги|цена|цен[ыы]\*?|в\s+доме|на\s+территории|"
    r"комнаты|студия|отель)\s*:\.?\s*",
    flags=re.I,
)

_CAPS_LABEL_PARA_RE = re.compile(
    r'<p\s+class="paragraph-blocks__caps"[^>]*>(.*?)</p>',
    flags=re.I | re.S,
)

_PARAGRAPH_BLOCKS_WRAPPER_RE = re.compile(
    r'(<div\s+class="paragraph-blocks"[^>]*>)(.*?)(</div>)',
    flags=re.I | re.S,
)

_P_ANY_RE = re.compile(r"<p(\s[^>]*)?>(.*?)</p>", flags=re.I | re.S)


def _normalize_section_label_key(raw: str) -> str:
    t = sanitize_listing_card_intro_text(raw).strip(" .:,-–—•")
    t = re.sub(r"\*+", "", t)
    return t.lower().rstrip(":")


def _strip_caps_heading_ps(inner: str) -> str:
    def repl(match: re.Match[str]) -> str:
        plain = clean_text(strip_tags(match.group(1)))
        if _normalize_section_label_key(plain) in BENEFIT_SECTION_HEADINGS:
            return ""
        return match.group(0)

    return _CAPS_LABEL_PARA_RE.sub(repl, inner)


def _strip_plain_label_ps(inner: str) -> str:
    def repl(m: re.Match[str]) -> str:
        attrs = m.group(1) or ""
        body = m.group(2)
        if "paragraph-blocks__caps" in attrs:
            return m.group(0)
        plain = clean_text(strip_tags(body))
        if not plain or len(plain) > 120:
            return m.group(0)
        if _normalize_section_label_key(plain) in BENEFIT_SECTION_HEADINGS:
            return ""
        return m.group(0)

    return _P_ANY_RE.sub(repl, inner)


def _polish_paragraph_blocks_ps(inner: str) -> str:
    """Убирает эмодзи и служебные префиксы в обычных абзацах детального текста."""

    def repl(m: re.Match[str]) -> str:
        attrs = m.group(1) or ""
        body = m.group(2)
        if "paragraph-blocks__caps" in attrs:
            return m.group(0)
        plain = clean_text(strip_tags(body))
        if not plain:
            return m.group(0)
        cleaned = sanitize_listing_card_intro_text(plain)
        if cleaned == plain:
            return m.group(0)
        return f"<p{attrs}>{html.escape(cleaned)}</p>"

    return _P_ANY_RE.sub(repl, inner)


def strip_caps_label_paragraphs(section_html: str) -> str:
    """Текст карточки должен совпадать с постом Telegram — не вырезаем капс-заголовки и ярлыки секций."""

    return section_html


_KVARTIRA_CATALOG_CARD_SNIPPET_RE = re.compile(
    r'(<a class="catalog-card"[^>]*>.*?<h3>.*?</h3>\s*<p>)(.*?)(</p>\s*</a>)',
    flags=re.I | re.S,
)


def patch_kvartira_catalog_card_blurbs() -> None:
    """Чистит превью-текст в статической сетке kvartira/index.html (без правок scripts.js)."""
    path = ROOT / "kvartira" / "index.html"
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")

    def repl(m: re.Match[str]) -> str:
        plain = strip_tags(m.group(2))
        cleaned = sanitize_listing_card_intro_text(plain)
        if not cleaned:
            cleaned = "Абхазия"
        return m.group(1) + html.escape(cleaned) + m.group(3)

    new_text = _KVARTIRA_CATALOG_CARD_SNIPPET_RE.sub(repl, text)
    if new_text != text:
        path.write_text(new_text, encoding="utf-8")

PROMISE_HINTS = (
    "уют",
    "тих",
    "спокойн",
    "зелен",
    "сад",
    "двор",
    "семейн",
    "отдых",
    "подойд",
    "подходит",
    "террас",
    "веранд",
    "простор",
    "укром",
    "сосны",
    "чайн",
    "бассейн",
    "завтрак",
    "кафе",
)

PRACTICAL_HINTS = (
    "минут",
    "пляж",
    "море",
    "этаж",
    "лифт",
    "спальн",
    "кровать",
    "диван",
    "кухн",
    "столов",
    "сануз",
    "душ",
    "стирал",
    "парков",
    "wi-fi",
    "wifi",
    "интернет",
    "кондиционер",
    "сплит",
    "магазин",
    "рынок",
    "остановк",
    "центр",
    "балкон",
    "террас",
    "веранд",
    "холодиль",
    "телевиз",
    "чайник",
    "полотен",
    "бель",
    "трансфер",
)

EQUIPMENT_HINTS = (
    "wi-fi",
    "wifi",
    "интернет",
    "сплит",
    "кондиционер",
    "телевиз",
    "фен",
    "чайник",
    "утюг",
    "гладиль",
    "холодиль",
    "мини-бар",
    "микроволнов",
    "пылесос",
    "стираль",
    "полотен",
    "бель",
)

LEGACY_DETAIL_SECTION_TITLES = {
    "фото номеров тут",
    "дополнительное фото номеров тут",
    "фото домиков тут",
    "дополнительное фото домиков тут",
    "фото квартиры тут",
    "дополнительное фото квартиры тут",
    "фото апартаментов тут",
    "дополнительное фото апартаментов тут",
}


def split_sentences(text: str) -> list[str]:
    plain = clean_text(text)
    if not plain:
        return []
    return [
        part.strip()
        for part in re.split(r"(?<=[.!?])\s+", plain)
        if part.strip()
    ]


def _benefit_key(text: str) -> str:
    return re.sub(r"[^a-zа-яё0-9]+", " ", clean_text(text).lower()).strip()


def _benefit_sentence_keys(text: str) -> set[str]:
    return {_benefit_key(sentence) for sentence in split_sentences(text) if _benefit_key(sentence)}


def _is_benefit_heading(text: str) -> bool:
    value = clean_text(text)
    if not value:
        return True
    value = re.sub(r"^[^\wА-Яа-яЁё]+", "", value, flags=re.UNICODE).strip(" .:-")
    low = value.lower()
    if low in BENEFIT_SECTION_HEADINGS:
        return True
    return bool(re.fullmatch(r"[А-ЯЁA-Z0-9\s\-]{2,24}", value)) and len(value.split()) <= 3


def is_cross_catalog_spam_plain(plain: str) -> bool:
    """Рекламные вставки из канала («весь каталог квартир смотреть тут» и т.п.)."""
    t = clean_text(plain).casefold()
    if not t:
        return False
    if "весь каталог квартир" in t:
        return True
    if "каталог квартир" in t and "смотреть" in t:
        return True
    if "весь каталог жилья" in t:
        return True
    if "каталог жилья" in t and ("t.me" in t or "telegram" in t or "abhazbooking" in t):
        return True
    return False


def strip_cross_catalog_spam_from_markup(fragment: str) -> str:
    """Удаляет <li>/<p>, если текст — перекрёстная реклама каталога квартир/жилья."""

    def drop_li(m: re.Match[str]) -> str:
        body = m.group(2) or ""
        if is_cross_catalog_spam_plain(strip_tags(body)):
            return ""
        return m.group(0)

    def drop_p(m: re.Match[str]) -> str:
        body = m.group(2) or ""
        if is_cross_catalog_spam_plain(strip_tags(body)):
            return ""
        return m.group(0)

    out = re.sub(r"<li(\s[^>]*)?>(.*?)</li>", drop_li, fragment, flags=re.I | re.S)
    return _P_ANY_RE.sub(drop_p, out)


def normalize_benefit_text(text: str) -> str:
    value = remove_price_clauses(text)
    value = clean_text(value)
    if not value:
        return ""
    if is_cross_catalog_spam_plain(value):
        return ""
    value = re.sub(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]", "", value)
    value = value.replace("\ufe0f", "").replace("\u200d", "")
    value = re.sub(r"^[\s\u2714\u2705\u2713\u2611\ufe0f•·\-–—📍🏖🏝👥⭐✨]+", "", value)
    for _ in range(12):
        new = _CARD_INTRO_SECTION_LABEL_RE.sub(" ", value)
        if new == value:
            break
        value = new
    while True:
        match = re.match(r"^([А-ЯЁA-Z][А-Яа-яЁёA-Za-z\s\-]{0,24})\s*:\.?\s*(.+)$", value)
        if not match:
            break
        heading = match.group(1).strip().lower()
        if heading not in BENEFIT_SECTION_HEADINGS:
            break
        value = match.group(2).strip()
    value = value.strip(" .,-")
    if not value or _is_benefit_heading(value):
        return ""
    if re.fullmatch(r"\d+\s*минут(?:\s+пешком)?", value, flags=re.I):
        return ""
    value = re.sub(
        r"\bидеальный вариант для тех,\s*кто хочет\b",
        "Подойдет тем, кто хочет",
        value,
        flags=re.I,
    )
    value = re.sub(
        r"\b(ДОМИКИ|НОМЕРА|КВАРТИРА|КВАРТИРЫ|АПАРТАМЕНТЫ|КОТТЕДЖИ|ДНЕМ|ВЕЧЕРОМ)\b",
        lambda match: match.group(1).lower(),
        value,
    )
    if value[:1].islower():
        value = value[:1].upper() + value[1:]
    value = re.sub(r"\.\s*\.", ".", value)
    value = re.sub(r"\s{2,}", " ", value).strip()
    value = strip_gps_coordinate_clause(value).strip()
    if not value or _is_coordinates_noise_sentence(value):
        return ""
    if value[-1] not in ".!?":
        value += "."
    return value


def extract_benefit_paragraphs(section: str) -> list[str]:
    items: list[str] = []
    seen: set[str] = set()
    for paragraph in extract_paragraphs(section):
        normalized = normalize_benefit_text(paragraph)
        key = _benefit_key(normalized)
        if not normalized or not key or key in seen:
            continue
        seen.add(key)
        items.append(normalized)
    return items


def _limit_sentences(text: str, limit: int = 2) -> str:
    parts = split_sentences(text)
    if not parts:
        return ""
    return " ".join(parts[:limit]).strip()


def _looks_like_equipment_list(text: str) -> bool:
    low = text.lower()
    hits = sum(1 for hint in EQUIPMENT_HINTS if hint in low)
    if hits >= 2:
        return True
    return hits >= 1 and text.count(",") >= 4 and not any(hint in low for hint in PROMISE_HINTS)


def _is_promise_candidate(text: str) -> bool:
    low = text.lower()
    has_view = bool(re.search(r"красив\w*\s+вид|вид\s+на|видом\s+на|вид\s+из", low))
    return (has_view or any(hint in low for hint in PROMISE_HINTS)) and not _looks_like_equipment_list(text)


def _is_practical_candidate(text: str) -> bool:
    if _is_coordinates_noise_sentence(text):
        return False
    low = text.lower()
    return any(hint in low for hint in PRACTICAL_HINTS) or bool(re.search(r"\b\d+\b", low))


def _is_location_advantage(text: str) -> bool:
    low = text.lower()
    return bool(re.search(r"пляж|море|берег|магазин|рынок|остановк|центр|транспорт|кафе|ресторан", low))


def _append_unique_benefit(items: list[str], candidate: str, max_items: int) -> None:
    normalized = _limit_sentences(candidate, 2)
    if not normalized:
        return
    cand_key = _benefit_key(normalized)
    if not cand_key:
        return
    cand_sentences = _benefit_sentence_keys(normalized)
    for current in items:
        current_key = _benefit_key(current)
        if cand_key == current_key or cand_key in current_key or current_key in cand_key:
            return
        current_sentences = _benefit_sentence_keys(current)
        if cand_sentences and current_sentences and cand_sentences <= current_sentences:
            return
    items.append(normalized)
    del items[max_items:]


def build_listing_benefits(section_paragraph_groups: list[list[str]], lead_lines: list[str]) -> tuple[list[str], list[str]]:
    paragraphs = [item for group in section_paragraph_groups for item in group]
    why_choose_items: list[str] = []
    important_items: list[str] = []

    intro_sentences: list[str] = []
    for paragraph in section_paragraph_groups[0] if section_paragraph_groups else []:
        if _looks_like_equipment_list(paragraph):
            continue
        for sentence in split_sentences(paragraph):
            normalized = normalize_benefit_text(sentence)
            if not normalized:
                continue
            intro_sentences.append(normalized)
            if len(intro_sentences) >= 2:
                break
        if len(intro_sentences) >= 2:
            break
    if intro_sentences:
        _append_unique_benefit(why_choose_items, " ".join(intro_sentences[:2]), 2)

    for paragraph in paragraphs:
        if _looks_like_equipment_list(paragraph):
            continue
        for sentence in split_sentences(paragraph):
            normalized = normalize_benefit_text(sentence)
            if normalized and _is_promise_candidate(normalized):
                _append_unique_benefit(why_choose_items, normalized, 2)
                if len(why_choose_items) >= 2:
                    break
        if len(why_choose_items) >= 2:
            break

    if len(why_choose_items) < 2:
        for paragraph in paragraphs:
            if _looks_like_equipment_list(paragraph):
                continue
            _append_unique_benefit(why_choose_items, paragraph, 2)
            if len(why_choose_items) >= 2:
                break

    for lead in lead_lines:
        normalized = normalize_benefit_text(lead)
        if not normalized:
            continue
        for sentence in split_sentences(normalized):
            sentence = normalize_benefit_text(sentence)
            low = sentence.lower() if sentence else ""
            if sentence and "минут" in low and not re.search(r"пляж|море|центр|магазин|рынок|остановк|берег", low):
                continue
            if sentence and _is_practical_candidate(sentence):
                _append_unique_benefit(important_items, sentence, 3)
        if len(important_items) >= 3:
            break

    for paragraph in paragraphs:
        if _is_location_advantage(paragraph):
            _append_unique_benefit(important_items, paragraph, 3)
        if len(important_items) >= 3:
            break

    for paragraph in paragraphs:
        if _is_practical_candidate(paragraph) or _looks_like_equipment_list(paragraph):
            _append_unique_benefit(important_items, paragraph, 3)
        if len(important_items) >= 3:
            break

    if len(important_items) < 2:
        for paragraph in paragraphs:
            _append_unique_benefit(important_items, paragraph, 3)
            if len(important_items) >= 3:
                break

    return why_choose_items[:2], important_items[:3]


def _has_price_signal(plain: str) -> bool:
    """Абзац или фрагмент явно про тариф/деньги — убираем из описаний, переносим в «Цены»."""
    if not plain or not plain.strip():
        return False
    t = plain.strip()
    if "₽" in t:
        return True
    if re.search(r"\d[\d\s]*\s*/\s*сут", t, re.I):
        return True
    if re.search(r"\d[\d\s]*\s*руб\.?", t, re.I):
        return True
    if re.search(r"\bруб\.?\b", t, re.I) and re.search(r"\d", t):
        return True
    return False


def _is_prices_section_header(plain: str) -> bool:
    """Заголовок «ЦЕНЫ» с галочкой/эмодзи (✔️ЦЕНЫ:), без текста про суммы."""
    s = plain.strip()
    s = re.sub(r"^[^\wА-Яа-яЁё]+", "", s, flags=re.UNICODE)
    return bool(re.match(r"^ЦЕНЫ\s*:?\s*$", s, re.I))


def _is_other_section_header_after_ceny(plain: str) -> bool:
    """Следующий раздел с галочкой (не «ЦЕНЫ») — конец подблока цен в обзоре."""
    if _is_prices_section_header(plain):
        return False
    s = plain.strip()
    if not s:
        return False
    for ch in ("\u2714", "\u2705", "\u2713", "\u2611"):
        if s.startswith(ch):
            return True
    return s.startswith("✔")


def _should_stop_ceny_tail_paragraph(plain: str) -> bool:
    """Длинный абзац после списка категорий (не тарифная строка) — оставляем в обзоре."""
    if len(plain) > 200:
        return True
    if re.search(r"\bсобач|предварительн\w+\s+соглас", plain, re.I):
        return True
    if plain.count(".") >= 2 and len(plain) > 90:
        return True
    return False


def _is_room_category_header_line(plain: str) -> bool:
    """Подписи категорий номеров из поста — не строки тарифа, не блок «Цены»."""
    p = (plain or "").strip()
    if not p or len(p) > 96:
        return False
    if re.search(r"\d", p):
        return False
    low = p.lower().rstrip(".: ")
    if low in {"номера", "номер", "домики", "домик", "коттеджи", "коттедж", "апартаменты", "студии"}:
        return True
    if re.match(
        r"^(домики|номера|коттеджи|апартаменты)\s+"
        r"(семейн\w*|комфорт\w*|эконом\w*|стандарт\w*|люкс\w*|студи\w*)$",
        low,
    ):
        return True
    if re.match(r"^(номера|домики|коттеджи)\s+(эконом|комфорт|стандарт|люкс)$", low):
        return True
    if re.match(r"^номер(а)?\s+(эконом|комфорт|стандарт|люкс|делюкс|апарт|студи)\b", low):
        return True
    if re.match(r"^(эконом|комфорт|стандарт|люкс)(\s+номер(а)?)?$", low):
        return True
    if low in {"номера эконом", "номера комфорт", "номер эконом", "номер комфорт"}:
        return True
    return False


def strip_ceny_subsection_from_section_html(section_html: str) -> tuple[str, list[str]]:
    """Убирает из текста секции блок от «✔️ЦЕНЫ:» до следующего ✔️-раздела или до длинного абзаца."""
    extracted: list[str] = []
    if "ЦЕНЫ" not in section_html:
        return section_html, extracted

    match = re.search(
        r'<p[^>]*>[^<]{0,48}ЦЕНЫ\s*:?\s*</p>',
        section_html,
        flags=re.I | re.S,
    )
    if not match:
        return section_html, extracted

    start = match.start()
    after_header = section_html[match.end() :]
    remove_end = match.end()
    pos = 0
    while True:
        m = re.search(r"<p[^>]*>(.*?)</p>", after_header[pos:], flags=re.S)
        if not m:
            break
        plain = strip_tags(m.group(1)).strip()
        abs_start = pos + m.start()
        abs_end = pos + m.end()
        if _is_other_section_header_after_ceny(plain):
            break
        if _should_stop_ceny_tail_paragraph(plain):
            break
        if _is_prose_paragraph_keep_with_price_mention(plain):
            break
        if plain:
            if not _is_room_category_header_line(plain):
                extracted.append(clean_text(plain))
        remove_end = match.end() + abs_end
        pos = abs_end

    cleaned = section_html[:start] + section_html[remove_end:]
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned, extracted


def normalize_for_price_dedup(s: str) -> str:
    return re.sub(r"\s+", " ", strip_tags(s).lower()).strip()


def remove_price_clauses(text: str) -> str:
    """Убирает предложения/части с ценами; если вся строка про цены — пусто."""
    t = clean_text(text)
    if not t:
        return ""
    if _is_prose_paragraph_keep_with_price_mention(t):
        return t
    if not _has_price_signal(t):
        return t
    parts = re.split(r"(?<=[.!?])\s+", t)
    kept = [p for p in parts if p.strip() and not _has_price_signal(p)]
    out = " ".join(kept).strip()
    return out if out else ""


def strip_paragraphs_price_from_section_html(section_html: str) -> tuple[str, list[str]]:
    """Удаляет из HTML секции <p> с ценами и заголовок ✔️ЦЕНЫ:; возвращает строки для переноса в блок «Цены»."""
    extracted: list[str] = []

    def repl(match: re.Match[str]) -> str:
        inner = match.group(1)
        plain = strip_tags(inner).strip()
        if not plain:
            return ""
        if _is_prices_section_header(plain):
            return ""
        if _has_price_signal(plain):
            if _is_prose_paragraph_keep_with_price_mention(plain):
                return match.group(0)
            extracted.append(clean_text(plain))
            return ""
        return match.group(0)

    out = re.sub(r"<p[^>]*>(.*?)</p>", repl, section_html, flags=re.S)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out, extracted


def extract_list_items(section: str) -> list[str]:
    return [clean_text(item) for item in re.findall(r"<li[^>]*>(.*?)</li>", section, flags=re.S) if clean_text(item)]


def extract_section_heading_text(section_html: str) -> str:
    return clean_text(find_first([r"<h2[^>]*>(.*?)</h2>"], section_html))


def is_legacy_detail_heading(title: str) -> bool:
    return clean_text(title).casefold() in LEGACY_DETAIL_SECTION_TITLES


def merge_section_into_paragraph_blocks(base_section: str, extra_section: str) -> str:
    extra_block = find_first([r'(?s)<div class="paragraph-blocks">(.*?)</div>'], extra_section)
    if not extra_block:
        return base_section
    extra_inner = re.sub(r'^\s*<p[^>]*>\s*</p>\s*', "", extra_block, flags=re.S)
    if not extra_inner.strip():
        return base_section

    def repl(match: re.Match[str]) -> str:
        current = match.group(1).rstrip()
        spacer = "\n" if current else ""
        return f'<div class="paragraph-blocks">{current}{spacer}{extra_inner}\n          </div>'

    return re.sub(
        r'(?s)<div class="paragraph-blocks">(.*?)</div>',
        repl,
        base_section,
        count=1,
    )


def merge_legacy_detail_sections(content_sections: list[str]) -> list[str]:
    merged: list[str] = []
    for section in content_sections:
        heading = extract_section_heading_text(section)
        should_merge = bool(merged) and (not heading or is_legacy_detail_heading(heading))
        if should_merge:
            merged[-1] = merge_section_into_paragraph_blocks(merged[-1], section)
        else:
            merged.append(section)
    return merged


def extract_links(section: str) -> list[tuple[str, str]]:
    links = []
    for href, label in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', section, flags=re.S):
        clean_label = clean_text(label)
        if href and clean_label:
            links.append((href, clean_label))
    return links


def extract_images(section: str) -> list[tuple[str, str]]:
    return re.findall(r'<img[^>]+src="([^"]+)"[^>]+alt="([^"]*)"', section, flags=re.S)


def extract_reviews(section: str) -> list[tuple[str, str, str]]:
    reviews = []

    for head, text in re.findall(
        r'(?s)<div class="review-item">.*?<p class="review-head">(.*?)</p>.*?<p class="review-text">(.*?)</p>',
        section,
    ):
        title = clean_text(head)
        body = clean_text(text)
        if title and body:
            reviews.append((title, "Гость", body))

    if reviews:
        return reviews[:3]

    for top, body in re.findall(r'(?s)<article class="review-card">.*?<div class="review-card__top">(.*?)</div>.*?<p>(.*?)</p>', section):
        parts = re.findall(r"<strong>(.*?)</strong>|<span>(.*?)</span>", top)
        author = ""
        kind = "Гость"
        for strong, span in parts:
            if strong and not author:
                author = clean_text(strong)
            if span and kind == "Гость":
                kind = clean_text(span)
        body_text = clean_text(body)
        if author and body_text:
            reviews.append((author, kind, body_text))

    return reviews[:3]


# Цена «число ₽/…» в начале строки, затем тире и период/условия
_PRICE_LEADING = re.compile(
    r"^\s*(\d[\d\s]*\s*(?:₽|руб\.?)(?:/[^\s–—-]+)?)\s*[-–—]\s*(.+)\s*$",
    re.IGNORECASE | re.DOTALL,
)
# Редко: описание — цена в конце (например доп. место)
_PRICE_TRAILING = re.compile(
    r"^\s*(.+?)\s*[-–—]\s*(\d[\d\s]*\s*(?:₽|руб\.?)(?:/[^\s–—-]+)?)\s*$",
    re.IGNORECASE | re.DOTALL,
)
_MONTHS_RE = re.compile(
    r"(январ[ьяе]?|феврал[ьяе]?|март[ае]?|апрел[ьяе]?|ма[йяе]|июн[ьяе]?|июл[ьяе]?|август[ае]?|сентябр[ьяе]?|октябр[ьяе]?|ноябр[ьяе]?|декабр[ьяе]?)",
    re.IGNORECASE,
)


def bold_months_in_tail(tail: str) -> str:
    """Жирным только слова месяцев; остальное (условия, числа) — обычный текст."""
    out: list[str] = []
    pos = 0
    for m in _MONTHS_RE.finditer(tail):
        out.append(html.escape(tail[pos : m.start()]))
        out.append(f"<strong>{html.escape(m.group(1))}</strong>")
        pos = m.end()
    out.append(html.escape(tail[pos:]))
    return "".join(out)


def bold_digits_outside_tags(fragment: str) -> str:
    """Оборачивает числовые группы в <strong>, не затрагивая уже вставленные теги."""
    if not fragment:
        return ""
    parts = re.split(r"(<[^>]+>)", fragment)
    out: list[str] = []
    for part in parts:
        if part.startswith("<") and part.endswith(">"):
            out.append(part)
            continue
        out.append(
            re.sub(
                r"(\d[\d\s\u00a0,.]*\d|\d+)",
                r"<strong>\1</strong>",
                part,
            )
        )
    return "".join(out)


def line_has_month_name(text: str) -> bool:
    return bool(_MONTHS_RE.search(text or ""))


def price_season_li_class_attr(text: str) -> str:
    return ' class="price-card__season-line"' if line_has_month_name(text) else ""


def format_price_season_li_html(plain: str) -> str:
    plain = (plain or "").strip()
    return f"<li{price_season_li_class_attr(plain)}>{format_price_line_to_html(plain)}</li>"


def format_price_line_to_html(text: str) -> str:
    """Сумма жирным, месяцы жирным; условия обычным текстом."""
    text = (text or "").strip()
    if not text:
        return ""

    m = _PRICE_LEADING.match(text)
    if m:
        amount, tail = m.group(1).strip(), m.group(2).strip()
        tail_html = bold_digits_outside_tags(bold_months_in_tail(tail))
        return (
            f'<strong class="price-card__amount">{html.escape(amount)}</strong> - '
            f"{bold_months_in_tail(tail)}"
        )

    m = _PRICE_TRAILING.match(text)
    if m:
        desc, amount = m.group(1).strip(), m.group(2).strip()
        return f"{html.escape(desc)} - " f'<strong class="price-card__amount">{html.escape(amount)}</strong>'

    m_plus = re.match(r"^(.+?)\s*\+\s*(\d[\d\s]*\s*(?:₽|руб\.?))\s*$", text, re.I)
    if m_plus:
        left, right = m_plus.group(1).strip(), m_plus.group(2).strip()
        left_html = bold_digits_outside_tags(html.escape(left))
        return f"{left_html} + " f'<span class="price-card__amount">{html.escape(right)}</span>'

    return bold_digits_outside_tags(html.escape(text))


def _is_prose_paragraph_keep_with_price_mention(plain: str) -> bool:
    """Длинное описание локации/питания/инфраструктуры с разовым «от N₽/завтрак» — остаётся в тексте, не в «Цены»."""
    plain = (plain or "").strip()
    if len(plain) < 85 or "₽" not in plain:
        return False
    if is_seasonal_price_line(plain):
        return False
    if _PRICE_LEADING.match(plain) or _PRICE_TRAILING.match(plain):
        return False
    if re.search(r"\d[\d\s]*\s*/\s*сут", plain, re.I):
        return False
    low = plain.lower()
    if re.match(r"^доп(\.|олнительн)", low) or re.match(r"^дети\b", low):
        return False
    food_or_walk = re.search(
        r"столов|кафе|завтрак|обед|ужин|меню|пита|рыноч|рынок|магазин|шашлык|чебур|экскурс|"
        r"ходьб|пеш[а-я]*|доступност|минут[^.]{0,40}до|окрест|инфраструкт|рядом\s+работ",
        low,
    )
    if food_or_walk:
        return True
    return False


def is_seasonal_price_line(plain: str) -> bool:
    """Сезонные строки «цена — месяц»; остальное — особые условия (доп. место, дети, примечания)."""
    plain = (plain or "").strip()
    if not plain:
        return False
    if plain.startswith("("):
        return False
    low = plain.lower()
    # Промо/служебные подписи не являются сезонными ярлыками.
    if any(token in low for token in ("акция", "подар", "забронируй", "скидк")):
        return False
    if re.match(r"^\(?указан", low):
        return False
    if _PRICE_TRAILING.match(plain):
        return False
    if low.startswith("дети") or low.startswith("доп"):
        return False
    # Отдельные ярлыки месяцев/сезона (без цены) должны идти в price-card__seasons.
    if _MONTHS_RE.search(plain):
        return True
    m = _PRICE_LEADING.match(plain)
    if m:
        tail = m.group(2)
        return bool(_MONTHS_RE.search(tail) or _MONTHS_RE.search(plain))
    if re.search(r"\d[\d\s]*\s*/\s*сутки", plain, re.I) and _MONTHS_RE.search(plain):
        return True
    if ("₽" in plain or "руб" in low) and _MONTHS_RE.search(plain):
        return True
    return False


def split_price_card_seasons_notes(section: str) -> str:
    """Заголовок ЦЕНЫ:; два списка — сезоны и особые условия."""
    if not section or "price-card" not in section:
        return section
    if "price-card__seasons" in section:
        if "price-card__heading" not in section:
            section = re.sub(
                r'<h2[^>]*>\s*Цены\s*</h2>',
                '<h2 class="price-card__heading">ЦЕНЫ:</h2>',
                section,
                count=1,
                flags=re.I,
            )
        return section

    section = re.sub(
        r'<h2[^>]*>\s*Цены\s*</h2>',
        '<h2 class="price-card__heading">ЦЕНЫ:</h2>',
        section,
        count=1,
        flags=re.I,
    )
    if "price-card__heading" not in section:
        section = re.sub(
            r'<h2[^>]*>\s*ЦЕНЫ:?\s*</h2>',
            '<h2 class="price-card__heading">ЦЕНЫ:</h2>',
            section,
            count=1,
            flags=re.I,
        )

    ul_match = re.search(r"<ul[^>]*>(.*?)</ul>", section, flags=re.S)
    if not ul_match:
        return section

    items = re.findall(r"<li[^>]*>(.*?)</li>", ul_match.group(1), flags=re.S)
    seasons: list[str] = []
    notes: list[str] = []
    for raw_inner in items:
        inner = raw_inner.strip()
        if not inner:
            continue
        plain = strip_tags(inner).strip()
        if not plain:
            continue
        if _is_room_category_header_line(plain):
            continue
        if is_seasonal_price_line(plain):
            seasons.append(format_price_season_li_html(plain))
        else:
            notes.append(f"<li>{inner}</li>")

    seasons_block = (
        f'<ul class="price-card__seasons">\n{"".join(seasons)}\n</ul>' if seasons else '<ul class="price-card__seasons"></ul>'
    )
    notes_block = (
        f'<ul class="price-card__notes" aria-label="Особые условия">\n{"".join(notes)}\n</ul>' if notes else ""
    )
    replacement = seasons_block + ("\n" + notes_block if notes_block else "")
    return section[: ul_match.start()] + replacement + section[ul_match.end() :]


def _append_li_chunks_to_ul(html: str, ul_class: str, chunks: list[str]) -> str:
    if not chunks:
        return html
    pat = rf'(<ul class="{re.escape(ul_class)}"[^>]*>)([\s\S]*?)(</ul>)'
    m = re.search(pat, html)
    if not m:
        return html
    insert = m.group(2).rstrip() + "\n" + "\n".join(chunks) + "\n"
    return html[: m.start()] + m.group(1) + insert + m.group(3) + html[m.end() :]


def reformat_price_card_content(section: str) -> str:
    """Перестраивает пункты списка и тизер «от …»: цена / месяцы без лишнего strong."""
    if not section or "price-card" not in section:
        return section

    def li_repl(match: re.Match) -> str:
        inner = match.group(1)
        plain = strip_tags(inner).strip()
        if not plain:
            return match.group(0)
        return format_price_season_li_html(plain)

    updated = re.sub(r"<li[^>]*>(.*?)</li>", li_repl, section, flags=re.S)

    def teaser_repl(match: re.Match) -> str:
        inner = match.group(1)
        plain = strip_tags(inner).strip()
        if not plain:
            return match.group(0)
        formatted = format_price_line_to_html(plain)
        return (
            f'<p class="price-card__teaser">'
            f'<span class="price-box__label">от</span> '
            f"{formatted}"
            f"</p>"
        )

    updated = re.sub(
        r'<p class="price-card__teaser"[^>]*>\s*<span class="price-box__label">от</span>\s*(.*?)\s*</p>',
        teaser_repl,
        updated,
        flags=re.S,
    )
    return updated


def cleanup_misplaced_prose_in_price_section(section: str) -> str:
    """Убирает из блока «Цены» тизер и пункты, которые на самом деле описание инфраструктуры/питания."""
    if not section or "price-card" not in section:
        return section

    def drop_teaser(m: re.Match[str]) -> str:
        full = m.group(0)
        plain = clean_text(strip_tags(full))
        if plain.lower().startswith("от "):
            plain = plain[3:].strip()
        if _is_prose_paragraph_keep_with_price_mention(plain):
            return ""
        return full

    section = re.sub(r'<p class="price-card__teaser"[^>]*>.*?</p>', drop_teaser, section, flags=re.S)

    def drop_li(match: re.Match[str]) -> str:
        inner = match.group(1)
        plain = clean_text(strip_tags(inner))
        if not plain:
            return match.group(0)
        if _is_room_category_header_line(plain):
            return ""
        if _is_prose_paragraph_keep_with_price_mention(plain):
            return ""
        return match.group(0)

    return re.sub(r"<li[^>]*>(.*?)</li>", drop_li, section, flags=re.S)


def _reflow_price_card_inner_tariff_groups(inner: str) -> str:
    """Форматирует строки в каждом ul сезонов/примечаний, не смешивая тарифные группы."""

    def repl_season_ul(match: re.Match[str]) -> str:
        open_tag, ul_body, close_tag = match.group(1), match.group(2), match.group(3)
        lis_out: list[str] = []
        for raw_inner in re.findall(r"<li[^>]*>(.*?)</li>", ul_body, flags=re.S):
            plain = clean_text(strip_tags(raw_inner))
            if not plain or _is_room_category_header_line(plain):
                continue
            lis_out.append(format_price_season_li_html(plain))
        body = "\n".join(f"            {x}" for x in lis_out)
        return f"{open_tag}\n{body}\n          {close_tag}"

    updated = re.sub(
        r'(<ul class="price-card__seasons"[^>]*>)([\s\S]*?)(</ul>)',
        repl_season_ul,
        inner,
        flags=re.S,
    )

    def repl_notes_ul(match: re.Match[str]) -> str:
        open_tag, ul_body, close_tag = match.group(1), match.group(2), match.group(3)
        lis_out: list[str] = []
        for raw_inner in re.findall(r"<li[^>]*>(.*?)</li>", ul_body, flags=re.S):
            plain = clean_text(strip_tags(raw_inner))
            if not plain:
                continue
            lis_out.append(f"<li>{format_price_line_to_html(plain)}</li>")
        body = "\n".join(f"            {x}" for x in lis_out)
        return f"{open_tag}\n{body}\n          {close_tag}"

    return re.sub(
        r'(<ul class="price-card__notes"[^>]*>)([\s\S]*?)(</ul>)',
        repl_notes_ul,
        updated,
        flags=re.S,
    )


def reflow_price_card_list_items(fragment: str) -> str:
    """Убирает подписи категорий номеров; подмешивает в список цену из тизера, если её не было в ul; пересобирает сезоны/примечания."""
    if "price-card" not in fragment:
        return fragment
    m = re.search(r'(<article class="card price-card">)([\s\S]*?)(</article>)', fragment, re.S)
    if not m:
        return fragment
    art_open, inner, art_close = m.group(1), m.group(2), m.group(3)
    if "price-card__tariff-group" in inner:
        new_inner = _reflow_price_card_inner_tariff_groups(inner)
        return fragment[: m.start()] + art_open + new_inner + art_close + fragment[m.end() :]
    h2_m = re.search(r"(<h2[^>]*>.*?</h2>)", inner, flags=re.S)
    h2 = h2_m.group(1) if h2_m else ""
    teaser_m = re.search(r'(<p class="price-card__teaser"[^>]*>.*?</p>)', inner, flags=re.S)
    teaser_plain = ""
    if teaser_m:
        t_inner = re.search(
            r'price-box__label[^>]*>от</span>\s*(.*?)\s*</p>',
            teaser_m.group(1),
            flags=re.S,
        )
        if t_inner:
            teaser_plain = clean_text(strip_tags(t_inner.group(1)))
    if teaser_plain and _is_prose_paragraph_keep_with_price_mention(teaser_plain):
        teaser_plain = ""

    lis_plain_order: list[str] = []
    for raw_inner in re.findall(r"<li[^>]*>(.*?)</li>", inner, flags=re.S):
        plain = clean_text(strip_tags(raw_inner))
        if not plain or _is_room_category_header_line(plain):
            continue
        lis_plain_order.append(plain)

    plains_norm = {normalize_for_price_dedup(p) for p in lis_plain_order}
    if teaser_plain:
        tn = normalize_for_price_dedup(teaser_plain)
        if tn not in plains_norm and (
            is_seasonal_price_line(teaser_plain)
            or ("₽" in teaser_plain and _MONTHS_RE.search(teaser_plain))
        ):
            lis_plain_order.insert(0, teaser_plain)

    seasons: list[str] = []
    notes: list[str] = []
    for plain in lis_plain_order:
        if is_seasonal_price_line(plain):
            seasons.append(format_price_season_li_html(plain))
        else:
            notes.append(f"<li>{format_price_line_to_html(plain)}</li>")

    seasons_block = (
        f'<ul class="price-card__seasons">\n{"".join(seasons)}\n</ul>' if seasons else "<ul class=\"price-card__seasons\"></ul>"
    )
    notes_block = (
        f'<ul class="price-card__notes" aria-label="Особые условия">\n{"".join(notes)}\n</ul>' if notes else ""
    )
    new_inner = f"\n{h2}\n{seasons_block}\n{notes_block}\n"
    return fragment[: m.start()] + art_open + new_inner + art_close + fragment[m.end() :]


def merge_extra_lines_into_price_section(price_section: str, extra_lines: list[str]) -> str:
    """Добавляет уникальные строки в список сезонов или особых условий."""
    if not price_section or not extra_lines or "price-card" not in price_section:
        return price_section
    existing = {normalize_for_price_dedup(x) for x in extract_list_items(price_section)}
    season_chunks: list[str] = []
    note_chunks: list[str] = []
    for line in extra_lines:
        plain = clean_text(line)
        if not plain:
            continue
        if _is_prose_paragraph_keep_with_price_mention(plain):
            continue
        if _is_room_category_header_line(plain):
            continue
        key = normalize_for_price_dedup(plain)
        if key in existing:
            continue
        existing.add(key)
        if is_seasonal_price_line(plain):
            season_chunks.append(format_price_season_li_html(plain))
        else:
            note_chunks.append(f"<li>{format_price_line_to_html(plain)}</li>")
    updated = price_section
    if season_chunks:
        if "price-card__seasons" in updated:
            updated = _append_li_chunks_to_ul(updated, "price-card__seasons", season_chunks)
        else:
            pos = updated.find("</ul>")
            if pos != -1:
                updated = updated[:pos] + "\n" + "\n".join(season_chunks) + updated[pos:]
    if note_chunks:
        if "price-card__notes" in updated:
            updated = _append_li_chunks_to_ul(updated, "price-card__notes", note_chunks)
        else:
            block = f'<ul class="price-card__notes" aria-label="Особые условия">\n{"".join(note_chunks)}\n</ul>'
            updated = re.sub(r"(</article>)", block + r"\n\1", updated, count=1, flags=re.S)
    return updated


def patch_price_season_line_classes_in_html(html: str) -> str:
    """Добавляет price-card__season-line на пункты сезонов с названиями месяцев."""

    def repl_season_ul(match: re.Match[str]) -> str:
        open_tag, ul_body, close_tag = match.group(1), match.group(2), match.group(3)
        lis_out: list[str] = []
        for li_match in re.finditer(r"<li([^>]*)>([\s\S]*?)</li>", ul_body):
            attrs, inner = li_match.group(1), li_match.group(2)
            plain = clean_text(strip_tags(inner))
            if line_has_month_name(plain):
                if "price-card__season-line" in attrs:
                    lis_out.append(f"<li{attrs}>{inner}</li>")
                elif re.search(r'\bclass="', attrs):
                    new_attrs = re.sub(
                        r'class="([^"]*)"',
                        lambda m: f'class="{m.group(1)} price-card__season-line"',
                        attrs,
                        count=1,
                    )
                    lis_out.append(f"<li{new_attrs}>{inner}</li>")
                else:
                    lis_out.append(f'<li class="price-card__season-line"{attrs}>{inner}</li>')
            else:
                new_attrs = re.sub(
                    r'\s*class="[^"]*\bprice-card__season-line\b[^"]*"',
                    "",
                    attrs,
                )
                lis_out.append(f"<li{new_attrs}>{inner}</li>" if new_attrs.strip() else f"<li>{inner}</li>")
        body = "\n".join(f"            {x}" for x in lis_out)
        return f"{open_tag}\n{body}\n          {close_tag}"

    return re.sub(
        r'(<ul class="price-card__seasons"[^>]*>)([\s\S]*?)(</ul>)',
        repl_season_ul,
        html,
        flags=re.S,
    )


def patch_all_object_pages_price_season_classes() -> int:
    root = Path(__file__).resolve().parents[1]
    changed = 0
    for folder in ("hotels", "kvartira"):
        for path in (root / folder).glob("*/index.html"):
            text = path.read_text(encoding="utf-8")
            if "price-card__seasons" not in text:
                continue
            new_text = patch_price_season_line_classes_in_html(text)
            if new_text != text:
                path.write_text(new_text, encoding="utf-8")
                changed += 1
    return changed


def _is_standalone_phone_line(plain: str) -> bool:
    """Строка — только номер (+7/8 и цифры), без цены и текста."""
    p = plain.strip()
    if not p:
        return False
    if "₽" in p or "руб" in p.lower():
        return False
    if not re.fullmatch(r"[\d\s\-+()]+", p):
        return False
    digits = re.sub(r"\D", "", p)
    if len(digits) < 10:
        return False
    return digits.startswith("7") or digits.startswith("8")


def strip_stray_contacts_from_price_section(section: str) -> str:
    """Удаляет из блока «Цены» контакты, продублированные из поста (не секция Контакты)."""
    if not section or "price-card" not in section:
        return section

    def li_drop(match: re.Match) -> str:
        inner = match.group(1)
        plain = strip_tags(inner).strip()
        if not plain:
            return match.group(0)
        if re.search(r"я\s+на\s+связи", plain, flags=re.I):
            return ""
        if _is_standalone_phone_line(plain):
            return ""
        return match.group(0)

    return re.sub(r"<li[^>]*>(.*?)</li>", li_drop, section, flags=re.S)


def first_price_highlight(section: str) -> str:
    """Первая строка с ценой для «от …» — из списка или существующего тизера."""
    for raw in extract_list_items(section):
        plain_li = clean_text(strip_tags(raw))
        if _is_prose_paragraph_keep_with_price_mention(plain_li):
            continue
        if "₽" in raw or "руб" in raw.lower() or re.search(r"\d[\d\s]*/\s*сутки", raw, re.I):
            return raw
    m = re.search(
        r'price-card__teaser[^>]*>.*?price-box__label[^>]*>от</span>\s*(.*?)\s*</p>',
        section,
        flags=re.S,
    )
    if m:
        t = strip_tags(m.group(1))
        if "₽" in t or "руб" in t.lower() or re.search(r"\d[\d\s]*/\s*сутки", t, re.I):
            return clean_text(t)
    return "Уточнить стоимость"


def inject_price_teaser(price_section: str, highlight: str) -> str:
    """Вставка строки «от …» под заголовок блока цен; без повторения слова «Цены» (оно только в h2)."""
    if not price_section or not highlight or highlight == "Уточнить стоимость":
        return price_section
    if "price-card__teaser" in price_section:
        return price_section
    m0 = re.search(r'<ul class="price-card__seasons"[^>]*>\s*<li>(.*?)</li>', price_section, flags=re.S)
    if m0:
        if normalize_for_price_dedup(highlight) == normalize_for_price_dedup(strip_tags(m0.group(1))):
            return price_section
    teaser = (
        f'\n          <p class="price-card__teaser">'
        f'<span class="price-box__label">от</span> '
        f"{format_price_line_to_html(highlight)}"
        f"</p>\n"
    )
    updated, n = re.subn(
        r"(<h2[^>]*>.*?</h2>)",
        r"\1" + teaser,
        price_section,
        count=1,
        flags=re.S,
    )
    if n == 0:
        return price_section
    return updated


def upgrade_price_card_article(fragment: str) -> str:
    """Полный проход по блоку цен (для квартир и ручных правок)."""
    fragment = reformat_price_card_content(fragment)
    fragment = strip_stray_contacts_from_price_section(fragment)
    fragment = cleanup_misplaced_prose_in_price_section(fragment)
    fragment = reflow_price_card_list_items(fragment)
    fragment = split_price_card_seasons_notes(fragment)
    hi = first_price_highlight(fragment)
    fragment = inject_price_teaser(fragment, hi)
    return fragment


def patch_all_listing_price_cards() -> None:
    """Обновляет разметку «Цены» на всех страницах отелей и квартир."""
    for path in LISTING_PRICE_FILES:
        text = path.read_text(encoding="utf-8")
        if 'class="card price-card"' not in text:
            continue

        def repl(m: re.Match[str]) -> str:
            return upgrade_price_card_article(m.group(0))

        new_text, n = re.subn(
            r'(?s)<article class="card price-card">.*?</article>',
            repl,
            text,
            count=1,
        )
        if n and new_text != text:
            path.write_text(clean_html_block(new_text) + "\n", encoding="utf-8")


def build_homepage() -> None:
    text = INDEX_FILE.read_text(encoding="utf-8")
    catalog_section = add_class_to_tag(extract_index_section(text, "catalog"), "section", "site-concept__catalog")
    reviews_section = add_class_to_tag(extract_index_section(text, "reviews"), "section", "site-concept__reviews")
    contacts_section = add_class_to_tag(extract_index_section(text, "contacts"), "section", "site-concept__contacts")

    new_main = f"""<main class="page-shell site-concept site-concept--home">
  <div class="bg-blur bg-blur--mint" aria-hidden="true"></div>
  <div class="bg-blur bg-blur--sand" aria-hidden="true"></div>

  <header class="site-concept__topbar" role="banner">
    <a class="site-concept__brand" href="#search">
      <img class="site-concept__brand-mark" src="media/branding/logo-emblem-160.png" width="80" height="80" alt="АБХАЗБЕРЕГ - жилье напрямую — на главную" decoding="async" />
      <span class="site-concept__brand-copy">
        <strong>АБХАЗБЕРЕГ - жилье напрямую</strong>
      </span>
    </a>

    <nav class="site-concept__topnav" aria-label="Основная навигация">
      <a href="#search">Подбор жилья</a>
      <a href="/blog/kak-vybrat-kurort-abkhaziya-pervyy-raz/">Для тех, кто едет впервые</a>
      <a href="#guide">Как бронировать</a>
      <a href="/blog/">Полезно узнать</a>
      <a href="#contacts">Контакты</a>
    </nav>

  </header>

  <div class="site-concept__masthead" aria-hidden="true">
    <div class="site-concept__masthead-bg" aria-hidden="true">
      <picture>
        <source type="image/webp" srcset="media/branding/hero-banner-2400.webp 2400w, media/branding/hero-banner-3200.webp 3200w" sizes="(max-width: 1540px) 100vw, 1540px" />
        <img class="site-concept__masthead-photo" src="media/branding/hero-banner-2400.jpg" width="2400" height="796" alt="" decoding="async" fetchpriority="high" />
      </picture>
      <div class="site-concept__masthead-fade"></div>
    </div>
  </div>

  <section class="site-concept__hero-card">
    <div class="site-concept__hero-copy">
      <div class="site-concept__eyebrow">Бронирование и подбор отелей в Абхазии</div>
      <div class="site-concept__hero-title-block">
      <h1>АБХАЗБЕРЕГ - жилье напрямую</h1>
      <p class="site-concept__hero-tagline">живая картотека проверенного жилья в Абхазии</p>
      </div>
      <div class="site-concept__hero-media-column">
        <div class="site-concept__hero-video">
          <video class="site-concept__hero-video-player" controls playsinline webkit-playsinline preload="none" poster="https://storage.yandexcloud.net/abhazbereg-media/media/branding/darya-expert-portrait.jpg" data-defer-load="1" data-high-src="https://chnyazvybzzryduhgopa.supabase.co/storage/v1/object/public/site-media/videos/hero/darya-intro-vertical-high.mp4" data-low-src="https://chnyazvybzzryduhgopa.supabase.co/storage/v1/object/public/site-media/videos/hero/darya-intro-vertical-low.mp4">
            Ваш браузер не поддерживает воспроизведение видео.
          </video>
        </div>
        <div class="site-concept__host-intro">
          <p class="site-concept__host-intro-text">
            Всем привет, меня зовут Дарья. Когда-то я сама приехала в Абхазию как турист, а теперь - влюбляю вас в Абхазию, в республику, которую сложно описать - лишь прочувствовать! На страницах этого сайта вы найдете варианты проверенного лично мной жилья, а так же можете воспользоваться бесплатным подбором и консультацией в чате. Давайте начнем выбирать!
          </p>
        </div>
      </div>

      <div class="site-concept__social-stats" role="list">
        <a aria-label="Telegram: 13 900 подписчиков, открыть канал" class="site-concept__social-stat" href="https://t.me/abhazbooking" rel="noopener noreferrer" role="listitem" target="_blank">
          <span aria-hidden="true" class="site-concept__social-stat-icon site-concept__social-stat-icon--tg">
            <svg aria-hidden="true" fill="none" height="28" viewBox="0 0 24 24" width="28" xmlns="http://www.w3.org/2000/svg"><path d="M21.5 5.2 3.4 11.9c-1.1.4-1.1 1-.2 1.3l4.6 1.4 1.8 5.5c.2.6.9.8 1.4.4l2.5-2 4.3 3.2c.8.4 1.7.2 2-.6l3-14.2c.4-1.6-.6-2.3-1.8-1.7Z" fill="#fff"/></svg>
          </span>
          <strong>13&#8239;900</strong>
          <span class="site-concept__social-stat-label">подписчиков</span>
        </a>
        <a aria-label="ВКонтакте: 42 000 участников" class="site-concept__social-stat" href="https://vk.com/abhazbereg" rel="noopener noreferrer" role="listitem" target="_blank">
          <span aria-hidden="true" class="site-concept__social-stat-icon site-concept__social-stat-icon--vk">
            <svg aria-hidden="true" fill="none" height="24" viewBox="0 0 24 24" width="24" xmlns="http://www.w3.org/2000/svg"><path d="M15.7 0H8.3C2.8 0 0 2.8 0 8.3v7.4C0 22.2 2.8 24 8.3 24h7.4c5.5 0 8.3-1.8 8.3-7.3V8.3C24 2.8 21.2 0 15.7 0zm4.1 17.3h-1.7c-.7 0-.9-.5-2-1.7-1-1-1.5-1.2-1.7-1.2-.4 0-.5.1-.5.6v1.6c0 .4-.1.7-1.2.7-1.9 0-4-1.1-5.5-3.2-2.2-3.1-2.8-5.2-2.8-5.6 0-.2.2-.5.6-.5h1.7c.4 0 .6.2.8.7.8 2.5 2.3 4.6 2.9 4.6.2 0 .3-.1.3-.7V9.7c-.1-1.2-.7-1.3-.7-1.7 0-.2.2-.4.4-.4h2.7c.3 0 .4.2.4.5v4c0 .3.1.5.3.5.2 0 .3-.1.6-.3 1-1.1 1.7-2.9 1.7-2.9.2-.3.3-.5.7-.5h1.7c.5 0 .6.3.5.7-.2.9-2.1 3.6-2.1 3.6-.2.3-.3.4 0 .7.2.3.7.8.9 1.3.6 1 1.1 2.1 1.2 2.8.1.4-.1.7-.5.7z" fill="#fff"/></svg>
          </span>
          <strong>42&#8239;000</strong>
          <span class="site-concept__social-stat-label">участников</span>
        </a>
        <a aria-label="MAX: 5 500 участников" class="site-concept__social-stat" href="https://max.ru/abhazbereg" rel="noopener noreferrer" role="listitem" target="_blank">
          <span aria-hidden="true" class="site-concept__social-stat-icon site-concept__social-stat-icon--max">
            <svg aria-hidden="true" fill="none" height="26" viewBox="0 0 24 24" width="26" xmlns="http://www.w3.org/2000/svg"><path d="M7 10c0-1.1.9-2 2-2h6c1.1 0 2 .9 2 2v3c0 1.1-.9 2-2 2h-2.5l-2.2 2.2c-.4.4-1 .1-1-.5V15H9c-1.1 0-2-.9-2-2v-3Z" fill="#fff"/></svg>
          </span>
          <strong>5&#8239;500</strong>
          <span class="site-concept__social-stat-label">участников</span>
        </a>
      </div>

      <div class="site-concept__hero-highlights">
        <article class="site-concept__benefit-card">
          <h3 class="site-concept__benefit-title">Выгода 1. Только проверенное жилье</h3>
          <div class="site-concept__benefit-body">
            <p>Все объекты в каталоге жилья проверены лично мной. Я езжу в отели, смотрю номера, территорию, пляжи, общаюсь с владельцами и персоналом, снимаю подробные видео. Если объект не развивается, не заботится о гостях или не соответствует заявленному уровню, я с ними больше не работаю.</p>
          </div>
        </article>
        <article class="site-concept__benefit-card">
          <h3 class="site-concept__benefit-title">Выгода 2. Цены всегда без накруток</h3>
          <div class="site-concept__benefit-body">
            <p>Любые расценки на размещение всегда точь-в-точь с ценами прямого бронирования. Это мое правило.</p>
            <p>Более того, я первая публикую в соцсетях информацию о горящих окошках, снижении цен и раннем бронировании. Если нашли дешевле — напишите!</p>
          </div>
        </article>
        <article class="site-concept__benefit-card">
          <h3 class="site-concept__benefit-title">Выгода 3. Сопровождение от брони до выезда</h3>
          <div class="site-concept__benefit-body">
            <p>Я оказываю сопровождение по любым вопросам, связанным с самостоятельным путешествием. Я не исчезаю после бронирования, остаюсь на связи.</p>
            <p>В разделе <a href="/blog/">Полезно узнать</a> вы найдете полезные статьи обо всем, что связано с поездкой в Абхазию, либо напишите мне сразу в чат, я подскажу где что и как.</p>
          </div>
        </article>
      </div>
    </div>
  </section>

  <section class="site-concept__section-block" id="stays">
      <nav class="site-concept__filter-pills" aria-label="Быстрые подборки">
        <a class="is-active" href="#catalog">Все</a>
        <a href="/podborki/dvuhkomnatnye-i-bolee/">Двухкомнатные</a>
        <a href="/podborki/basseyn-vse-varianty/">С бассейном</a>
        <a href="/podborki/bereg-morya-oteli-na-beregu/">У моря</a>
        <a href="/podborki/varianty-dorozhe-12-tr-premium/">Премиум</a>
      </nav>

    <div class="site-concept__search-surface" id="search">
      <form class="site-concept__search-bar" id="home-search-form">
        <label class="site-concept__search-field site-concept__search-field--wide">
          <span>Куда едем</span>
          <select id="search-city" name="city">
            <option value="">Любой город</option>
          </select>
        </label>
        <label class="site-concept__search-field">
          <span>Заезд</span>
          <input id="search-checkin" name="checkin" type="date" />
        </label>
        <label class="site-concept__search-field">
          <span>Выезд</span>
          <input id="search-checkout" name="checkout" type="date" />
        </label>
        <label class="site-concept__search-field">
          <span>Гости</span>
          <input id="search-guests" max="12" min="1" name="guests" type="number" value="2" />
        </label>
        <label class="site-concept__search-field">
          <span>До пляжа</span>
          <select id="search-distance" name="distance">
            <option value="">Любое</option>
            <option value="beachfront">Береговая зона</option>
            <option value="up-to-5">До 5 минут</option>
            <option value="up-to-10">До 10 минут</option>
            <option value="over-10">Более 10 минут</option>
          </select>
        </label>
        <label class="site-concept__search-field">
          <span>Пляж</span>
          <select id="search-beach" name="beach">
            <option value="">Любой</option>
            <option value="sand">Песчаный</option>
            <option value="pine-pebble">Сосновый галечный</option>
            <option value="mixed">Мелкая галька и песок</option>
            <option value="pebble">Галечный</option>
          </select>
        </label>
        <label class="site-concept__search-field">
          <span>Бюджет</span>
          <select id="search-price" name="price">
            <option value="">Любой</option>
            <option value="economy">Эконом и комфорт до 5000</option>
            <option value="midrange">Средний бюджет до 10000</option>
            <option value="premium">Премиум-сегмент</option>
          </select>
        </label>
        <button class="btn-book site-concept__search-submit" type="submit">Найти варианты</button>
      </form>

      <div class="site-concept__search-tags">
        <span>Проверенные хозяева</span>
        <span>Поддержка от брони до выезда</span>
        <span>Цены напрямую</span>
      </div>
    </div>

    {catalog_section}
  </section>

  <section class="site-concept__section-block" id="guide">
    <div class="site-concept__section-head">
      <div>
        <p class="site-concept__eyebrow">Как бронировать</p>
        <h2>Как найти жильё в Абхазии без утомительного поиска и переплат</h2>
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
        <a class="btn-book site-concept__guide-cta-btn" href="#contacts">Написать мне</a>
      </div>
    </div>
  </section>

  {reviews_section}
  {HOME_SOCIAL_STATS_STRIP}
  {contacts_section}
</main>"""

    rebuilt = replace_main(text, new_main)
    if "scripts.js" not in rebuilt:
        rebuilt = rebuilt.replace("</body>", '  <script src="scripts.min.js?v=202607111837" defer></script>\n</body>')
    INDEX_FILE.write_text(clean_html_block(rebuilt) + "\n", encoding="utf-8")


def build_listing_pages() -> None:
    index_src = INDEX_FILE.read_text(encoding="utf-8")
    listing_contacts_section = add_class_to_tag(
        extract_index_section(index_src, "contacts"),
        "section",
        "site-concept__contacts",
    )

    for path in LISTING_PRICE_FILES:
        text = path.read_text(encoding="utf-8")

        header_html = extract_header(text)
        section_matches = extract_sections(text)
        if not section_matches:
            continue

        media_section = ""
        price_section = ""
        reviews_section = ""
        faq_section = ""
        content_sections: list[str] = []

        for section in section_matches:
            if "hotel-media-section" in section:
                media_section = section
            elif "class=\"card price-card\"" in section:
                price_section = section
            elif "<h2>Отзывы</h2>" in section:
                reviews_section = section
            elif "faq-card" in section:
                faq_section = section
            elif "cta-block" in section:
                continue
            else:
                content_sections.append(section)

        title = clean_text(find_first([r"<h1>(.*?)</h1>"], header_html))
        if not title:
            title = clean_text(
                find_first(
                    [
                        r'<div class="hotel-card__header-main">\s*<h2>(.*?)</h2>',
                        r'<div class="hotel-card__header">\s*<div[^>]*>\s*<h2>(.*?)</h2>',
                    ],
                    text,
                )
            )
        if not title:
            raw_t = find_first([r"<title>(.*?)</title>"], text)
            title = clean_text(re.sub(r"\s*[—–]\s*обзор.*$", "", raw_t, flags=re.I))
        lead_raw = find_first(
            [
                r'<p class="lead">(.*?)</p>',
                r'<h1>.*?</h1>\s*<p>(.*?)</p>',
            ],
            header_html,
        )
        if not lead_raw:
            lead_raw = find_first([r'<p class="location">(.*?)</p>'], text)
        lead_text = format_lead_text(lead_raw)
        lead_text_clean = remove_price_clauses(lead_text)
        if lead_text_clean:
            lead_text = lead_text_clean
        lead_text = sanitize_listing_card_intro_text(lead_text)
        lead_text = strip_gps_coordinate_clause(lead_text)
        lead_lines = [clean_text(part) for part in re.split(r"[•\n]", lead_text) if clean_text(part)]

        extra_price_from_prose: list[str] = []
        content_sections_cleaned: list[str] = []
        for section in content_sections:
            s0, e0 = strip_ceny_subsection_from_section_html(section)
            cleaned, extra = strip_paragraphs_price_from_section_html(s0)
            extra_price_from_prose.extend(e0 + extra)
            content_sections_cleaned.append(cleaned)
        content_sections = merge_legacy_detail_sections(content_sections_cleaned)
        content_sections = [strip_caps_label_paragraphs(s) for s in content_sections]
        content_sections = [strip_cross_catalog_spam_from_markup(s) for s in content_sections]

        all_images = extract_images(media_section)
        main_image = all_images[0] if all_images else ("", title)
        thumb_images = all_images[1:4]

        section_titles = [
            clean_text(raw)
            for raw in re.findall(r"<h2>(.*?)</h2>", " ".join(content_sections), flags=re.S)
            if clean_text(raw)
        ]
        section_paragraph_groups = [extract_benefit_paragraphs(section) for section in content_sections]

        description_parts: list[str] = []
        for paragraphs in section_paragraph_groups[:2]:
            for paragraph in paragraphs[:2]:
                if paragraph and paragraph not in description_parts:
                    description_parts.append(paragraph)
        description = " ".join(description_parts[:2]) if description_parts else (remove_price_clauses(lead_text) or lead_text)
        description = strip_gps_coordinate_clause(sanitize_listing_card_intro_text(description))

        why_choose_items, important_items = build_listing_benefits(section_paragraph_groups, lead_lines)
        if not important_items and lead_lines:
            important_items = [p for p in (normalize_benefit_text(line) for line in lead_lines[:3]) if p]

        review_cards = extract_reviews(reviews_section)
        price_section = reformat_price_card_content(price_section)
        price_section = strip_stray_contacts_from_price_section(price_section)
        price_section = cleanup_misplaced_prose_in_price_section(price_section)
        price_section = reflow_price_card_list_items(price_section)
        price_section = split_price_card_seasons_notes(price_section)
        price_section = merge_extra_lines_into_price_section(price_section, extra_price_from_prose)
        price_section = cleanup_misplaced_prose_in_price_section(price_section)
        price_section = strip_cross_catalog_spam_from_markup(price_section)
        price_highlight = first_price_highlight(price_section)

        gallery_html = ""
        if main_image[0]:
            thumbs_html = "".join(
                f'<img src="{src}" alt="{alt or title}" loading="lazy" />'
                for src, alt in thumb_images
            )
            gallery_html = f"""
          <div class="hotel-card__gallery">
            <div class="hotel-card__main-photo">
              <img src="{main_image[0]}" alt="{main_image[1] or title}" loading="eager" />
              <div class="hotel-card__floating">
                <span class="pill pill--accent">Проверенный объект</span>
              </div>
            </div>
            <div class="hotel-card__thumbs">
              {thumbs_html}
            </div>
          </div>"""

        why_choose_html = "".join(f"<li>{item}</li>" for item in why_choose_items)
        important_html = "".join(f"<li>{item}</li>" for item in important_items)
        reviews_html = "".join(
            f"""<article class="review-card">
                <div class="review-card__top">
                  <strong>{author}</strong>
                  <span>{kind}</span>
                </div>
                <p>{body}</p>
              </article>"""
            for author, kind, body in review_cards
        )
        reviews_panel = ""
        if reviews_html:
            reviews_panel = (
                '<section class="reviews-panel">'
                '<div class="reviews-panel__head">'
                '<div class="reviews-summary"><span>Отзывы гостей</span>'
                "</div></div>"
                f'<div class="reviews-grid">{reviews_html}</div>'
                "</section>"
            )

        details_main = "".join(add_class_to_tag(section, "section", "hotel-site-concept__detail-section") for section in ([media_section] + content_sections if media_section else content_sections))
        price_section_ready = inject_price_teaser(price_section, price_highlight)
        details_aside = "".join(
            add_class_to_tag(section, "section", "hotel-site-concept__detail-section")
            for section in [price_section_ready, faq_section]
            if section
        )

        city_badge = short_location_badge(lead_lines, title)
        location_html = (
            f'<p class="location">{html.escape(lead_text)}</p>'
            if should_show_location_under_title(lead_text, description)
            else ""
        )
        eyebrow_link, save_href, save_label = listing_catalog_markup(path)

        new_main = f"""<main class="hotel-site-concept">
  <div class="card-preview-page__halo card-preview-page__halo--mint" aria-hidden="true"></div>
  <div class="card-preview-page__halo card-preview-page__halo--sand" aria-hidden="true"></div>

  <section class="hotel-site-concept__intro">
    <div class="hotel-site-concept__intro-brand">
      <p class="eyebrow">{eyebrow_link}</p>
      <p class="hotel-site-concept__intro-subline">онлайн-бронирование без накруток</p>
    </div>
  </section>

  <article class="hotel-card hotel-site-concept__card">
    {gallery_html}

    <div class="hotel-card__content">
      <div class="hotel-card__topline">
        <div class="hotel-card__rating">
          <span class="hotel-card__rating-label">Локация объекта</span>
          <strong class="hotel-card__rating-summary">{html.escape(city_badge)}</strong>
        </div>
        <a class="save-button" href="{html.escape(save_href)}">{html.escape(save_label)}</a>
      </div>

      <div class="hotel-card__header">
        <div class="hotel-card__header-main">
          <h2>{html.escape(title)}</h2>
          {location_html}
        </div>
        <div class="partner-badge">
          <span>Abhazbereg</span>
          <strong>Проверено</strong>
        </div>
      </div>

      <div class="benefit-grid">
        <article>
          <strong>Почему выбирают</strong>
          <ul>{why_choose_html}</ul>
        </article>
        <article>
          <strong>Важно для гостя</strong>
          <ul>{important_html}</ul>
        </article>
      </div>

      {LISTING_GUEST_REVIEWS_BLOCK}

      {reviews_panel}

      <div class="hotel-card__footer">
        <div class="hotel-card__actions">
          <a class="button button--ghost" href="#contacts">Что-то нужно уточнить?</a>
          <a class="button button--accent" href="#contacts">Написать мне</a>
        </div>
      </div>
    </div>
  </article>

  <div class="hotel-site-concept__detail-grid" id="details">
    <div class="hotel-site-concept__detail-main">
      {details_main}
    </div>
    <aside class="hotel-site-concept__detail-aside">
      {details_aside}
    </aside>
  </div>

  {LISTING_PAGE_GUIDE_SECTION}

  {HOME_SOCIAL_STATS_STRIP}

  {listing_contacts_section}
</main>"""

        rebuilt = replace_main(text, new_main)
        meta_desc = build_listing_meta_description(lead_text, description)
        rebuilt = patch_listing_head_meta_descriptions(rebuilt, meta_desc)
        path.write_text(clean_html_block(rebuilt) + "\n", encoding="utf-8")


if __name__ == "__main__":
    build_homepage()
    build_listing_pages()
    patch_all_listing_price_cards()
    patch_kvartira_catalog_card_blurbs()
    print(
        f"updated index, {len(LISTING_PRICE_FILES)} listing pages (hotels + kvartira), "
        f"price cards on {len(LISTING_PRICE_FILES)} listings"
    )
