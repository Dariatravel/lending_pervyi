(() => {
  'use strict';
  const root = document.querySelector('.gega-live');
  const source = window.HotelGuestPrices;
  if (!root || !source) return;
  const hotel = root.dataset.hotel;
  if (!['gega','shambala'].includes(hotel)) return;
  const form = root.querySelector('[data-guest-form]');
  const night = form.querySelector('input[type="date"]');
  const adults = form.querySelector('[data-guest-adults]');
  const children = form.querySelector('[data-guest-children]');
  const agesBox = form.querySelector('[data-child-ages]');
  const meal = form.querySelector('[data-live-meal]');
  const button = form.querySelector('[data-guest-search]');
  const status = root.querySelector('[data-gega-status]');
  const output = root.querySelector('[data-gega-live-table]');
  const today = () => new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Moscow'}).format(new Date());
  let revision = 0, controller, result, resultKey = '';
  const element = (tag,text) => {const node=document.createElement(tag);node.textContent=text;return node;};
  const message = text => {status.textContent=text;status.hidden=false;};
  const query = () => ({night:night.value,adults:Number(adults.value),
    ages:[...agesBox.querySelectorAll('select')].map(select => select.value === '' ? null : Number(select.value))});
  const key = q => JSON.stringify(q);
  function invalidate() {
    revision++; controller?.abort(); button.disabled=false;
    result=null; resultKey=''; output.replaceChildren();
    message('Нажмите «Показать цены» для выбранного состава гостей.');
  }
  function childFields() {
    const previous = [...agesBox.querySelectorAll('select')].map(select => select.value);
    agesBox.replaceChildren();
    for (let i=0;i<Number(children.value);i++) {
      const wrapper=element('div','');wrapper.className='gega-price-picker';
      const id=`${hotel}-child-age-${i}`;
      const label=element('label',`Возраст ребёнка ${i+1} на дату заезда`);label.htmlFor=id;
      const select=element('select','');select.id=id;select.required=true;
      const empty=element('option','Выберите возраст');empty.value='';select.append(empty);
      for (let age=0;age<=17;age++) {
        const suffix=age===1?'год':age>=2&&age<=4?'года':'лет';
        const option=element('option',age===0?'До 1 года':`${age} ${suffix}`);option.value=String(age);select.append(option);
      }
      select.value=previous[i] || '';
      wrapper.append(label,select);agesBox.append(wrapper);
    }
    agesBox.hidden=Number(children.value)===0;
  }
  function render() {
    output.replaceChildren();
    if (!result || resultKey !== key(query())) return;
    const age=Date.now()-Date.parse(result.checked_at);
    if (!Number.isFinite(age) || age < -60000 || age > 7200000 || night.value < today()) {
      message('Цены устарели. Нажмите «Показать цены» для нового расчёта.');return;
    }
    const table=element('table','');table.className='gega-price-table';
    const q=query();table.setAttribute('aria-label',`Стоимость за ночь: взрослых ${q.adults}, детей ${q.ages.length}`);
    const head=element('thead',''),titles=element('tr','');
    for (const text of ['Категория номера','Тариф и питание','За ночь']) {
      const th=element('th',text);th.scope='col';titles.append(th);
    }
    head.append(titles);table.append(head);
    const body=element('tbody','');let count=0;
    for (const category of result.categories) {
      let offers=category.available>0?category.tariffs:[];
      if (meal) offers=offers.filter(t => !meal.value || t.meal===meal.value);
      offers=offers.slice().sort((a,b) => a.price-b.price || a.name.localeCompare(b.name,'ru')).slice(0,1);
      const tariff=offers[0];if (tariff) count++;
      const row=element('tr',''),room=element('th',category.category);room.scope='row';row.append(room);
      // В публикации Геги 5510 тариф межсезонья на 1–25 декабря указан без завтраков.
      const mealLabel = hotel === 'gega' && tariff?.name === 'Межсезонье'
        && q.night >= '2026-12-01' && q.night <= '2026-12-25'
        ? 'Без завтрака' : tariff?.meal;
      row.append(element('td',tariff?[tariff.name,mealLabel,tariff.notes].filter(Boolean).join('. '):'Нет предложения для выбранного состава и питания'));
      const price=element('td',tariff?`${new Intl.NumberFormat('ru-RU').format(tariff.price)} ₽`:'Уточнить');
      price.className='gega-price-amount';row.append(price);body.append(row);
    }
    table.append(body);output.append(table);
    if (count) {status.textContent='';status.hidden=true;}
    else message('Отель не вернул подтверждённых предложений для выбранного состава и питания. Уточните у менеджера.');
  }
  function accept(data,q,token) {
    if (token!==revision || key(q)!==key(query())) return;
    result=data;resultKey=key(q);
    if (meal) {
      const previous=meal.value;
      const values=[...new Set([...data.categories.flatMap(c => c.tariffs.map(t => t.meal)),...(previous?[previous]:[])])].sort();
      meal.replaceChildren();
      for (const value of ['',...values]) {const option=element('option',value||'Любое питание');option.value=value;meal.append(option);}
      meal.value=previous;meal.disabled=false;
    }
    render();
  }
  async function calculate(snapshot=false) {
    const q=query();
    try {source.validateQuery(q);} catch (error) {invalidate();message(error.message);return;}
    if (q.night<today() || q.night>night.max) {invalidate();message('Выберите доступную дату проживания.');return;}
    controller?.abort();controller=new AbortController();
    const current=controller,token=++revision;
    result=null;resultKey='';output.replaceChildren();button.disabled=true;message('Получаем цену для выбранного состава гостей…');
    const timeout=setTimeout(() => current.abort(),25000);
    try {
      let data;
      if (snapshot && q.adults===2 && q.ages.length===0) {
        const response=await fetch(`https://storage.yandexcloud.net/abhazbereg-media/media/${hotel}-live-prices/v1.json`,{signal:current.signal,cache:'no-store',credentials:'omit'});
        if (!response.ok) throw Error('Не удалось загрузить цены. Нажмите «Показать цены».');
        const saved=await response.json();
        if (saved.hotel!==hotel || saved.adults!==2 || saved.children!==0 || saved.version!==1) throw Error('Неизвестный состав сохранённого расчёта.');
        data=saved.nights[q.night];
        if (!data) throw Error('Нет сохранённой цены. Нажмите «Показать цены».');
      } else data=await source.getPrices(hotel,q,current.signal);
      accept(data,q,token);
    } catch (error) {
      if (token===revision) {
        output.replaceChildren();
        const explanation=/[А-Яа-яЁё]/.test(error.message || '')?error.message:'Не удалось получить расчёт отеля. Попробуйте ещё раз.';
        message(current.signal.aborted?'Отель не ответил вовремя. Попробуйте ещё раз.':explanation);
      }
    } finally {
      clearTimeout(timeout);if (token===revision) button.disabled=false;
    }
  }
  children.addEventListener('change',() => {childFields();invalidate();});
  form.addEventListener('change',event => {if (event.target!==children && event.target!==meal) invalidate();});
  form.addEventListener('submit',event => {event.preventDefault();calculate();});
  if (meal) meal.addEventListener('change',render);
  night.min=today();night.max=new Date(Date.parse(today()+'T00:00:00Z')+364*86400000).toISOString().slice(0,10);night.value=today();
  if (meal) meal.disabled=false;
  childFields();calculate(true);
  setInterval(render,60000);
  setInterval(() => {if (result && !document.hidden && resultKey===key(query())) calculate();},300000);
})();
