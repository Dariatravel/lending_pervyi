/* Публичные расчёты отелей. Никаких ключей, броней или ручных доплат. */
(function (root) {
  'use strict';
  const GEGA = 'https://bookonline24.ru/api/v1/';
  const TL = 'https://ab-ibe.tlintegration.com/ApiWebDistribution/BookingForm/';
  const sorted = values => [...values].sort((a,b) => a-b);
  const ageLabel = age => age === 0 ? 'до 1 года' : `${age} ${age === 1 ? 'год' : age >= 2 && age <= 4 ? 'года' : 'лет'}`;
  const equalAges = (a,b) => JSON.stringify(sorted(a)) === JSON.stringify(sorted(b));
  function validateQuery(q) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(q.night) || !Number.isFinite(Date.parse(q.night)) ||
        new Date(q.night).toISOString().slice(0,10) !== q.night ||
        !Number.isInteger(q.adults) || q.adults < 1 || q.adults > 10 ||
        !Array.isArray(q.ages) || q.ages.length > 5 ||
        q.ages.some(age => !Number.isInteger(age) || age < 0 || age > 17)) {
      throw Error('Проверьте дату, количество гостей и возраст каждого ребёнка.');
    }
    return q;
  }
  const endNight = night => new Date(Date.parse(night+'T00:00:00Z')+86400000).toISOString().slice(0,10);
  function amount(value) {
    if (!Number.isFinite(value) || value <= 0 || value >= 10000000) throw Error('Отель не вернул точную стоимость.');
    return value;
  }
  function money(value) {
    if (!value || !Number.isInteger(value.roubles) || !Number.isInteger(value.copecks) ||
        value.roubles < 0 || value.copecks < 0 || value.copecks > 99) throw Error('Неизвестный формат цены отеля.');
    return amount(value.roubles + value.copecks / 100);
  }
  function categories(entities, idKey) {
    if (!Array.isArray(entities) || entities.length !== 9 || new Set(entities.map(c => c[idKey])).size !== 9 ||
        entities.some(c => !c[idKey] || typeof c.name !== 'string')) throw Error('Категории отеля требуют проверки.');
    return entities.map(c => ({id:c[idKey],category:c.name,available:0,tariffs:[]}));
  }
  function gegaChildren(info, ages) {
    const settings = info.childrenSettings;
    if (!Array.isArray(settings)) throw Error('Условия детского размещения требуют проверки.');
    for (const age of ages) {
      if (!settings.some(s => age >= s.interval.from && age <= s.interval.to)) {
        throw Error('Система Геги не даёт точный расчёт для выбранного возраста ребёнка. Уточните цену у менеджера.');
      }
    }
    for (const setting of settings) {
      const count = ages.filter(age => age >= setting.interval.from && age <= setting.interval.to).length;
      if (Number.isInteger(setting.maxOnBooking) && count > setting.maxOnBooking) {
        throw Error('Для такого количества детей нужен расчёт менеджера отеля.');
      }
    }
  }
  function normalizeGega(entities, rates, offers, q) {
    validateQuery(q);
    const result = categories(entities, 'id');
    const names = new Map(rates.map(r => [r.id,r.name]));
    if (!Array.isArray(offers)) throw Error('Неизвестный ответ Геги.');
    for (const offer of offers) {
      const category = result.find(c => c.id === offer.roomCategoryId);
      if (!category) throw Error('Неизвестная категория Геги.');
      const a = offer.accommodation;
      // Источник иногда уменьшает число взрослых или игнорирует детей.
      if (!a || a.searchedAdultsCount !== q.adults || a.searchedChildrenCount !== q.ages.length ||
          !equalAges((a.childrenAccommodation || []).map(c => c.age),q.ages) ||
          offer.dateFrom?.slice(0,10) !== q.night || offer.dateTo?.slice(0,10) !== endNight(q.night)) continue;
      if (!Number.isInteger(offer.availableCount) || offer.availableCount <= 0) continue;
      for (const p of a.prices || []) {
        if (p.totalAdultCount !== q.adults || p.totalChildrenCount !== q.ages.length) continue;
        if (!names.has(p.rateId)) throw Error('Тариф Геги требует проверки.');
        const notes = [];
        if ((p.childrenWithoutPlace || []).length) notes.push('Ребёнок без отдельного места');
        if (p.totalAdultOnAdditionalPlace > 0 || (p.childrenOnAdditionalPlace || []).length) notes.push('Дополнительное место включено в расчёт');
        category.available = Math.max(category.available,offer.availableCount);
        category.tariffs.push({name:names.get(p.rateId),price:money(p.price),meal:'Питание уточняется',notes:notes.join('. ')});
      }
    }
    return result;
  }
  function shambalaParams(q) {
    validateQuery(q);
    return {'criterions[0].hotels[0].code':'64223','criterions[0].dates':q.night+';'+endNight(q.night),
      'criterions[0].adults':String(q.adults),'criterions[0].children':q.ages.join(';'),
      include_rates:'true',include_all_placements:'false',include_promo_restricted:'false',language:'ru-ru'};
  }
  function normalizeShambala(hotel, data, q) {
    validateQuery(q);
    if (hotel.code !== '64223' || !Array.isArray(data.room_stays)) throw Error('Неизвестный ответ Шамбалы.');
    const result = categories(hotel.room_types,'code');
    const rates = new Map(hotel.rate_plans.map(r => [r.code,r.name]));
    const quotas = new Map((data.room_type_quotas || []).map(r => [r.rph,r.quantity]));
    const mealCodes = new Map((hotel.services || []).filter(s => s.kind === 'meal').map(s => [s.code,s.meal_plan_type]));
    const included = new Map((data.services || []).filter(s => s.inclusive === true && mealCodes.has(s.code)).map(s => [s.rph,mealCodes.get(s.code)]));
    for (const stay of data.room_stays) {
      if (stay.room_types?.length !== 1 || stay.rate_plans?.length !== 1) throw Error('Состав номера и тарифа требует проверки.');
      const guests = stay.guests || [];
      if (guests.some(g => !Number.isInteger(g.count) || g.count < 1)) throw Error('Неизвестный состав гостей.');
      const adults = guests.filter(g => g.age == null).reduce((n,g) => n+g.count,0);
      const ages = guests.filter(g => g.age != null).flatMap(g => Array(g.count).fill(g.age));
      if (adults !== q.adults || !equalAges(ages,q.ages) ||
          stay.stay_dates?.start_date.slice(0,10) !== q.night || stay.stay_dates?.end_date.slice(0,10) !== endNight(q.night)) continue;
      if (stay.total?.currency !== 'RUB') throw Error('Валюта отеля требует проверки.');
      const price = amount(stay.total.price_after_tax);
      const meals = (stay.services || []).map(s => included.get(s.rph)).filter(Boolean);
      const notes = [];
      for (const guest of guests.filter(g => g.age != null)) {
        if (guest.placement.kind.includes('without_bed')) notes.push(`Без отдельного места: ребёнок ${ageLabel(guest.age)}`);
        if (guest.placement.kind.startsWith('extra_')) notes.push(`Дополнительное место включено в расчёт (ребёнок: ${ageLabel(guest.age)})`);
      }
      for (const room of stay.room_types || []) {
        const category = result.find(c => c.id === room.code);
        if (!category) throw Error('Неизвестная категория Шамбалы.');
        const count = quotas.get(room.room_type_quota_rph) ?? room.limited_inventory_count;
        if (!Number.isInteger(count) || count <= 0) continue;
        for (const rate of stay.rate_plans || []) {
          const name = rates.get(rate.code);
          if (!name) throw Error('Неизвестный тариф Шамбалы.');
          const lower = name.toLowerCase();
          const meal = meals.includes('breakfast') ? 'Завтрак включён' :
            lower.includes('без питания') ? 'Без питания' : lower.includes('без завтрака') ? 'Без завтрака' : 'Питание уточняется';
          category.available = Math.max(category.available,count);
          category.tariffs.push({name,price,meal,notes:notes.join('. ')});
        }
      }
    }
    return result;
  }
  async function json(url, signal, body) {
    const response = await fetch(url,{signal,cache:'no-store',credentials:'omit',
      ...(body ? {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)} : {})});
    if (!response.ok) throw Error('Не удалось получить расчёт отеля. Попробуйте ещё раз.');
    return response.json();
  }
  const metadata = {};
  async function getMetadata(hotel, signal) {
    if (!metadata[hotel] || Date.now()-metadata[hotel].at > 600000) {
      const value = hotel === 'gega' ? await Promise.all([
        json(GEGA+'daily/hotel-gega/entities',signal),json(GEGA+'daily/hotel-gega/rates',signal),json(GEGA+'hotelInfo/hotel-gega',signal)
      ]) : await json(TL+'hotel_info?'+new URLSearchParams({'hotels[0].code':'64223',language:'ru-ru'}),signal);
      metadata[hotel] = {at:Date.now(),value};
    }
    return metadata[hotel].value;
  }
  async function getPrices(hotel, q, signal) {
    validateQuery(q);
    if (!['gega','shambala'].includes(hotel)) throw Error('Неизвестный отель.');
    const meta = await getMetadata(hotel,signal);
    let result;
    if (hotel === 'gega') {
      const [entities,rates,info] = meta;
      if (info.currencyCode !== 'RUB') throw Error('Валюта Геги требует проверки.');
      gegaChildren(info,q.ages);
      const offers = await json(GEGA+'daily/hotel-gega/accommodation-prices/all',signal,
        {dateFrom:q.night,dateTo:endNight(q.night),adultsCount:q.adults,children:q.ages.map(age => ({age})),roomCategoryId:entities[0].id});
      result = normalizeGega(entities,rates,offers,q);
    } else {
      const hotelInfo = meta.hotels?.find(h => h.code === '64223');
      if (!hotelInfo) throw Error('Не найден справочник Шамбалы.');
      const data = await json(TL+'hotel_availability?'+new URLSearchParams(shambalaParams(q)),signal);
      result = normalizeShambala(hotelInfo,data,q);
    }
    return {categories:result,checked_at:new Date().toISOString()};
  }
  const api = {validateQuery,endNight,money,gegaChildren,normalizeGega,shambalaParams,normalizeShambala,getPrices};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.HotelGuestPrices = api;
})(typeof window === 'undefined' ? {} : window);
