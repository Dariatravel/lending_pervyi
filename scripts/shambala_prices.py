"""Публичный блок цен только Шамбалы, устойчивый к пересборке Telegram."""
from bs4 import BeautifulSoup, NavigableString

SLUG = 'shambala-eko-otel-na-beregu-morya-s-basseynom-5520'


def apply_to_page_html(page_html, slug):
    if slug != SLUG:
        return page_html
    soup = BeautifulSoup(page_html, 'html.parser')
    old = soup.select_one('#prices')
    grid = soup.select_one('.hotel-site-concept__detail-grid')
    if not old or not grid:
        return page_html
    source = old.select_one('[data-shambala-source]')
    original = source or old.select_one('.price-card')
    if not original:
        raise ValueError('Не найден исходный прайс Шамбалы')
    original.extract()
    original.attrs.pop('data-shambala-source', None)
    original.attrs.pop('hidden', None)
    section = BeautifulSoup('''<section id="prices" class="section hotel-price-section gega-prices">
      <article class="card gega-live" data-hotel="shambala">
      <h2>Актуальные цены на выбранную ночь</h2>
      <p>Стоимость номера за одну ночь для 2 взрослых без детей. Для другого состава гостей обратитесь к менеджеру.</p>
      <div class="gega-price-picker"><label for="shambala-night">Дата ночи проживания</label>
      <input id="shambala-night" type="date" disabled></div>
      <div class="gega-price-picker"><label for="shambala-meal">Питание</label>
      <select id="shambala-meal" data-live-meal disabled><option value="">Любое питание</option></select></div>
      <p data-gega-status role="status">Загружаем цены отеля…</p>
      <div data-gega-live-table></div>
      <p class="gega-price-note">Показываем самую низкую цену для выбранного питания. Название тарифа указано рядом с ценой. В тарифах с пометкой «Завтрак включён» он входит в указанную цену.</p>
      <p class="gega-price-note">Окончательную стоимость поездки и условия бронирования подтвердит менеджер.</p>
      <noscript>Для просмотра актуальных цен включите JavaScript или напишите менеджеру.</noscript>
      </article>
      <details class="gega-reference"><summary>Справочный прайс и доплаты из публикаций отеля</summary>
      <p>Ранее опубликованный прайс может отличаться от актуальных цен выше. Доплаты подтвердит менеджер.</p>
      <div data-shambala-source></div></details></section>''', 'html.parser').section
    # Оригинальная price-card и ul остаются доступны штатному аудиту и обновлению Telegram.
    container = section.select_one('[data-shambala-source]')
    original['data-shambala-source'] = ''
    container.replace_with(original)
    before, after = old.previous_sibling, old.next_sibling
    if (isinstance(before, NavigableString) and isinstance(after, NavigableString)
            and not before.strip() and not after.strip()):
        before.extract()
    old.decompose()
    grid.insert(0, section)
    for marker, href in [('data-shambala-prices', '/assets/gega-prices-v1.css'),
                         ('data-shambala-live', '/assets/gega-live-prices-v1.css')]:
        if not soup.select_one('link[' + marker + ']'):
            soup.head.append(soup.new_tag('link', attrs={'rel': 'stylesheet', 'href': href, marker: ''}))
    if not soup.select_one('script[data-shambala-live]'):
        soup.body.append(soup.new_tag('script', attrs={'src': '/assets/hotel-live-prices-v2.js',
                                                    'defer': '', 'data-shambala-live': ''}))
    from hotel_guest_controls import attach_controls
    attach_controls(soup, section.select_one('.gega-live'), 'shambala')
    return str(soup)
