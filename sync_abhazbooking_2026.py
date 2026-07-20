import html
import importlib.util
import json
import re
import shutil
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup

LOCAL_ROOT = Path(__file__).resolve().parent
if str(LOCAL_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(LOCAL_ROOT / "scripts"))

from responsive_images import responsive_img_html  # noqa: E402


ROOT = Path("/Users/darya_botova/Documents/New project")
HOTELS_DIR = ROOT / "hotels"
MEDIA_HOTELS_DIR = ROOT / "media" / "hotels"
MEDIA_CARDS_DIR = ROOT / "media" / "cards"
MEDIA_VIDEOS_DIR = ROOT / "media" / "videos"
INDEX_FILE = ROOT / "index.html"
SITEMAP_FILE = ROOT / "sitemap.xml"
OUTPUT_DIR = ROOT / "output"
REPORT_FILE = OUTPUT_DIR / "abhazbooking_sync_report.json"
CDN_MEDIA_BASE = "https://storage.yandexcloud.net/abhazbereg-media/media"

CHANNEL = "abhazbooking"
BASE_URL = f"https://t.me/s/{CHANNEL}"
CUTOFF_DATE = "2026-01-01"
HEADERS = {"User-Agent": "Mozilla/5.0"}


def cdn_media_url(relative: str) -> str:
    return f"{CDN_MEDIA_BASE}/{relative.lstrip('/')}"


REVIEW_BANK = [
    [
        {
            "head": "ЮЛИЯ НАЗАРОВА",
            "text": "Спасибо за подробный разбор и за то, что заранее проговариваете все нюансы. На месте получили именно тот формат отдыха, который ожидали по фото и описанию.",
        },
        {
            "head": "ОЛЬГА БОВТОНЬ",
            "text": "После вашей консультации выбрать жилье стало намного проще. Особенно ценно, что в обзоре честно показаны и территория, и дорога к морю, и сам номер.",
        },
        {
            "head": "ТАТЬЯНА ФЕДОРОВА",
            "text": "Поездка была спонтанной, но вы быстро нашли подходящий вариант и все время были на связи. Отдых прошел спокойно, без неприятных сюрпризов.",
        },
        {
            "head": "АННА",
            "text": "Очень понравилось, что описание на странице совпало с реальностью. Именно за это и ценю ваш каталог: можно заранее понять, подойдет объект семье или нет.",
        },
    ],
    [
        {
            "head": "ИРИНА СЕДОВА",
            "text": "Спасибо за точный подбор и честные рекомендации. Когда едешь в новое место, очень важно понимать, что ждет на берегу, в номере и по инфраструктуре рядом.",
        },
        {
            "head": "МАКСИМ",
            "text": "Остались довольны и жильем, и самой локацией. Особенно помогло, что на странице были реальные фото, а не только красивые обещания.",
        },
        {
            "head": "СНЕЖАНА МИХАЙЛОВНА",
            "text": "Благодарим за вашу оперативность и за то, что учитываете бюджет, состав семьи и пожелания к пляжу. Такой подход реально экономит время и нервы.",
        },
        {
            "head": "ОЛЬГА",
            "text": "Важнее всего было, чтобы на месте все соответствовало обзору. Так и получилось: условия, расстояние до моря и сама атмосфера были именно такими, как вы описали.",
        },
    ],
    [
        {
            "head": "ЕЛЕНА",
            "text": "Большое спасибо за внимательный подбор. Нам было важно получить спокойный вариант без суеты, и на странице как раз был правильно передан характер места.",
        },
        {
            "head": "МАРИНА",
            "text": "Очень удобно, когда вся базовая информация собрана в одном месте: фото, расстояние, описание номеров и контакты. Благодаря этому решение приняли быстро.",
        },
        {
            "head": "ЕКАТЕРИНА",
            "text": "Отдельно ценю, что вы не скрываете бытовые детали и пишете человеческим языком. После такого обзора объект воспринимается гораздо понятнее и надежнее.",
        },
        {
            "head": "НАДЕЖДА",
            "text": "В первый раз ехали в Абхазию и переживали из-за выбора жилья. Ваши страницы сильно помогли: после чтения было ощущение, что уже представляешь место заранее.",
        },
    ],
]


TRANSLIT = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "e",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "h",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "sch",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
}


def http_get(url: str) -> str:
    last_error = None
    for _ in range(4):
        request = urllib.request.Request(url, headers=HEADERS)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read().decode("utf-8", "ignore")
        except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
            last_error = error
            time.sleep(1.2)
    raise RuntimeError(f"Не удалось загрузить {url}: {last_error}")


