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
      <a aria-label="ВКонтакте: 37 800 участников" class="site-concept__social-stat" href="https://vk.com/abhazbereg" rel="noopener noreferrer" role="listitem" target="_blank">
        <span aria-hidden="true" class="site-concept__social-stat-icon site-concept__social-stat-icon--vk">
          <svg aria-hidden="true" fill="none" height="24" viewBox="0 0 24 24" width="24" xmlns="http://www.w3.org/2000/svg"><path d="M15.7 0H8.3C2.8 0 0 2.8 0 8.3v7.4C0 22.2 2.8 24 8.3 24h7.4c5.5 0 8.3-1.8 8.3-7.3V8.3C24 2.8 21.2 0 15.7 0zm4.1 17.3h-1.7c-.7 0-.9-.5-2-1.7-1-1-1.5-1.2-1.7-1.2-.4 0-.5.1-.5.6v1.6c0 .4-.1.7-1.2.7-1.9 0-4-1.1-5.5-3.2-2.2-3.1-2.8-5.2-2.8-5.6 0-.2.2-.5.6-.5h1.7c.4 0 .6.2.8.7.8 2.5 2.3 4.6 2.9 4.6.2 0 .3-.1.3-.7V9.7c-.1-1.2-.7-1.3-.7-1.7 0-.2.2-.4.4-.4h2.7c.3 0 .4.2.4.5v4c0 .3.1.5.3.5.2 0 .3-.1.6-.3 1-1.1 1.7-2.9 1.7-2.9.2-.3.3-.5.7-.5h1.7c.5 0 .6.3.5.7-.2.9-2.1 3.6-2.1 3.6-.2.3-.3.4 0 .7.2.3.7.8.9 1.3.6 1 1.1 2.1 1.2 2.8.1.4-.1.7-.5.7z" fill="#fff"/></svg>
        </span>
        <strong>37&#8239;800</strong>
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
    value = value.replace("📍", "").replace("🏖", " • ").replace("👥", " • ")
    value = re.sub(r"\s*•\s*", " • ", value)
    return re.sub(r"\s+", " ", value).strip(" •")


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
    plain = clean_text(raw)
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
    r"(январь|февраль|март|апрель|май|июнь|июль|август|сентябрь|октябрь|ноябрь|декабрь)",
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


def format_price_line_to_html(text: str) -> str:
    """Цена обычным начертанием, месяцы — <strong>; без жирного для условий."""
    text = (text or "").strip()
    if not text:
        return ""

    m = _PRICE_LEADING.match(text)
    if m:
        amount, tail = m.group(1).strip(), m.group(2).strip()
        return (
            f'<span class="price-card__amount">{html.escape(amount)}</span> - '
            f"{bold_months_in_tail(tail)}"
        )

    m = _PRICE_TRAILING.match(text)
    if m:
        desc, amount = m.group(1).strip(), m.group(2).strip()
        return f"{html.escape(desc)} - " f'<span class="price-card__amount">{html.escape(amount)}</span>'

    return html.escape(text)


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
    if re.match(r"^\(?указан", low):
        return False
    if _PRICE_TRAILING.match(plain):
        return False
    if low.startswith("дети") or low.startswith("доп"):
        return False
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
        li_html = f"<li>{inner}</li>"
        if _is_room_category_header_line(plain):
            continue
        if is_seasonal_price_line(plain):
            seasons.append(li_html)
        else:
            notes.append(li_html)

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
        return f"<li>{format_price_line_to_html(plain)}</li>"

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


