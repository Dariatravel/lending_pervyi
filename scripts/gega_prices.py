"""Presentation-only pilot for one hotel. Source tariffs remain in Telegram/manifest."""
from __future__ import annotations

from copy import copy
import html
import re

from bs4 import BeautifulSoup

SLUG = 'gega-otel-s-basseynom-i-zavtrakami-5510'
ASSET = '/assets/gega-prices-v1'
ROOMS = {
    'Стандарт без балкона', 'Стандарт с раздельными кроватями без балкона',
    'Стандарт с выходом к бассейну', 'Большой стандарт с выходом к бассейну',
    'Стандарт с балконом', 'Делюкс с балконом', 'Полулюкс с балконом',
    'Семейный полулюкс с балконом', 'Люкс',
}


def parse_lines(lines):
    periods, notes = [], []
    current = None
    for value in lines:
        line = value.strip()
        if not line or line == 'Цены с 30 апреля:':
            continue
        meal = re.search(r'\s+(?:-\s*)?с\s+завтрак.*$', line, re.I)
        if re.match(r'^[СC]\s+\d', line) and '₽' not in line:
            title = line[:meal.start()].strip(' -–') if meal else line
            food = meal.group().strip(' -–').replace('. Новый год 🎄', '') if meal else ''
            if 'Новый год' in line and 'Новый год' not in title:
                title += ' · Новый год'
            current = {'title': title, 'food': food, 'rows': []}
            periods.append(current)
            continue
        match = re.fullmatch(r'(\d[\d \u00a0]*)\s*₽\s*[-–]\s*(.+)', line)
        if match and match[2] in ROOMS:
            if current is None:
                raise ValueError('Gega tariff without period')
            room = match[2]
            if any(row['room'] == room for row in current['rows']):
                raise ValueError('Gega duplicate room in period')
            current['rows'].append({'room': room, 'amount': int(match[1].replace(' ', '').replace('\u00a0', '')),
                                    'guests': 3 if room.startswith(('Семейный полулюкс', 'Люкс')) else 2})
        else:
            # Never silently classify a new room or malformed tariff as an extra.
            if match and not re.match(r'Дети\b|ужин\b', match[2], re.I):
                raise ValueError('Unknown Gega tariff line')
            notes.append(line)
    if not periods or any(len(p['rows']) != 8 or not p['food'] for p in periods):
        raise ValueError('Incomplete Gega tariff period')
    return periods, notes


def table(period):
    e = html.escape
    rows = ''.join(
        f'<tr><th scope="row">{e(r["room"])}</th><td>{r["guests"]} гостя</td>'
        f'<td class="gega-price-amount">{r["amount"]:,} ₽</td></tr>'.replace(',', '\u202f')
        for r in period['rows'])
    food = {'с завтраком':'завтрак', 'с завтраками и ужинами':'завтрак и ужин',
            'с завтраком и ужином':'завтрак и ужин'}.get(period['food'].lower(),period['food'])
    return (f'<p class="gega-food">В тариф включено: {e(food)}.</p>'
            '<table class="gega-price-table"><caption>Стоимость номера за сутки</caption>'
            '<thead><tr><th scope="col">Категория номера</th><th scope="col">В цене</th>'
            '<th scope="col">За сутки</th></tr></thead><tbody>'+rows+'</tbody></table>')