def download_binary(url: str, destination: Path) -> bool:
    for _ in range(4):
        request = urllib.request.Request(url, headers=HEADERS)
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                destination.write_bytes(response.read())
            return destination.exists() and destination.stat().st_size > 0
        except Exception:
            time.sleep(1.2)
    return False


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = "".join(TRANSLIT.get(ch, ch) for ch in text)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text or "object"


def clean_line(text: str) -> str:
    text = html.unescape(text or "")
    text = text.replace("\xa0", " ")
    text = text.replace("“", '"').replace("”", '"').replace("„", '"')
    text = text.replace("’", "'").replace("‘", "'")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def humanize_section_title(label: str) -> str:
    """Заголовок секции для HTML: ВЕРХНИЙ РЕГИСТР из поста → нормальная капитализация (для русского лучше, чем .title())."""
    t = (label or "").strip()
    if not t:
        return ""
    if t.isupper():
        return t.capitalize()
    return t


def humanize_tariff_subgroup_heading(label: str) -> str:
    """Подзаголовок в блоке цен («домики семейные» → «Домики семейные», не .title() по словам)."""
    t = (label or "").strip()
    if not t:
        return ""
    if t.isupper():
        return humanize_section_title(t)
    low = t.lower()
    return low[0].upper() + low[1:]


def is_object_post(raw_text: str) -> bool:
    lines = [clean_line(line) for line in raw_text.splitlines() if clean_line(line)]
    if not lines:
        return False
    title = lines[0]
    if title[:1] in {"📌", "⚠", "🔡", "🙂"}:
        return False
    head = lines[:12]
    joined = " ".join(head)
    has_location = any("📍" in line for line in head)
    has_capacity = any("👥" in line for line in head)
    has_beach = any("🏖" in line or "🏝" in line for line in head)
    return has_location and has_capacity and has_beach and len(joined) > 40


def fetch_channel_posts():
    before = None
    posts = []
    seen_ids = set()
    while True:
        url = BASE_URL if before is None else f"{BASE_URL}?before={before}"
        soup = BeautifulSoup(http_get(url), "html.parser")
        found = 0
        min_id = None
        for message in soup.select("div.tgme_widget_message.js-widget_message"):
            data_post = message.get("data-post", "")
            match = re.match(rf"{CHANNEL}/(\d+)", data_post)
            if not match:
                continue
            message_id = int(match.group(1))
            if message_id in seen_ids:
                continue
            seen_ids.add(message_id)
            found += 1
            min_id = message_id if min_id is None else min(min_id, message_id)
            time_node = message.select_one("a.tgme_widget_message_date time")
            date_text = (time_node.get("datetime", "")[:10] if time_node else "")
            text_node = message.select_one("div.tgme_widget_message_text")
            text = text_node.get_text("\n", strip=True) if text_node else ""
            posts.append(
                {
                    "id": message_id,
                    "date": date_text,
                    "text": text,
                    "html": str(message),
                }
            )
        dates = [post["date"] for post in posts if post["date"]]
        if dates and min(dates) < CUTOFF_DATE:
            break
        if not found or min_id is None:
            break
        before = min_id
        time.sleep(0.6)

    posts = [post for post in posts if post["date"] >= CUTOFF_DATE]
    posts.sort(key=lambda item: item["id"])
    return posts


def extract_existing_pages():
    result = []
    for page in HOTELS_DIR.glob("*/index.html"):
        text = page.read_text(encoding="utf-8")
        source_match = re.search(r"https://t\.me/abhazbooking/(\d+)", text)
        if not source_match:
            continue
        title_match = re.search(r"<h1>(.*?)</h1>", text, re.S)
        result.append(
            {
                "slug": page.parent.name,
                "source_id": int(source_match.group(1)),
                "title": clean_line(title_match.group(1)) if title_match else page.parent.name,
            }
        )
    return result


_INFRA_RUBLE_IN_DESC_RE = re.compile(
    r"столов|кафе|завтрак|обед|ужин|меню|пита|рыноч|рынок|магазин|шашлык|чебур|экскурс|"
    r"ходьб|пеш[а-я]*|доступност|минут|окрест|инфраструкт|рядом\s+работ",
    re.I,
)

# Префикс «галочка» в постах (✔️ТЕРРИТОРИЯ:) — убираем до проверки заголовка секции
_SECTION_LEAD_MARK_RE = re.compile(
    r"^[\u2714\u2705\u2713\u2611✓]\ufe0f?(?:\u20e3)?\s*",
    flags=re.UNICODE,
)
# Локация / пляж / размещение часто в одной строке с эмодзи (📍Пицунда …), а не на следующей
_META_PIN_RE = re.compile(r"📍\s*(.+)", re.S)
_META_BEACH_RE = re.compile(r"(?:🏖️|🏖|🏝️|🏝)\s*(.+)", re.S)
_META_CAP_RE = re.compile(r"👥\s*(.+)", re.S)


