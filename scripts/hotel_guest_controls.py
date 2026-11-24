"""Узкие элементы выбора гостей для двух динамических отелей."""
from bs4 import BeautifulSoup


def attach_controls(soup, live, hotel):
    live['data-hotel'] = hotel
    live.find('p').string = 'Стоимость номера за одну ночь для выбранного состава гостей.'
    date = live.select_one('.gega-price-picker').extract()
    date.select_one('input').attrs.pop('disabled', None)
    meal = live.select_one('.gega-price-picker')
    if meal:
        meal.extract()
    form = BeautifulSoup(f'''<form class="hotel-guest-form" data-guest-form>
      <div class="hotel-guest-grid">
      <div class="gega-price-picker"><label for="{hotel}-adults">Взрослые</label><select id="{hotel}-adults" data-guest-adults></select></div>
      <div class="gega-price-picker"><label for="{hotel}-children">Дети</label><select id="{hotel}-children" data-guest-children></select></div>
      </div><div class="hotel-child-ages" data-child-ages aria-live="polite" hidden></div>
      <button type="submit" class="hotel-guest-submit" data-guest-search>Показать цены</button>
      </form>''','html.parser').form
    for selector, values, default in [('[data-guest-adults]',range(1,11),2),('[data-guest-children]',range(6),0)]:
        for value in values:
            option = soup.new_tag('option',value=str(value))
            option.string = str(value)
            if value == default:
                option['selected'] = ''
            form.select_one(selector).append(option)
    form.insert(0,date)
    if meal:
        form.select_one('[data-guest-search]').insert_before(meal)
    live.select_one('[data-gega-status]').insert_before(form)
    for marker in ('data-gega-live','data-shambala-live'):
        script = soup.select_one('script['+marker+']')
        if script:
            script['src'] = '/assets/hotel-live-prices-v3.js'
    if not soup.select_one('script[data-hotel-guest-source]'):
        source_script = soup.new_tag('script',attrs={'src':'/assets/hotel-guest-source-v1.js','defer':'','data-hotel-guest-source':''})
        first = soup.select_one('script[data-gega-live],script[data-shambala-live]')
        first.insert_before(source_script)
    if not soup.select_one('link[data-hotel-guest-controls]'):
        soup.head.append(soup.new_tag('link',attrs={'rel':'stylesheet','href':'/assets/hotel-guest-controls-v1.css','data-hotel-guest-controls':''}))
