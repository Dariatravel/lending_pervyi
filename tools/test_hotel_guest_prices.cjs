'use strict';
const assert = require('node:assert/strict');
const api = require('../assets/hotel-guest-source-v1.js');
const q = {night:'2027-07-20',adults:2,ages:[5]};
const rooms = Array.from({length:9},(_,i)=>({id:String(i),code:String(i),name:'Номер '+i}));
const clone = x => JSON.parse(JSON.stringify(x));
let tests = 0;
function test(name,fn) {fn();tests++;console.log('OK '+name);}
function gegaOffer(adults,ages) {
  return {roomCategoryId:'0',availableCount:2,dateFrom:q.night,dateTo:'2027-07-21',
    accommodation:{searchedAdultsCount:adults,searchedChildrenCount:ages.length,
      childrenAccommodation:ages.map(age=>({age})),prices:[{totalAdultCount:adults,totalChildrenCount:ages.length,
        rateId:'r',price:{roubles:8500,copecks:50},childrenWithoutPlace:ages.map(age=>({age}))}]}};
}
const hotel = {code:'64223',room_types:rooms,rate_plans:[{code:'r',name:'С завтраком'}],
  services:[{code:'breakfast',kind:'meal',meal_plan_type:'breakfast'}]};
function tlData(age=5) {
  return {room_type_quotas:[{rph:11,quantity:2}],services:[{rph:4,code:'breakfast',inclusive:true}],room_stays:[{
    guests:[{count:2,placement:{kind:'adult'}},{age,count:1,placement:{kind:age===17?'extra_adult':'child_band_without_bed'}}],
    room_types:[{code:'0',room_type_quota_rph:11}],rate_plans:[{code:'r'}],
    stay_dates:{start_date:q.night+' 14:00:00',end_date:'2027-07-21 12:00:00'},
    total:{currency:'RUB',price_after_tax:12060},services:[{rph:4}]}]};
}
test('проверка количества и возраста',()=>{
  for (const change of [{adults:0},{adults:11},{adults:2.5},{ages:[null]},{ages:[18]},{ages:[-1]},{night:'2027-02-30'}]) {
    assert.throws(()=>api.validateQuery({...q,...change}));
  }
  assert.equal(api.validateQuery(q),q);
});
test('переход месяца и года',()=>{
  assert.equal(api.endNight('2026-12-31'),'2027-01-01');
  assert.equal(api.endNight('2028-02-28'),'2028-02-29');
});
test('точная денежная сумма без округления и выдуманных доплат',()=>{
  assert.equal(api.money({roubles:8500,copecks:50}),8500.5);
  for (const value of [null,{roubles:100,copecks:100},{roubles:-1,copecks:0},{roubles:0,copecks:0}]) assert.throws(()=>api.money(value));
});
test('Гега не публикует цену на двоих при запросе троих',()=>{
  const result=api.normalizeGega(rooms,[{id:'r',name:'Тариф'}],[gegaOffer(2,[])],{...q,adults:3,ages:[]});
  assert.equal(result[0].tariffs.length,0);
});
test('Гега не публикует цену, если источник проигнорировал ребёнка',()=>{
  const result=api.normalizeGega(rooms,[{id:'r',name:'Тариф'}],[gegaOffer(2,[])],q);
  assert.equal(result[0].tariffs.length,0);
});
test('Гега подтверждённый младенец без отдельного места',()=>{
  const result=api.normalizeGega(rooms,[{id:'r',name:'Тариф'}],[gegaOffer(2,[0])],{...q,ages:[0]});
  assert.equal(result[0].tariffs[0].price,8500.5);
  assert.match(result[0].tariffs[0].notes,/без отдельного места/i);
});
test('возрастной предел Геги и лимит младенцев не обходятся',()=>{
  const info={childrenSettings:[{interval:{from:0,to:1},maxOnBooking:1}]};
  api.gegaChildren(info,[0]);api.gegaChildren(info,[1]);
  assert.throws(()=>api.gegaChildren(info,[5]));
  assert.throws(()=>api.gegaChildren(info,[0,1]));
});
test('Шамбала передаёт каждого ребёнка, включая нулевой возраст',()=>{
  assert.equal(api.shambalaParams({...q,ages:[0,5]})['criterions[0].children'],'0;5');
  assert.equal(api.shambalaParams(q)['criterions[0].adults'],'2');
});
test('Шамбала цена, включённое питание и отсутствие отдельного места',()=>{
  const result=api.normalizeShambala(hotel,tlData(),q);
  assert.equal(result.length,9);assert.equal(result[0].tariffs[0].price,12060);
  assert.equal(result[0].tariffs[0].meal,'Завтрак включён');
  assert.match(result[0].tariffs[0].notes,/5 лет/);
  assert.match(result[0].tariffs[0].notes,/без отдельного места/i);
});
test('подросток в категории extra_adult остаётся учтённым ребёнком возраста17',()=>{
  const result=api.normalizeShambala(hotel,tlData(17),{...q,ages:[17]});
  assert.equal(result[0].tariffs.length,1);assert.match(result[0].tariffs[0].notes,/17 лет/);
});
test('Шамбала чужой состав, дата, нулевой остаток и питание не подставляются',()=>{
  for (const mutate of [d=>{d.room_stays[0].guests.pop();},d=>{d.room_stays[0].stay_dates.start_date='2027-07-19';},d=>{d.room_type_quotas[0].quantity=0;}]) {
    const data=tlData();mutate(data);assert.equal(api.normalizeShambala(hotel,data,q)[0].tariffs.length,0);
  }
  const data=tlData();data.services[0].inclusive=false;
  assert.equal(api.normalizeShambala(hotel,data,q)[0].tariffs[0].meal,'Питание уточняется');
});
test('чужая валюта, неизвестный тариф, состав из нескольких номеров отвергаются',()=>{
  for (const mutate of [d=>{d.room_stays[0].total.currency='USD';},d=>{d.room_stays[0].rate_plans[0].code='other';},d=>{d.room_stays[0].room_types.push({code:'1'});}]) {
    const data=tlData();mutate(data);assert.throws(()=>api.normalizeShambala(hotel,data,q));
  }
});
console.log(`Проверено сценариев: ${tests}`);