def reflow_price_card_list_items(fragment: str) -> str:
    """Убирает подписи категорий номеров; подмешивает в список цену из тизера, если её не было в ul; пересобирает сезоны/примечания."""
    if "price-card" not in fragment:
        return fragment
    m = re.search(r'(<article class="card price-card">)([\s\S]*?)(</article>)', fragment, re.S)
    if not m:
        return fragment
    art_open, inner, art_close = m.group(1), m.group(2), m.group(3)
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
        li_html = f"<li>{format_price_line_to_html(plain)}</li>"
        if is_seasonal_price_line(plain):
            seasons.append(li_html)
        else:
            notes.append(li_html)

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
        li_html = f"<li>{format_price_line_to_html(plain)}</li>"
        if is_seasonal_price_line(plain):
            season_chunks.append(li_html)
        else:
            note_chunks.append(li_html)
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

    new_main = f"""<main class="page-shell site-concept">
  <div class="bg-blur bg-blur--mint" aria-hidden="true"></div>
  <div class="bg-blur bg-blur--sand" aria-hidden="true"></div>

  <header class="site-concept__topbar" role="banner">
    <a class="site-concept__brand" href="#search">
      <img class="site-concept__brand-mark" src="media/branding/logo-emblem.png" width="80" height="80" alt="Абхазский берег — на главную" decoding="async" />
      <span class="site-concept__brand-copy">
        <strong>Абхазский берег</strong>
        <span>Каталог проверенного жилья в Абхазии</span>
      </span>
    </a>

    <nav class="site-concept__topnav" aria-label="Основная навигация">
      <a href="#search">Подбор жилья</a>
      <a href="#regions">Лучшие пляжи Абхазии</a>
      <a href="#stay-categories">Для тех, кто едет впервые</a>
      <a href="#guide">Как бронировать</a>
      <a href="/blog/">Блог</a>
      <a href="#contacts">Контакты</a>
    </nav>

    <div class="site-concept__topbar-actions">
      <a class="btn-book site-concept__cta" href="#search">онлайн-подбор жилья</a>
    </div>
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
      <h1>Абхазский берег</h1>
      <p class="site-concept__hero-tagline">живая картотека проверенного жилья в Абхазии</p>
      </div>
      <div class="site-concept__hero-media-column">
        <div class="site-concept__hero-video">
          <video class="site-concept__hero-video-player" controls playsinline webkit-playsinline preload="metadata" src="https://chnyazvybzzryduhgopa.supabase.co/storage/v1/object/public/site-media/videos/hero/darya-intro-vertical-high.mp4">
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
        <a aria-label="ВКонтакте: 37 800 участников" class="site-concept__social-stat" href="https://vk.com/abhazbereg" rel="noopener noreferrer" role="listitem" target="_blank">
          <span aria-hidden="true" class="site-concept__social-stat-icon site-concept__social-stat-icon--vk">
            <svg aria-hidden="true" fill="none" height="24" viewBox="0 0 24 24" width="24" xmlns="http://www.w3.org/2000/svg"><path d="M15.7 0H8.3C2.8 0 0 2.8 0 8.3v7.4C0 22.2 2.8 24 8.3 24h7.4c5.5 0 8.3-1.8 8.3-7.3V8.3C24 2.8 21.2 0 15.7 0zm4.1 17.3h-1.7c-.7 0-.9-.5-2-1.7-1-1-1.5-1.2-1.7-1.2-.4 0-.5.1-.5.6v1.6c0 .4-.1.7-1.2.7-1.9 0-4-1.1-5.5-3.2-2.2-3.1-2.8-5.2-2.8-5.6 0-.2.2-.5.6-.5h1.7c.4 0 .6.2.8.7.8 2.5 2.3 4.6 2.9 4.6.2 0 .3-.1.3-.7V9.7c-.1-1.2-.7-1.3-.7-1.7 0-.2.2-.4.4-.4h2.7c.3 0 .4.2.4.5v4c0 .3.1.5.3.5.2 0 .3-.1.6-.3 1-1.1 1.7-2.9 1.7-2.9.2-.3.3-.5.7-.5h1.7c.5 0 .6.3.5.7-.2.9-2.1 3.6-2.1 3.6-.2.3-.3.4 0 .7.2.3.7.8.9 1.3.6 1 1.1 2.1 1.2 2.8.1.4-.1.7-.5.7z" fill="#fff"/></svg>
          </span>
          <strong>37&#8239;800</strong>
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
            <p>В разделе <a href="/blog/">Блог</a> вы найдете полезные статьи обо всем, что связано с поездкой в Абхазию, либо напишите мне сразу в чат, я подскажу где что и как.</p>
          </div>
        </article>
      </div>
    </div>
  </section>

  <section class="site-concept__section-block" id="regions">
    <div class="site-concept__section-head">
      <div>
        <p class="site-concept__eyebrow">Популярные направления</p>
      </div>
      <a href="#stays">Все подборки</a>
    </div>

    <div class="site-concept__destination-grid">
      <article class="site-concept__destination-card site-concept__destination-card--wide">
        <img src="/media/cards/pegas-otel-na-pervoy-linii-vid-na-more-2574.jpg" alt="Отдых у моря" />
        <div class="site-concept__destination-content">
          <span>Море и первая линия</span>
          <strong>Для пляжного отдыха</strong>
        </div>
      </article>
      <article class="site-concept__destination-card">
        <img src="/media/cards/fazenda-otel-s-basseynom-i-pitaniem-3190.jpg" alt="Семейный отдых" />
        <div class="site-concept__destination-content">
          <span>Сервис и семейный формат</span>
          <strong>Пицунда и Лдзаа</strong>
        </div>
      </article>
      <article class="site-concept__destination-card">
        <img src="/media/cards/krylya-domiki-vidovye-dvuhkomnatnye-2765.jpg" alt="Горы и панорамы" />
        <div class="site-concept__destination-content">
          <span>Тишина и виды</span>
          <strong>Горные домики</strong>
        </div>
      </article>
    </div>
  </section>

  <section class="site-concept__section-block" id="stays">
    <div class="site-concept__section-head">
      <div class="site-concept__section-head__intro">
        <p class="site-concept__eyebrow">Страничка подбора</p>
      </div>
      <div class="site-concept__filter-pills" aria-hidden="true">
        <span class="is-active">Все</span>
        <span>Семейные</span>
        <span>С бассейном</span>
        <span>У моря</span>
        <span>Премиум</span>
      </div>
    </div>

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
        <span>Мгновенное подтверждение</span>
        <span>Проверенные хозяева</span>
        <span>Поддержка 24/7</span>
        <span>Оплата на сайте</span>
      </div>
    </div>

    {catalog_section}
  </section>

  <section class="site-concept__section-block site-concept__section-block--subcatalog" id="kvartira-catalog">
    <div class="site-concept__section-head">
      <div>
        <p class="site-concept__eyebrow">Квартиры и дома</p>
      </div>
      <a href="/kvartira/">Открыть весь раздел</a>
    </div>
    <div class="catalog-grid" id="kvartira-catalog-grid"></div>
  </section>

  <section class="site-concept__section-block" id="guide">
    <div class="site-concept__section-head">
      <div>
        <p class="site-concept__eyebrow">Как бронировать</p>
        <h2>Как найти жильё в Абхазии без утомительного поиска</h2>
        <p class="site-concept__guide-subtitle site-concept__guide-subtitle--full">Можно искать самой по сайтам и чатам. А можно просто написать мне — и я помогу быстрее найти нормальный вариант под ваш запрос.</p>
        <p class="site-concept__guide-subtitle site-concept__guide-subtitle--short">Искать самой или написать мне — я помогу подобрать вариант под ваш запрос.</p>
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
      <p class="site-concept__guide-pitch">Самостоятельный поиск жилья — это десятки сайтов и переписок, где теряется время. Напишите, что вам нужно — я предложу подходящие варианты; если не подойдёт, продолжите искать сами.</p>
      <div class="site-concept__guide-cta">
        <a class="btn-book site-concept__guide-cta-btn" href="https://t.me/abhazbooking_online" rel="noopener noreferrer" target="_blank">Написать в мессенджер</a>
        <p class="site-concept__guide-cta-caption">Отвечу, помогу сориентироваться и предложу варианты под ваш запрос</p>
      </div>
    </div>
  </section>

  {reviews_section}
  {HOME_SOCIAL_STATS_STRIP}
  {contacts_section}
</main>"""

    rebuilt = replace_main(text, new_main)
    if "scripts.js" not in rebuilt:
        rebuilt = rebuilt.replace("</body>", '  <script src="scripts.js?v=2026032801" defer></script>\n</body>')
    INDEX_FILE.write_text(clean_html_block(rebuilt) + "\n", encoding="utf-8")