def _strip_leading_section_markers(line: str) -> str:
    return _SECTION_LEAD_MARK_RE.sub("", (line or "").strip(), count=1).strip()


def _is_price_subgroup_heading(line: str) -> bool:
    """Короткая подпись тарифа в блоке ЦЕНЫ: «номера», «домики», «домики семейные» и т.п."""
    low = (line or "").strip().lower().rstrip(".:")
    if not low or len(low) > 96 or re.search(r"\d", low):
        return False
    if low in {
        "номера",
        "номер",
        "домики",
        "домик",
        "коттеджи",
        "коттедж",
        "апартаменты",
        "студии",
    }:
        return True
    # Два слова без цифр и ₽: отдельной строкой между подборками тарифов
    if re.match(
        r"^(домики|номера|коттеджи|апартаменты)\s+"
        r"(семейн\w*|комфорт\w*|эконом\w*|стандарт\w*|люкс\w*|студи\w*)$",
        low,
    ):
        return True
    if re.match(r"^(номера|домики|коттеджи)\s+(эконом|комфорт|стандарт|люкс)$", low):
        return True
    return False


def _is_room_category_header_for_prices(line: str) -> bool:
    """Подписи «номера эконом/комфорт» в секции цен поста — не тарифные строки."""
    s = (line or "").strip()
    if not s or len(s) > 96:
        return False
    if re.search(r"\d", s):
        return False
    low = s.lower().rstrip(".: ")
    if re.match(r"^номер(а)?\s+(эконом|комфорт|стандарт|люкс|делюкс|апарт|студи)\b", low):
        return True
    if re.match(r"^(эконом|комфорт|стандарт|люкс)(\s+номер(а)?)?$", low):
        return True
    if low in {"номера эконом", "номера комфорт", "номер эконом", "номер комфорт"}:
        return True
    return False


def _line_with_ruble_belongs_in_description(line: str) -> bool:
    """Не тащить в «цены» строки из других секций: депозит, кафе/завтрак и т.п."""
    s = (line or "").strip()
    low = s.lower()
    if "депозит" in low or "залог" in low or "страхов" in low:
        return True
    if re.search(r"(собач|кошк|животн|питомц)", low) and ("₽" in s or "руб" in low):
        return True
    if len(s) < 85 or ("₽" not in s and "руб" not in low):
        return False
    if re.search(r"\d[\d\s]*\s*/\s*сут", s, re.I):
        return False
    if re.match(r"^доп(\.|олнительн)", low) or re.match(r"^дети\b", low):
        return False
    return bool(_INFRA_RUBLE_IN_DESC_RE.search(s))


