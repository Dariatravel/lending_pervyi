(() => {
  'use strict';
  const root = document.querySelector('.gega-live');
  if (!root) return;
  const input = root.querySelector('#gega-night');
  const status = root.querySelector('[data-gega-status]');
  const output = root.querySelector('[data-gega-live-table]');
  const today = () => new Intl.DateTimeFormat('sv-SE', {timeZone:'Europe/Moscow'}).format(new Date());
  let snapshot;
  const cell = (tag, text) => {
    const el = document.createElement(tag);
    el.textContent = text;
    return el;
  };
  function show() {
    output.replaceChildren();
    const night = snapshot?.nights?.[input.value];
    const age = night ? Date.now() - Date.parse(night.checked_at) : Infinity;
    if (input.value < today() || !night || !Number.isFinite(age) || age < -60000 || age > 7200000) {
      status.textContent = 'На эту ночь свежие цены пока недоступны. Уточните стоимость у менеджера.';
      return;
    }
    const table = document.createElement('table');
    table.className = 'gega-price-table';
    table.append(cell('caption', 'За номер на 2 взрослых, без детей, за одну ночь'));
    const head = document.createElement('thead');
    const titles = document.createElement('tr');
    for (const title of ['Категория номера', 'Тариф и питание', 'За ночь']) {
      const th = cell('th', title); th.scope = 'col'; titles.append(th);
    }
    head.append(titles); table.append(head);
    const body = document.createElement('tbody');
    for (const category of night.categories) {
      const offers = category.available > 0 ? category.tariffs : [];
      for (const tariff of offers.length ? offers : [null]) {
        const row = document.createElement('tr');
        const room = cell('th', category.category); room.scope = 'row'; row.append(room);
        row.append(cell('td', tariff ? `${tariff.name}. ${tariff.meal}` : 'Нет подтверждённого предложения'));
        const amount = tariff ? `${new Intl.NumberFormat('ru-RU').format(tariff.price)} ₽` : 'Уточнить';
        const price = cell('td', amount); price.className = 'gega-price-amount'; row.append(price);
        body.append(row);
      }
    }
    table.append(body); output.append(table);
    status.textContent = 'Обновлено ' + new Intl.DateTimeFormat('ru-RU', {
      timeZone:'Europe/Moscow', day:'numeric', month:'long', hour:'2-digit', minute:'2-digit'
    }).format(new Date(night.checked_at)) + ' (МСК). Наличие и цену подтвердим при бронировании.';
  }
  async function refresh() {
    try {
      const response = await fetch('https://storage.yandexcloud.net/abhazbereg-media/media/gega-live-prices/v1.json', {
        cache:'no-store', signal:AbortSignal.timeout(15000)
      });
      if (!response.ok) throw Error('snapshot');
      const data = await response.json();
      if (data.version !== 1 || data.hotel !== 'gega' || data.adults !== 2 || data.children !== 0 || !data.nights) throw Error('schema');
      snapshot = data;
      const dates = Object.keys(data.nights).filter(date => date >= today()).sort();
      input.min = today(); input.max = dates.at(-1) || today();
      if (!input.value || input.value < input.min) input.value = today();
      input.disabled = false;
      show();
    } catch (_) {
      output.replaceChildren();
      status.textContent = 'Не удалось обновить цены. Уточните стоимость у менеджера.';
    }
  }
  input.addEventListener('change', show);
  setInterval(() => { if (snapshot) show(); }, 60000);
  setInterval(refresh, 300000);
  refresh();
})();