def build_listing_pages() -> None:
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
        contacts_section = ""
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
                contacts_section = section
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
        lead_lines = [clean_text(part) for part in re.split(r"[•\n]", lead_text) if clean_text(part)]

        extra_price_from_prose: list[str] = []
        content_sections_cleaned: list[str] = []
        for section in content_sections:
            s0, e0 = strip_ceny_subsection_from_section_html(section)
            cleaned, extra = strip_paragraphs_price_from_section_html(s0)
            extra_price_from_prose.extend(e0 + extra)
            content_sections_cleaned.append(cleaned)
        content_sections = content_sections_cleaned

        all_images = extract_images(media_section)
        main_image = all_images[0] if all_images else ("", title)
        thumb_images = all_images[1:4]

        section_titles = [
            clean_text(raw)
            for raw in re.findall(r"<h2>(.*?)</h2>", " ".join(content_sections), flags=re.S)
            if clean_text(raw)
        ]
        feature_labels = list(dict.fromkeys(section_titles[:4] + [line for line in lead_lines[1:3] if line]))[:4]
        feature_labels = [lbl for lbl in feature_labels if clean_text(lbl).casefold() != "обзор"]

        description_parts: list[str] = []
        for section in content_sections[:2]:
            for paragraph in extract_paragraphs(section)[:2]:
                p = remove_price_clauses(paragraph)
                if p and p not in description_parts:
                    description_parts.append(p)
        description = " ".join(description_parts[:2]) if description_parts else (remove_price_clauses(lead_text) or lead_text)

        why_choose_items = []
        important_items = []
        if content_sections:
            why_choose_items = [remove_price_clauses(x) for x in extract_paragraphs(content_sections[0])[:3]]
            why_choose_items = [p for p in why_choose_items if p]
        if len(content_sections) > 1:
            important_items = [remove_price_clauses(x) for x in extract_paragraphs(content_sections[1])[:3]]
            important_items = [p for p in important_items if p]
        if not important_items and lead_lines:
            important_items = [p for p in lead_lines[:3] if not _has_price_signal(p)]

        review_cards = extract_reviews(reviews_section)
        price_section = reformat_price_card_content(price_section)
        price_section = strip_stray_contacts_from_price_section(price_section)
        price_section = cleanup_misplaced_prose_in_price_section(price_section)
        price_section = reflow_price_card_list_items(price_section)
        price_section = split_price_card_seasons_notes(price_section)
        price_section = merge_extra_lines_into_price_section(price_section, extra_price_from_prose)
        price_section = cleanup_misplaced_prose_in_price_section(price_section)
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

        feature_row_html = "".join(f"<span>{item}</span>" for item in feature_labels)
        feature_row_markup = (
            f"""      <div class="feature-row">
        {feature_row_html}
      </div>
"""
            if feature_row_html
            else ""
        )
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
                '<div class="reviews-summary__tags"><em>текстом</em><em>по объекту</em><em>без скриншотов</em></div>'
                "</div></div>"
                f'<div class="reviews-grid">{reviews_html}</div>'
                "</section>"
            )

        details_main = "".join(add_class_to_tag(section, "section", "hotel-site-concept__detail-section") for section in ([media_section] + content_sections if media_section else content_sections))
        price_section_ready = inject_price_teaser(price_section, price_highlight)
        if contacts_section and 'id="contacts"' not in contacts_section:
            contacts_section = re.sub(
                r"<section\b",
                '<section id="contacts"',
                contacts_section,
                count=1,
            )
        details_aside = "".join(
            add_class_to_tag(section, "section", "hotel-site-concept__detail-section")
            for section in [price_section_ready, faq_section, contacts_section]
            if section
        )

        city_badge = short_location_badge(lead_lines, title)
        location_html = (
            f'<p class="location">{html.escape(lead_text)}</p>'
            if should_show_location_under_title(lead_text, description)
            else ""
        )
        prose_html = description_to_prose_html(description)
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

      {prose_html}

      {feature_row_markup}

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
</main>"""

        rebuilt = replace_main(text, new_main)
        path.write_text(clean_html_block(rebuilt) + "\n", encoding="utf-8")


if __name__ == "__main__":
    build_homepage()
    build_listing_pages()
    patch_all_listing_price_cards()
    print(
        f"updated index, {len(LISTING_PRICE_FILES)} listing pages (hotels + kvartira), "
        f"price cards on {len(LISTING_PRICE_FILES)} listings"
    )