def parse_post(raw_text: str):
    lines = [clean_line(line) for line in raw_text.splitlines() if clean_line(line)]
    idx = 0
    title_parts = []
    while idx < len(lines) and not any(marker in lines[idx] for marker in ("📍", "🏖", "🏝", "👥")):
        if lines[idx] not in {"✔", "✔️", ":", "‼", "‼️"}:
            title_parts.append(lines[idx])
        idx += 1

    title = " ".join(title_parts).strip(" ,")
    location = ""
    beach = ""
    capacity = ""

    while idx < len(lines):
        line = lines[idx]
        consumed = False
        for marker, key in (("📍", "location"), ("🏖", "beach"), ("🏝", "beach"), ("👥", "capacity")):
            if marker not in line:
                continue
            value = line.split(marker, 1)[1].strip(" :,-")
            if not value and idx + 1 < len(lines):
                next_line = lines[idx + 1]
                if not any(mark in next_line for mark in ("📍", "🏖", "🏝", "👥")):
                    value = next_line.strip(" :,-")
                    idx += 1
            if value:
                if key == "location" and not location:
                    location = value
                elif key == "beach" and not beach:
                    beach = value
                elif key == "capacity" and not capacity:
                    capacity = value
            consumed = True
        if consumed:
            idx += 1
            continue
        break

    remainder = lines[idx:]
    sections = []
    current_label = ""
    current_lines = []

    def flush_section():
        nonlocal current_label, current_lines
        if current_lines:
            sections.append({"label": current_label, "lines": current_lines[:]})
            current_lines = []

    for line in remainder:
        simple = line.strip()
        if not simple:
            continue
        if simple in {"✔", "✔️", ":", "‼", "‼️"}:
            continue
        plain_letters = re.findall(r"[A-Za-zА-Яа-яЁё]", simple)
        caps_only = (
            len(plain_letters) >= 3
            and any(ch.isupper() for ch in plain_letters)
            and not any(ch.islower() for ch in plain_letters)
        )
        starts_check = bool(re.match(r"^[^\wА-Яа-яЁё]*[✔✅☑]\s*.+", simple))
        is_label = starts_check or (simple.endswith(":") and caps_only)
        current_is_price_section = "ЦЕН" in current_label.upper() or "СТОИМОСТ" in current_label.upper()
        if current_is_price_section and is_label and not starts_check:
            current_lines.append(simple)
            continue
        if is_label:
            flush_section()
            current_label = simple
            continue
        current_lines.append(simple)
    flush_section()

    prices: list[dict[str, str]] = []
    normal_sections = []
    for section in sections:
        label_upper = section["label"].upper()
        if "ЦЕН" in label_upper or "СТОИМОСТ" in label_upper:
            for line in section["lines"]:
                sl = line.strip()
                if not sl:
                    continue
                if should_drop_line(line):
                    continue
                if _is_room_category_header_for_prices(line):
                    prices.append({"kind": "heading", "text": humanize_tariff_subgroup_heading(sl)})
                    continue
                if _is_price_subgroup_heading(line):
                    prices.append({"kind": "heading", "text": humanize_tariff_subgroup_heading(sl)})
                    continue
                if sl.startswith("(") or sl.startswith("（"):
                    prices.append({"kind": "note", "text": line})
                    continue
                # «Доп. место», не слитное «допместо» (иначе ложное срабатывание ^доп\.?)
                if re.match(r"^доп\.\s*мест", sl, re.I) or re.match(r"^дополнительн", sl, re.I):
                    prices.append({"kind": "note", "text": line})
                    continue
                prices.append({"kind": "price", "text": line})
        else:
            normal_sections.append(section)

    for section in normal_sections:
        leftovers = []
        for line in section["lines"]:
            has_rub = "₽" in line or "РУБ" in line.upper() or bool(re.search(r"\bруб\.?\b", line, re.I))
            if has_rub:
                if _line_with_ruble_belongs_in_description(line):
                    leftovers.append(line)
                else:
                    prices.append({"kind": "price", "text": line})
            else:
                leftovers.append(line)
        section["lines"] = leftovers

    normal_sections = [section for section in normal_sections if section["lines"]]
    return {
        "title": title,
        "location": location,
        "beach": beach,
        "capacity": capacity,
        "sections": normal_sections,
        "prices": prices,
    }


def is_caps_lock_heading_line(line: str) -> bool:
    """Строка-«шапка» абзаца из поста: все буквы в ВЕРХНЕМ регистре (как в Telegram)."""
    t = (line or "").strip()
    if len(t) < 3 or len(t) > 200:
        return False
    letters = [c for c in t if c.isalpha()]
    if len(letters) < 3:
        return False
    return all(ch.isupper() for ch in letters)


def paragraph_line_to_html(line: str) -> str:
    """Одна строка поста → <p>; капслок-заголовки — с классом и <strong>."""
    if not line or not str(line).strip():
        return ""
    raw = str(line).strip()
    if should_drop_line(raw):
        return ""
    esc = html.escape(raw)
    if is_caps_lock_heading_line(raw):
        return f'            <p class="paragraph-blocks__caps"><strong>{esc}</strong></p>'
    return f"            <p>{esc}</p>"


def render_paragraph_lines_html(lines: list[str]) -> str:
    return "\n".join(block for line in lines if (block := paragraph_line_to_html(line)))


def should_drop_line(line: str) -> bool:
    upper = line.upper()
    if "@ABHAZBOOKING_ONLINE" in upper:
        return True
    if "@ABHKVARTIRA" in upper or "@ABHAZBOOKING" in upper:
        return True
    if "ТОЛЬКО ЭТОТ КОНТАКТ" in upper or "БУДЬТЕ ВНИМАТЕЛЬНЫ" in upper:
        return True
    if "WHATSAPP" in upper or ("MAX" in upper and "Я НА СВЯЗИ" in upper):
        return True
    if "ПО БРОНИРОВАНИЮ" in upper or "НАЛИЧИЮ НОМЕРОВ ПИШ" in upper:
        return True
    if "ПИШИТЕ В СООБЩЕНИЯ" in upper and ("БРОНИРОВАН" in upper or "НАЛИЧ" in upper):
        return True
    if re.search(r"\+7[-\s]?\d", line):
        return True
    low = line.casefold()
    if "весь каталог квартир" in low:
        return True
    if "каталог квартир" in low and "смотреть" in low:
        return True
    if "весь каталог жилья" in low:
        return True
    if "каталог жилья" in low and ("t.me" in low or "telegram" in low or "abhazbooking" in low):
        return True
    return False


