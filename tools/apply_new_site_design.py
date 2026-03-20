#!/usr/bin/env python3
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX_FILE = ROOT / "index.html"
HOTEL_FILES = sorted((ROOT / "hotels").glob("*/index.html"))


def strip_tags(html: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&quot;", '"').replace("&amp;", "&").replace("&nbsp;", " ")
    return re.sub(r"[ \t]+", " ", text).strip()


def clean_line(text: str) -> str:
    text = re.sub(r"^[^\wА-Яа-яЁё0-9]+", "", text.strip())
    return re.sub(r"\s+", " ", text)


def replace_main(text: str, new_main: str) -> str:
    return re.sub(r"(?s)<main.*?</main>", new_main, text, count=1)


def extract_section(text: str, anchor: str) -> str:
    match = re.search(rf'(?s)<section class="section(?: cta-block)?" id="{anchor}".*?</section>', text)
    if not match:
      raise RuntimeError(f"Не найден section #{anchor}")
    return match.group(0)


def build_homepage() -> None:
    text = INDEX_FILE.read_text(encoding="utf-8")
    catalog_section = extract_section(text, "catalog")
    reviews_section = extract_section(text, "reviews")
    contacts_section = extract_section(text, "contacts")

    new_main = f"""<main class="page-shell landing-v2">
<section class="landing-v2__topbar">
<a class="landing-v2__brand" href="#home">
<span class="landing-v2__brand-mark">A</span>
<span class="landing-v2__brand-copy">
<strong>Abhazbereg</strong>
<span>travel marketplace</span>
</span>
</a>
<nav aria-label="Основная навигация" class="landing-v2__nav">
<a href="#search">Поиск</a>
<a href="#regions">Регионы</a>
<a href="#catalog">Каталог</a>
<a href="#guide">Как бронировать</a>
<a href="#contacts">Контакты</a>
</nav>
<div class="landing-v2__topbar-actions">
<a class="landing-v2__topbar-link" href="/kvartira/">Квартиры и дома</a>
<a class="btn-book landing-v2__topbar-cta" href="#search">Начать поиск</a>
</div>
</section>

<section class="section landing-v2__hero" id="home">
<div class="landing-v2__hero-grid">
<div class="landing-v2__hero-copy" id="search">
<p class="eyebrow">Новая версия Abhazbereg: современная подача, но с сильной логикой старого сайта</p>
<h1>Подбор жилья в Абхазии как современный маркетплейс, но с живой экспертизой по каждому объекту.</h1>
<p class="landing-v2__hero-text">Сохраняем то, за что старый сайт был полезен: вход по регионам, понятные типы жилья, честные характеристики объектов, быстрый контакт с менеджером и доверие через реальные отзывы. Но собираем это в более чистую, продуктовую и удобную главную.</p>
<div class="landing-v2__hero-pills">
<span>Проверенные объекты</span>
<span>Честные описания без прикрас</span>
<span>Подбор под семью, пару и компанию</span>
<span>Быстрое бронирование через мессенджеры</span>
</div>
</div>
<aside class="landing-v2__hero-side">
<div class="landing-v2__hero-side-badge">Что сохраняем из старого сайта</div>
<ul class="landing-v2__hero-list">
<li>деление по регионам, а не просто длинный список объектов</li>
<li>удобный вход по типам жилья: отели, домики, гостевые дома, квартиры</li>
<li>живой менеджер как часть сценария бронирования</li>
<li>полезные детали: до моря, пляж, вместимость, питание, нюансы</li>
</ul>
<div class="landing-v2__hero-side-note">
<strong>Главная идея</strong>
<span>Сначала быстро понять, куда и в каком формате отдыха ехать, а уже потом выбирать объект.</span>
</div>
</aside>
</div>

<div class="landing-v2__search-surface">
<div class="landing-v2__search-tabs" role="tablist" aria-label="Тип поиска">
<button class="landing-v2__search-tab is-active" type="button">Гостям</button>
<button class="landing-v2__search-tab" type="button">Семьям</button>
<button class="landing-v2__search-tab" type="button">Владельцам</button>
</div>
<div class="landing-v2__search-bar">
<label class="landing-v2__search-field landing-v2__search-field--wide">
<span>Куда едем</span>
<strong>Пицунда, Лдзаа, Гагра или Сухум</strong>
</label>
<label class="landing-v2__search-field">
<span>Заезд</span>
<strong>12 июня</strong>
</label>
<label class="landing-v2__search-field">
<span>Выезд</span>
<strong>19 июня</strong>
</label>
<label class="landing-v2__search-field">
<span>Гости</span>
<strong>2 взрослых + ребёнок</strong>
</label>
<a class="btn-book landing-v2__search-submit" href="#catalog">Найти варианты</a>
</div>
<div class="landing-v2__search-tags">
<span>Подтверждение и сопровождение</span>
<span>Можно запросить доп. фото и видео</span>
<span>Telegram / WhatsApp / VK / MAX</span>
</div>
</div>

<div class="landing-v2__metrics">
<article>
<strong>8 региональных зон</strong>
<span>Поиск не по хаосу карточек, а по понятным районам отдыха.</span>
</article>
<article>
<strong>4 формата жилья</strong>
<span>Отели, гостевые дома, домики и квартиры в одной системе.</span>
</article>
<article>
<strong>Живой контакт</strong>
<span>Финализация брони без потери контекста выбранного объекта.</span>
</article>
</div>
</section>

<section class="section landing-v2__regions" id="regions">
<div class="section-heading landing-v2__section-heading">
<div>
<p class="eyebrow">Вход по регионам</p>
<h2>То, что было сильной стороной старого сайта, становится навигацией первого уровня.</h2>
</div>
<a class="landing-v2__section-link" href="#catalog">Открыть каталог</a>
</div>
<div class="landing-v2__region-grid">
<article class="landing-v2__region-card landing-v2__region-card--wide">
<img alt="Гагра, Цандрипш, Алахадзы" loading="lazy" src="/media/cards/pegas-otel-na-pervoy-linii-vid-na-more-2574.jpg"/>
<div class="landing-v2__region-copy">
<span>Западная Абхазия</span>
<strong>Гагра, Цандрипш, Алахадзы</strong>
<p>Для моря, инфраструктуры, семейных поездок и первого знакомства с Абхазией.</p>
</div>
</article>
<article class="landing-v2__region-card">
<img alt="Пицунда и Лдзаа" loading="lazy" src="/media/cards/fazenda-otel-s-basseynom-i-pitaniem-3190.jpg"/>
<div class="landing-v2__region-copy">
<span>Пицунда и Лдзаа</span>
<strong>Сосны, бухты, семейный отдых</strong>
<p>Один из самых сильных сценариев старого каталога.</p>
</div>
</article>
<article class="landing-v2__region-card">
<img alt="Сухум и Новый Афон" loading="lazy" src="/media/cards/avrora-inn-novyy-otel-v-tsentre-goroda-2641.jpg"/>
<div class="landing-v2__region-copy">
<span>Сухум и Новый Афон</span>
<strong>Город, прогулки и маршруты</strong>
<p>Для тех, кому важны не только пляж, но и жизнь вокруг.</p>
</div>
</article>
</div>
</section>

<section class="section landing-v2__types">
<div class="section-heading landing-v2__section-heading">
<div>
<p class="eyebrow">Типы размещения</p>
<h2>Нужен не только каталог, но и понятный вход в нужный формат отдыха.</h2>
</div>
</div>
<div class="landing-v2__type-grid">
<article class="landing-v2__type-card">
<strong>Отели и мини-отели</strong>
<p>Когда важны сервис, питание, бассейн и более предсказуемый уровень комфорта.</p>
</article>
<article class="landing-v2__type-card">
<strong>Гостевые дома</strong>
<p>Более камерный и тёплый формат, часто с хорошим соотношением цены и уюта.</p>
</article>
<article class="landing-v2__type-card">
<strong>Домики и коттеджи</strong>
<p>Подходят семьям и компаниям, которые хотят больше пространства и приватности.</p>
</article>
<article class="landing-v2__type-card">
<strong>Квартиры и апартаменты</strong>
<p>Для самостоятельного сценария отдыха, кухни и большей автономности.</p>
</article>
</div>
</section>

{catalog_section}

<section class="section landing-v2__guide" id="guide">
<div class="section-heading landing-v2__section-heading">
<div>
<p class="eyebrow">Как бронировать</p>
<h2>Старую полезную логику оставляем, но подаём кратко и по делу.</h2>
</div>
</div>
<div class="landing-v2__steps">
<article class="landing-v2__step">
<span>01</span>
<strong>Выбираете регион</strong>
<p>Не просто «Абхазия», а сразу Гагра, Лдзаа, Пицунда, Сухум или Новый Афон.</p>
</article>
<article class="landing-v2__step">
<span>02</span>
<strong>Смотрите честную карточку</strong>
<p>До моря, пляж, питание, формат жилья, вместимость и нюансы по заселению.</p>
</article>
<article class="landing-v2__step">
<span>03</span>
<strong>Запрашиваете бронь</strong>
<p>Через карточку объекта и удобный мессенджер без длинного ручного поиска.</p>
</article>
<article class="landing-v2__step">
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
    if 'src="scripts.js"' not in rebuilt:
        rebuilt = rebuilt.replace("</main>\n<script>", '</main>\n<script src="scripts.js" defer></script>\n<script>', 1)
    INDEX_FILE.write_text(rebuilt, encoding="utf-8")


def build_hotels() -> None:
    for path in HOTEL_FILES:
        text = path.read_text(encoding="utf-8")
        if "hotel-page-v2" in text:
            continue

        header_match = re.search(r'(?s)<header class="hero section">.*?</header>', text)
        section_matches = re.findall(r'(?s)<section class="section(?: cta-block)?">.*?</section>', text)
        if not header_match or not section_matches:
            continue

        header_html = header_match.group(0).replace('class="hero section"', 'class="hero section hotel-hero-v2"', 1)
        media_section = ""
        price_section = ""
        reviews_section = ""
        faq_section = ""
        contacts_section = ""
        content_sections = []

        for section in section_matches:
            if "Фото и видео из поста" in section:
                media_section = section.replace('class="section"', 'class="section hotel-media-section"', 1)
            elif 'class="card price-card"' in section:
                price_section = section.replace('class="section"', 'class="section hotel-price-section"', 1)
            elif "<h2>Отзывы</h2>" in section:
                reviews_section = section.replace('class="section"', 'class="section hotel-reviews-section"', 1)
            elif 'faq-card' in section:
                faq_section = section.replace('class="section"', 'class="section hotel-faq-section"', 1)
            elif 'class="section cta-block"' in section:
                contacts_section = section.replace('class="section cta-block"', 'class="section cta-block hotel-contact-section"', 1)
            else:
                content_sections.append(section)

        lead_match = re.search(r'(?s)<p class="lead">(.*?)</p>', header_html)
        lead_lines = []
        if lead_match:
            raw_lines = re.split(r"<br\s*/?>", lead_match.group(1), flags=re.I)
            lead_lines = [clean_line(strip_tags(line)) for line in raw_lines if clean_line(strip_tags(line))]

        heading_match = re.search(r"<h2>(.*?)</h2>", " ".join(content_sections))
        main_focus = strip_tags(heading_match.group(1)) if heading_match else "Главные особенности"
        section_titles = re.findall(r"<h2>(.*?)</h2>", " ".join(content_sections))
        section_tags = "".join(f"<span>{strip_tags(title)}</span>" for title in section_titles[:4])
        quick_facts = "".join(
            f"""<div class="hotel-side-summary__fact"><span>{idx + 1:02d}</span><strong>{line}</strong></div>"""
            for idx, line in enumerate(lead_lines[:3])
        )

        new_main = f"""<main class="hotel-page-v2">
      <div class="hotel-page-v2__glow hotel-page-v2__glow--mint" aria-hidden="true"></div>
      <div class="hotel-page-v2__glow hotel-page-v2__glow--sand" aria-hidden="true"></div>
      <section class="hotel-hero-shell">
        {header_html}
        <aside class="hotel-side-summary">
          <div class="hotel-side-summary__badge">Коротко об объекте</div>
          <div class="hotel-side-summary__facts">
            {quick_facts}
          </div>
          <div class="hotel-side-summary__focus">
            <span>Что важно изучить</span>
            <strong>{main_focus}</strong>
          </div>
          <div class="hotel-side-summary__tags">
            {section_tags}
          </div>
        </aside>
      </section>

      <div class="hotel-layout-v2">
        <div class="hotel-layout-v2__main">
          {media_section}
          {''.join(content_sections)}
          {reviews_section}
          {faq_section}
        </div>
        <aside class="hotel-layout-v2__aside">
          {price_section}
          {contacts_section}
        </aside>
      </div>
    </main>"""

        rebuilt = replace_main(text, new_main)
        path.write_text(rebuilt, encoding="utf-8")


if __name__ == "__main__":
    build_homepage()
    build_hotels()
    print(f"updated index and {len(HOTEL_FILES)} hotel pages")