def apply_to_page_html(page_html: str, slug: str) -> str:
    if slug != SLUG:
        return page_html  # Important: all other pages stay byte-for-byte identical.
    soup = BeautifulSoup(page_html, 'html.parser')
    old = soup.select_one('#prices')
    grid = soup.select_one('.hotel-site-concept__detail-grid')
    if not old or not grid:
        return page_html
    # Existing pilot pages keep the complete source list for future regeneration.
    source = old.select_one('[data-gega-source]')
    winter_lines = [li.get_text(' ', strip=True, types=None) for li in (source or old).select('li')]
    supplemental = soup.select_one('#supplemental-comments, #room-overviews')
    summer = None
    if supplemental:
        for card in supplemental.select('.room-overview-card'):
            heading = card.find('h3')
            if heading and heading.get_text(strip=True) == 'Цены с 30 апреля:':
                summer = card
                break
    stored_summer = old.select_one('[data-gega-summer-source]')
    if summer is not None:
        paragraph = summer.find('p')
        if not paragraph:
            raise ValueError('Missing Gega summer source')
        summer_text = paragraph.get_text('\n')
    elif stored_summer is not None and supplemental is None:
        summer_text = stored_summer.get_text(types=None)
    else:
        summer_text = ''  # A removed summer publication must not keep old tariffs.
    winter, notes = parse_lines(winter_lines)
    basis = ' '.join(winter_lines).lower().replace('ё','е')
    if ('за двухместное размещение' not in basis or
            'для номеров семейный полулюкс и люкс за трехместное размещение' not in basis):
        raise ValueError('Gega guest basis changed; confirm source before publishing')
    summer_periods, summer_notes = parse_lines(summer_text.splitlines()) if summer_text else ([],[])
    if any(re.search(r'размещени|основных мест|за \d+ гост',note,re.I) for note in summer_notes):
        raise ValueError('Separate summer guest basis requires confirmation')
    periods = winter + summer_periods
    if len({p['title'] for p in periods}) != len(periods):
        raise ValueError('Duplicate Gega tariff periods')
    # Basis is displayed next to every price; keep original basis in source too.
    extras = [n for n in notes + summer_notes if not n.startswith(('(за двухместное', 'Для номеров Семейный'))]
    e = html.escape
    options = ''.join(f'<option value="{i}">{e(p["title"])}</option>' for i,p in enumerate(periods))
    panels = ''.join(f'<div data-gega-period="{i}"'+(' hidden' if i else '')+'>'
                     f'<h3>{e(p["title"])}</h3>{table(p)}</div>' for i,p in enumerate(periods))
    complete = ''.join(f'<details class="gega-all-period"><summary>{e(p["title"])}</summary>{table(p)}</details>' for p in periods)
    groups = {'Дополнительные места': [], 'Дети и питание': [], 'Сауна и другие услуги': []}
    for note in extras:
        group = ('Дополнительные места' if 'доп место' in note.lower() else
                 'Дети и питание' if re.search(r'дети|ужин|питан', note, re.I) else 'Сауна и другие услуги')
        groups[group].append(note)
    # Pet policy is already public in the description; repeat it with other extras.
    for li in soup.select('.benefit-grid li'):
        note = li.get_text(' ', strip=True)
        if 'животными' in note and '₽' in note and note not in groups['Сауна и другие услуги']:
            groups['Сауна и другие услуги'].append(note)
    extra_html = ''.join(f'<section><h4>{e(title)}</h4><ul>'+''.join(f'<li>{e(n)}</li>' for n in values)+'</ul></section>'
                         for title,values in groups.items() if values)
    section_html = (
        '<section id="prices" class="section hotel-price-section gega-prices" aria-labelledby="gega-price-heading">'
        '<article class="card"><p class="gega-eyebrow">Проживание в отеле «Гега»</p>'
        '<h2 id="gega-price-heading">Цены на ваш период</h2>'
        '<p class="gega-intro">Выберите период поездки – покажем категории номеров, питание и стоимость за сутки.</p>'
        '<div class="gega-price-picker"><label for="gega-period">Период проживания</label>'
        f'<select id="gega-period" disabled>{options}</select></div>'
        '<div class="gega-selected" aria-live="polite" aria-atomic="true">'+panels+'</div>'
        '<p class="gega-price-note">Стоимость указана за номер: для большинства категорий – на двоих, '
        'для семейного полулюкса и люкса – на троих. Дополнительные места оплачиваются отдельно.</p>'
        '<p class="gega-price-note">Цены динамические. Стоимость и наличие на конкретные даты подтвердит менеджер.</p>'
        '<details class="gega-full"><summary>Посмотреть весь прайс по периодам</summary>'+complete+'</details>'
        '<section class="gega-extras" aria-labelledby="gega-extra-heading"><h3 id="gega-extra-heading">Доплаты и дополнительные услуги</h3>'
        '<p>Завтрак или завтрак с ужином, включённые в тариф, указаны над таблицей выбранного периода.</p>'
        '<div class="gega-extra-grid">'+extra_html+'</div></section></article></section>')
    new = BeautifulSoup(section_html, 'html.parser').section
    # Динамические цены отделены от справочного прайса: состав гостей различается.
    archive = soup.new_tag('details', attrs={'class': 'gega-reference'})
    summary = soup.new_tag('summary')
    summary.string = 'Справочный прайс и доплаты из публикаций отеля'
    archive.append(summary)
    archive.append(new.select_one('article').extract())
    new.append(archive)
    live = BeautifulSoup('''<article class="card gega-live">
      <h2>Актуальные цены на выбранную ночь</h2>
      <p>Стоимость номера за одну ночь для 2 взрослых без детей. Для другого состава гостей обратитесь к менеджеру.</p>
      <div class="gega-price-picker"><label for="gega-night">Дата ночи проживания</label>
      <input id="gega-night" type="date" disabled></div>
      <p data-gega-status role="status">Загружаем цены отеля…</p>
      <div data-gega-live-table></div>
      <p class="gega-price-note">Питание зависит от тарифа. Состав питания и окончательную стоимость всей поездки подтвердит менеджер.</p>
      <noscript>Для просмотра актуальных цен включите JavaScript или напишите менеджеру.</noscript>
      </article>''', 'html.parser').article
    new.insert(0, live)
    # These source nodes preserve original text and let repeated application work.
    original = soup.new_tag('div', attrs={'data-gega-source': '', 'hidden':'', 'class':'price-card'})
    original.append(copy((source or old).select_one('ul')))
    new.append(original)
    raw = soup.new_tag('template', attrs={'data-gega-summer-source': ''})
    raw.string = summer_text
    if summer_text:
        new.append(raw)
    image_details = old.select_one('.gega-original-image') if summer_text else None
    if summer is not None and summer.find('img'):
        image_details = soup.new_tag('details', attrs={'class':'gega-original-image'})
        summary = soup.new_tag('summary');summary.string = 'Изображение из публикации летнего прайса'
        image_details.append(summary);image_details.append(copy(summer.find('img')))
    if image_details:
        archive.select_one('article').append(copy(image_details))
    old.decompose()
    if summer is not None:
        summer.decompose()
        if not supplemental.select('.room-overview-card'):
            supplemental.decompose()
    grid.insert(0,new)
    if not soup.select_one('link[data-gega-prices]'):
        soup.head.append(soup.new_tag('link', attrs={'rel':'stylesheet','href':ASSET+'.css','data-gega-prices':''}))
    if not soup.select_one('script[data-gega-prices]'):
        soup.body.append(soup.new_tag('script', attrs={'src':ASSET+'.js','defer':'','data-gega-prices':''}))
    live_script = soup.select_one('script[data-gega-live]')
    if live_script:
        live_script['src'] = '/assets/hotel-live-prices-v2.js'
    else:
        soup.body.append(soup.new_tag('script', attrs={'src':'/assets/hotel-live-prices-v2.js','defer':'','data-gega-live':''}))
    if not soup.select_one('link[data-gega-live]'):
        soup.head.append(soup.new_tag('link', attrs={'rel':'stylesheet','href':'/assets/gega-live-prices-v1.css','data-gega-live':''}))
    from hotel_guest_controls import attach_controls
    attach_controls(soup, new.select_one('.gega-live'), 'gega')
    return re.sub(r'[ \t]+\n','\n',str(soup))