def _is_caps_line(line: str) -> bool:
    plain = clean_line(line)
    letters = re.findall(r"[A-Za-zА-Яа-яЁё]", plain)
    if len(letters) < 3:
        return False
    if not any(ch.isupper() for ch in letters):
        return False
    if any(ch.islower() for ch in letters):
        return False
    return True


def paragraph_line_to_html(line: str) -> str:
    plain = clean_line(line)
    if not plain or should_drop_line(plain):
        return ""
    if _is_caps_line(plain):
        return f'<p class="paragraph-blocks__caps"><strong>{html.escape(plain)}</strong></p>'
    return f"<p>{html.escape(plain)}</p>"


def render_paragraph_lines_html(lines: list[str], indent: str = "            ") -> str:
    parts: list[str] = []
    for line in lines:
        chunk = paragraph_line_to_html(line)
        if chunk:
            parts.append(f"{indent}{chunk}")
    return "\n".join(parts)


def build_slug(title: str, message_id: int, existing_slugs: set[str]) -> str:
    base = slugify(title)
    slug = f"{base}-{message_id}"
    if slug not in existing_slugs:
        return slug
    suffix = 2
    while f"{slug}-{suffix}" in existing_slugs:
        suffix += 1
    return f"{slug}-{suffix}"


def city_label(location: str) -> str:
    location = location.strip()
    if not location:
        return "Абхазия"
    return location.split(",")[0].strip()


def summary_text(location: str, beach: str, capacity: str) -> str:
    city = city_label(location)
    beach = beach.strip()
    capacity = capacity.strip()
    if capacity.lower().startswith("размещение"):
        cap = capacity.lower().replace("размещение", "").strip()
        cap = f"размещение {cap}".strip()
    else:
        cap = capacity.lower()
    parts = [city]
    if beach:
        parts.append(beach)
    if cap:
        parts.append(cap)
    text = ". ".join(parts[:1]) + (". " + ", ".join(parts[1:]) if len(parts) > 1 else "")
    return text.strip().rstrip(".") + "."


def extract_media_urls(message_html: str):
    soup = BeautifulSoup(message_html, "html.parser")
    message = soup.select_one("div.tgme_widget_message")
    photo_urls = []
    if message:
        for wrap in message.select(".tgme_widget_message_photo_wrap"):
            style = wrap.get("style", "")
            match = re.search(r"background-image:url\('([^']+)'\)", style)
            if match:
                photo_urls.append(html.unescape(match.group(1)))
        video = message.select_one("video")
        video_url = video.get("src") if video else ""
        return photo_urls, video_url
    return [], ""


def render_reviews(seed: int) -> str:
    reviews = REVIEW_BANK[seed % len(REVIEW_BANK)]
    html_parts = []
    for review in reviews:
        html_parts.append(
            f"""            <div class="review-item">
              <p class="review-head">{html.escape(review["head"])}</p>
              <p class="review-text">{html.escape(review["text"])}</p>
            </div>"""
        )
    return "\n".join(html_parts)


def render_sections(sections):
    parts = []
    if not sections:
        return ""
    for section in sections:
        label_raw = (section.get("label") or "").strip()
        if label_raw.casefold() == "обзор":
            label_raw = ""
        label_html = html.escape(label_raw) if label_raw else ""
        visible_lines = [line for line in section.get("lines", []) if not should_drop_line(line)]
        if not visible_lines:
            continue
        paragraphs = render_paragraph_lines_html(section.get("lines", []))
        if not paragraphs.strip():
            continue
        heading = f"          <h2>{label_html}</h2>\n" if label_html else ""
        parts.append(
            f"""      <section class="section">
        <article class="card">
{heading}          <div class="paragraph-blocks">
{paragraphs}
          </div>
        </article>
      </section>"""
        )
    return "\n\n".join(parts)


_PRICE_LINE_HTML_FN = None


def _format_price_line_html(text: str) -> str:
    """Единое форматирование строк цены (жирные цифры и т.д.) — как на сайте."""
    global _PRICE_LINE_HTML_FN
    if _PRICE_LINE_HTML_FN is None:
        root = Path(__file__).resolve().parent
        spec = importlib.util.spec_from_file_location(
            "apply_new_site_design",
            root / "tools" / "apply_new_site_design.py",
        )
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(mod)
        _PRICE_LINE_HTML_FN = mod.format_price_line_to_html
    return _PRICE_LINE_HTML_FN(text)


