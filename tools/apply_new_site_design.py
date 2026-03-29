#!/usr/bin/env python3
import html
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX_FILE = ROOT / "index.html"
HOTEL_FILES = sorted((ROOT / "hotels").glob("*/index.html"))


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
    if not lead_lines:
        return "Абхазия"
    location = lead_lines[0].replace("📍", "").strip()
    first_part = location.split(",")[0].strip()
    if first_part:
        return first_part
    return title.split()[0] if title else "Абхазия"


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
        if "₽" in raw or "руб" in raw.lower():
            return raw
    m = re.search(
        r'price-card__teaser[^>]*>.*?price-box__label[^>]*>от</span>\s*(.*?)\s*</p>',
        section,
        flags=re.S,
    )
    if m:
        t = strip_tags(m.group(1))
        if "₽" in t or "руб" in t.lower():
            return clean_text(t)
    return "Уточнить стоимость"


def inject_price_teaser(price_section: str, highlight: str) -> str:
    """Вставка строки «от …» под заголовок блока цен; без повторения слова «Цены» (оно только в h2)."""
    if not price_section or not highlight or highlight == "Уточнить стоимость":
        return price_section
    if "price-card__teaser" in price_section:
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
    # Убрать дублирующий первый пункт списка, если совпадает с акцентной строкой
    hi = clean_text(highlight)
    m = re.search(r"<ul[^>]*>\s*<li>(.*?)</li>", updated, flags=re.S)
    if m:
        li_plain = clean_text(m.group(1))
        if li_plain == hi:
            updated = re.sub(
                r"<ul([^>]*)>\s*<li>.*?</li>\s*",
                r"<ul\1>\n",
                updated,
                count=1,
                flags=re.S,
            )
    return updated


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
          <video class="site-concept__hero-video-player" controls playsinline preload="metadata" src="https://chnyazvybzzryduhgopa.supabase.co/storage/v1/object/public/site-media/videos/hero/darya-intro-vertical-high.mp4" data-high-src="/media/videos/hero/darya-intro-vertical-high.mp4" data-low-src="/media/videos/hero/darya-intro-vertical-low.mp4">
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
            <p>В разделе <a href="#journal">Блог</a> вы найдете полезные статьи обо всем, что связано с поездкой в Абхазию, либо напишите мне сразу в чат, я подскажу где что и как.</p>
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
        <h2>Старую полезную логику оставляем, но подаём кратко и по делу.</h2>
      </div>
    </div>

    <div class="site-concept__guide-grid">
      <article class="site-concept__guide-card">
        <span>01</span>
        <strong>Выбираете регион</strong>
        <p>Не просто Абхазия, а сразу Гагра, Лдзаа, Пицунда, Сухум или Новый Афон.</p>
      </article>
      <article class="site-concept__guide-card">
        <span>02</span>
        <strong>Смотрите честную карточку</strong>
        <p>До моря, пляж, питание, формат жилья, вместимость и важные нюансы по объекту.</p>
      </article>
      <article class="site-concept__guide-card">
        <span>03</span>
        <strong>Фиксируете вариант</strong>
        <p>Через сайт или удобный мессенджер без долгих пересылок карточек и скриншотов.</p>
      </article>
      <article class="site-concept__guide-card">
        <span>04</span>
        <strong>Получаете подтверждение</strong>
        <p>С поддержкой менеджера и понятными условиями, а не просто ссылкой на контакт.</p>
      </article>
    </div>
  </section>

  {reviews_section}
  {contacts_section}
</main>"""

    rebuilt = replace_main(text, new_main)
    if "scripts.js" not in rebuilt:
        rebuilt = rebuilt.replace("</body>", '  <script src="scripts.js?v=2026032801" defer></script>\n</body>')
    INDEX_FILE.write_text(clean_html_block(rebuilt) + "\n", encoding="utf-8")


def build_hotels() -> None:
    for path in HOTEL_FILES:
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
            if "Фото и видео из поста" in section:
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
                    [r'<div class="hotel-card__header">\s*<div>\s*<h2>(.*?)</h2>'],
                    text,
                )
            )
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
        lead_lines = [clean_text(part) for part in re.split(r"[•\n]", lead_text) if clean_text(part)]

        all_images = extract_images(media_section)
        main_image = all_images[0] if all_images else ("", title)
        thumb_images = all_images[1:4]

        section_titles = [
            clean_text(raw)
            for raw in re.findall(r"<h2>(.*?)</h2>", " ".join(content_sections), flags=re.S)
            if clean_text(raw)
        ]
        feature_labels = list(dict.fromkeys(section_titles[:4] + [line for line in lead_lines[1:3] if line]))[:4]

        description_parts: list[str] = []
        for section in content_sections[:2]:
            for paragraph in extract_paragraphs(section)[:2]:
                if paragraph not in description_parts:
                    description_parts.append(paragraph)
        description = " ".join(description_parts[:2]) or lead_text

        why_choose_items = []
        important_items = []
        if content_sections:
            why_choose_items = extract_paragraphs(content_sections[0])[:3]
        if len(content_sections) > 1:
            important_items = extract_paragraphs(content_sections[1])[:3]
        if not important_items and lead_lines:
            important_items = lead_lines[:3]

        review_cards = extract_reviews(reviews_section)
        price_section = reformat_price_card_content(price_section)
        price_section = strip_stray_contacts_from_price_section(price_section)
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

        new_main = f"""<main class="hotel-site-concept">
  <div class="card-preview-page__halo card-preview-page__halo--mint" aria-hidden="true"></div>
  <div class="card-preview-page__halo card-preview-page__halo--sand" aria-hidden="true"></div>

  <section class="hotel-site-concept__intro">
    <div class="hotel-site-concept__intro-brand">
      <p class="eyebrow"><a href="/"><strong>Каталог Абхазберег</strong></a></p>
      <p class="hotel-site-concept__intro-subline">онлайн-бронирование без накруток</p>
    </div>
  </section>

  <article class="hotel-card hotel-site-concept__card">
    {gallery_html}

    <div class="hotel-card__content">
      <div class="hotel-card__topline">
        <div class="hotel-card__rating">
          <strong>{city_badge}</strong>
          <span>Локация объекта</span>
        </div>
        <a class="save-button" href="/">К каталогу</a>
      </div>

      <div class="hotel-card__header">
        <div>
          <h2>{title}</h2>
          <p class="location">{lead_text}</p>
        </div>
        <div class="partner-badge">
          <span>Abhazbereg</span>
          <strong>Проверено</strong>
        </div>
      </div>

      <p class="hotel-card__description">{description}</p>

      <div class="feature-row">
        {feature_row_html}
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

      <div class="hotel-card__footer">
        <div class="hotel-card__actions">
          <a class="button button--ghost" href="#contacts">Что-то нужно уточнить?</a>
          <a class="button button--accent" href="#contacts">Написать мне</a>
        </div>
      </div>

      {reviews_panel}
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
    build_hotels()
    print(f"updated index and {len(HOTEL_FILES)} hotel pages")