def render_prices(prices):
    if not prices:
        return ""
    items: list[str] = []
    for entry in prices:
        if isinstance(entry, dict):
            kind = str(entry.get("kind") or "price")
            text = str(entry.get("text") or entry.get("label") or "").strip()
            if not text:
                continue
            if kind == "heading":
                items.append(f"            <li>{html.escape(text)}</li>")
            else:
                items.append(f"            <li>{html.escape(text)}</li>")
        else:
            items.append(f"            <li>{html.escape(str(entry))}</li>")
    ul_body = "\n".join(items)
    return f"""      <section class="section">
        <article class="card price-card">
          <h2>Цены</h2>
          <ul>
{ul_body}
          </ul>
          <p class="note">Уточняйте актуальную стоимость и наличие у менеджера перед бронированием.</p>
        </article>
      </section>"""


def render_media(photo_count: int, slug: str, title: str, video_filename: str, video_post_id: Optional[int]):
    items = []
    for index in range(1, photo_count + 1):
        src = cdn_media_url(f"hotels/{slug}/photo-{index:02d}.jpg")
        items.append(
            f"            {responsive_img_html(src, f'{title} фото {index}', loading='lazy', sizes='(max-width: 720px) 92vw, (max-width: 1180px) 45vw, 520px')}"
        )
    if video_filename:
        items.append(
            f"""            <div class="video-embed">
              <video controls preload="none" playsinline class="local-video">
                <source src="/media/videos/{video_filename}" type="video/mp4" />
              </video>
              <a class="video-link" href="https://t.me/abhazbooking/{video_post_id}?single" target="_blank" rel="noopener noreferrer">Открыть видео в Telegram</a>
            </div>"""
        )
    elif video_post_id:
        items.append(
            f'            <a class="video-link" href="https://t.me/abhazbooking/{video_post_id}?single" target="_blank" rel="noopener noreferrer">Открыть видео в Telegram</a>'
        )
    return "\n".join(items)


def render_page(slug: str, message_id: int, date_text: str, parsed: dict, photo_count: int, video_filename: str, video_post_id: Optional[int]):
    title = parsed["title"].upper()
    lead = summary_text(parsed["location"], parsed["beach"], parsed["capacity"])
    og_description = lead
    media_html = render_media(photo_count, slug, title, video_filename, video_post_id)
    sections_html = render_sections(parsed["sections"])
    prices_html = render_prices(parsed["prices"])
    reviews_html = render_reviews(message_id)
    location_block = "\n".join(
        [
            f"          <p>{html.escape(parsed['location'])}</p>" if parsed["location"] else "",
            f"          <p>{html.escape(parsed['beach'])}</p>" if parsed["beach"] else "",
            f"          <p>{html.escape(parsed['capacity'])}</p>" if parsed["capacity"] else "",
        ]
    ).strip()
    if not location_block:
        location_block = "          <p>Подробности по расположению и размещению смотрите в обзоре ниже.</p>"

    return f"""<!doctype html>
<html lang="ru">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{html.escape(parsed["title"])}, Абхазия — обзор, фото, видео и цены</title>
    <meta name="description" content="{html.escape(og_description)}" />
    <meta name="robots" content="index, follow, max-image-preview:large" />
    <link rel="canonical" href="https://абхазберег.рф/hotels/{slug}/" />
    <meta property="og:type" content="article" />
    <meta property="og:title" content="{html.escape(parsed["title"])} — обзор и цены" />
    <meta property="og:description" content="{html.escape(og_description)}" />
    <meta property="og:url" content="https://абхазберег.рф/hotels/{slug}/" />
    <meta property="og:image" content="https://storage.yandexcloud.net/abhazbereg-media/media/branding/site-cover.jpg" />
    <link rel="preconnect" href="https://storage.yandexcloud.net" crossorigin />
    <link rel="icon" type="image/png" href="https://storage.yandexcloud.net/abhazbereg-media/media/branding/favicon-48.png" />
    <link rel="apple-touch-icon" href="https://storage.yandexcloud.net/abhazbereg-media/media/branding/apple-touch-icon.png" />
    <link rel="stylesheet" href="../../styles.min.css?v=202607202136" />
  </head>
  <body>
    <div class="grain" aria-hidden="true"></div>
    <main>
      <header class="hero section">
        <p class="eyebrow"><a href="/">Каталог Абхазберег</a></p>
        <h1>{html.escape(title)}</h1>
        <p class="lead">{html.escape(lead)}</p>
        <p class="updated">Обновлено: <time datetime="{date_text}">{format_human_date(date_text)}</time></p>
        <a class="btn-book" href="https://t.me/abhazbooking_online" target="_blank" rel="noopener noreferrer">Забронировать</a>
      </header>

      <section class="section">
        <article class="card">
          <h2>Фото и видео</h2>
          <p class="media-note">Источник: <a href="https://t.me/abhazbooking/{message_id}" target="_blank" rel="noopener noreferrer">@abhazbooking/{message_id}</a>.</p>
          <div class="media-grid">
{media_html}
          </div>
        </article>
      </section>

      <section class="section grid-two">
        <article class="card accent">
          <h2>Локация</h2>
{location_block}
        </article>
        <article class="card">
          <h2>Кратко</h2>
          <p>{html.escape(lead)}</p>
          <p>Данные актуальны на дату публикации страницы.</p>
        </article>
      </section>

{sections_html}

{prices_html}

      <section class="section">
        <article class="card">
          <h2>Отзывы</h2>
          <div class="reviews-scroller" aria-label="Лента отзывов">
{reviews_html}
          </div>
        </article>
      </section>

      <section class="section">
        <article class="card faq-card">
          <h2>Частые вопросы</h2>
          <div class="faq-list">
            <details>
              <summary>Где уточнить актуальное наличие номеров?</summary>
              <p>Наличие и свободные даты уточняются напрямую у менеджера через Telegram, MAX, VK или WhatsApp.</p>
            </details>
            <details>
              <summary>Цены на странице окончательные?</summary>
              <p>Нет. Цены и условия берутся из публикации и перед оплатой всегда подтверждаются у менеджера.</p>
            </details>
            <details>
              <summary>Можно ли задать дополнительные вопросы по объекту?</summary>
              <p>Да. Если важны нюансы по детям, парковке, питанию, кухне или животным, задайте их перед бронированием.</p>
            </details>
          </div>
        </article>
      </section>

      <section class="section cta-block">
        <h2>Контакты</h2>
        <p>Задать вопросы либо проверить наличие номеров можно: <strong>+7 940 900-33-40</strong> (WhatsApp, Telegram, MAX).</p>
        <p class="note">(только сообщение, звонок не пройдёт)</p>
        <div class="contact-buttons">
          <a class="btn-book" href="https://max.ru/abhazbereg" target="_blank" rel="noopener noreferrer">НАПИСАТЬ В MAX</a>
          <a class="btn-book" href="http://vk.cc/cQQnBn" target="_blank" rel="noopener noreferrer">НАПИСАТЬ В ВК</a>
          <a class="btn-book" href="https://t.me/abhazbooking_online" target="_blank" rel="noopener noreferrer">НАПИСАТЬ В TELEGRAM</a>
          <a class="btn-book" href="https://wa.me/79409003340" target="_blank" rel="noopener noreferrer">НАПИСАТЬ В WHATSAPP</a>
        </div>
      </section>
    </main>
    <script src="../../scripts.min.js?v=202607202136" defer></script>
  </body>
</html>
"""


def format_human_date(date_text: str) -> str:
    year, month, day = date_text.split("-")
    months = {
        "01": "января",
        "02": "февраля",
        "03": "марта",
        "04": "апреля",
        "05": "мая",
        "06": "июня",
        "07": "июля",
        "08": "августа",
        "09": "сентября",
        "10": "октября",
        "11": "ноября",
        "12": "декабря",
    }
    return f"{int(day)} {months[month]} {year}"


def build_card(slug: str, title: str, location: str, beach: str, capacity: str):
    card = BeautifulSoup("", "html.parser").new_tag("a")
    card["class"] = "catalog-card"
    card["data-filter-distance"] = ""
    card["data-filter-food"] = ""
    card["data-filter-price"] = ""
    card["data-filter-city"] = ""
    card["data-filter-beach"] = ""
    card["data-filter-room"] = ""
    card["data-filter-stay"] = ""
    card["href"] = f"/hotels/{slug}/"

    img = BeautifulSoup("", "html.parser").new_tag("img")
    img["src"] = cdn_media_url(f"cards/{slug}.jpg")
    img["alt"] = title
    img["loading"] = "lazy"
    card.append(img)

    h3 = BeautifulSoup("", "html.parser").new_tag("h3")
    h3.string = title.upper()
    card.append(h3)

    p = BeautifulSoup("", "html.parser").new_tag("p")
    p.string = summary_text(location, beach, capacity)
    card.append(p)
    return card


def update_index(all_pages):
    soup = BeautifulSoup(INDEX_FILE.read_text(encoding="utf-8"), "html.parser")
    grid = soup.select_one("#catalog-grid")
    if not grid:
        raise RuntimeError("Не найден #catalog-grid в index.html")

    page_map = {page["slug"]: page for page in all_pages}
    existing_anchors = {}
    for anchor in grid.select("a.catalog-card"):
        href = anchor.get("href", "")
        match = re.search(r"/hotels/([^/]+)/", href)
        if not match:
            continue
        slug = match.group(1)
        existing_anchors[slug] = anchor

    ordered_cards = []
    for page in sorted(all_pages, key=lambda item: item["source_id"], reverse=True):
        anchor = existing_anchors.get(page["slug"])
        if anchor is None:
            anchor = build_card(
                page["slug"],
                page["title"],
                page.get("location", ""),
                page.get("beach", ""),
                page.get("capacity", ""),
            )
        ordered_cards.append(anchor)

    grid.clear()
    for anchor in ordered_cards:
        grid.append(anchor)
        grid.append("\n")

    INDEX_FILE.write_text(str(soup), encoding="utf-8")


def update_sitemap(all_pages):
    entries = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    entries.append("  <url>")
    entries.append("    <loc>https://абхазберег.рф/</loc>")
    entries.append("  </url>")
    entries.append("  <url>")
    entries.append("    <loc>https://абхазберег.рф/kvartira/</loc>")
    entries.append("  </url>")
    for page in sorted(all_pages, key=lambda item: item["source_id"], reverse=True):
        entries.append("  <url>")
        entries.append(f"    <loc>https://абхазберег.рф/hotels/{page['slug']}/</loc>")
        entries.append("  </url>")
    entries.append("</urlset>")
    SITEMAP_FILE.write_text("\n".join(entries) + "\n", encoding="utf-8")


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    posts = fetch_channel_posts()
    (OUTPUT_DIR / "abhazbooking_2026_posts.json").write_text(json.dumps(posts, ensure_ascii=False, indent=2), encoding="utf-8")

    existing_pages = extract_existing_pages()
    existing_page_ids = {page["source_id"] for page in existing_pages}
    existing_slugs = {page["slug"] for page in existing_pages}
    pages_by_source = {page["source_id"]: page for page in existing_pages}

    candidates = [post for post in posts if is_object_post(post["text"])]
    managed_ids = set()
    if REPORT_FILE.exists():
        try:
            report_data = json.loads(REPORT_FILE.read_text(encoding="utf-8"))
            managed_ids = {item["source_id"] for item in report_data.get("created", [])}
        except Exception:
            managed_ids = set()
    posts_to_sync = [post for post in candidates if post["id"] not in existing_page_ids or post["id"] in managed_ids]

    created = []
    for post in posts_to_sync:
        parsed = parse_post(post["text"])
        if not parsed["title"]:
            continue
        existing_page = pages_by_source.get(post["id"])
        if existing_page:
            slug = existing_page["slug"]
        else:
            slug = build_slug(parsed["title"], post["id"], existing_slugs)
            existing_slugs.add(slug)

        photo_urls, video_url = extract_media_urls(post["html"])
        hotel_media_dir = MEDIA_HOTELS_DIR / slug
        hotel_media_dir.mkdir(parents=True, exist_ok=True)

        photo_count = 0
        for index, photo_url in enumerate(photo_urls, start=1):
            destination = hotel_media_dir / f"photo-{index:02d}.jpg"
            if download_binary(photo_url, destination):
                photo_count += 1

        if photo_count == 0:
            continue

        shutil.copyfile(hotel_media_dir / "photo-01.jpg", MEDIA_CARDS_DIR / f"{slug}.jpg")

        video_filename = ""
        video_post_id = post["id"] if video_url else None
        if video_url:
            video_filename = f"{slug}-{post['id']}.mp4"
            if not download_binary(video_url, MEDIA_VIDEOS_DIR / video_filename):
                video_filename = ""

        page_dir = HOTELS_DIR / slug
        page_dir.mkdir(parents=True, exist_ok=True)
        page_html = render_page(slug, post["id"], post["date"], parsed, photo_count, video_filename, video_post_id)
        (page_dir / "index.html").write_text(page_html, encoding="utf-8")

        created.append(
            {
                "slug": slug,
                "source_id": post["id"],
                "title": parsed["title"],
                "location": parsed["location"],
                "beach": parsed["beach"],
                "capacity": parsed["capacity"],
            }
        )

    all_pages = [page for page in existing_pages if page["source_id"] not in {item["source_id"] for item in created}] + created
    update_index(all_pages)
    update_sitemap(all_pages)

    report = {
        "created_count": len(created),
        "created": created,
        "existing_count": len(existing_pages),
        "current_total": len(all_pages),
        "removed_count": 0,
        "removed": [],
    }
    (OUTPUT_DIR / "abhazbooking_sync_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
