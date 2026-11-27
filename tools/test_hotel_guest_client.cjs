'use strict';
// Исполняем настоящий клиент. DOM-объекты и сеть заменены только на границах.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {validateQuery} = require('../assets/hotel-guest-source-v1.js');
const client = fs.readFileSync(path.join(__dirname,'../assets/hotel-live-prices-v3.js'),'utf8');
const defer = () => {let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};};
const flush = () => new Promise(resolve => setImmediate(resolve));

class Element {
  constructor(tag) {this.tag=tag;this.children=[];this.listeners={};this._text='';this._value='';this.hidden=false;this.disabled=false;}
  append(...nodes) {for(const node of nodes){node.parent=this;this.children.push(node);}}
  replaceChildren(...nodes) {this.children=[];this._value='';this._text='';this.append(...nodes);}
  set textContent(value) {this._text=String(value);this.children=[];}
  get textContent() {return this._text+this.children.map(node=>node.textContent).join('');}
  set value(value) {this._value=String(value);}
  get value() {
    if(this.tag!=='select')return this._value;
    return this.children.some(node=>node.value===this._value)?this._value:(this.children[0]?.value||'');
  }
  setAttribute(name,value) {this[name]=String(value);}
  addEventListener(type,callback) {(this.listeners[type] ||= []).push(callback);}
  emit(type) {
    const event={target:this,preventDefault(){}};
    for(let node=this;node;node=node.parent)for(const callback of node.listeners[type]||[])callback(event);
  }
  querySelector(selector) {return this.selectors?.[selector] || this.querySelectorAll(selector)[0] || null;}
  querySelectorAll(selector) {
    const found=[];
    for(const node of this.children){if(node.tag===selector)found.push(node);found.push(...node.querySelectorAll(selector));}
    return found;
  }
}

function harness(hotel = 'shambala', date = '2026-11-24') {
  let now=Date.parse(date+'T15:00:00Z');
  class Clock extends Date {constructor(...args){super(...(args.length?args:[now]));}static now(){return now;}}
  const root=new Element('article');root.dataset={hotel};
  const form=new Element('form'),night=new Element('input'),adults=new Element('select'),children=new Element('select');
  const ages=new Element('div'),meal=new Element('select'),button=new Element('button'),status=new Element('p'),output=new Element('div');
  const option=(select,value)=>{const node=new Element('option');node.value=String(value);select.append(node);};
  for(let i=1;i<=10;i++)option(adults,i);adults.value='2';
  for(let i=0;i<=5;i++)option(children,i);children.value='0';option(meal,'');
  form.append(night,adults,children,ages,meal,button);root.append(form,status,output);
  form.selectors={'input[type="date"]':night,'[data-guest-adults]':adults,'[data-guest-children]':children,
    '[data-child-ages]':ages,'[data-live-meal]':hotel==='shambala'?meal:null,'[data-guest-search]':button};
  root.selectors={'[data-guest-form]':form,'[data-gega-status]':status,'[data-gega-live-table]':output};
  const initial=defer(),requests=[],intervals=[];
  const source={validateQuery,getPrices(hotel,q,signal){const pending=defer();requests.push({hotel,q:JSON.parse(JSON.stringify(q)),signal,...pending});return pending.promise;}};
  const context={window:{HotelGuestPrices:source},document:{hidden:false,querySelector:()=>root,createElement:tag=>new Element(tag)},
    Date:Clock,Intl,AbortController,setTimeout:()=>1,clearTimeout(){},setInterval:callback=>intervals.push(callback),
    fetch:(url,options)=>{if(url==='/assets/gega-meals.json')return Promise.resolve({ok:true,json:async()=>[{start:'2026-12-01',end:'2026-12-25',meal:'Без завтрака'}]});initial.signal=options.signal;return initial.promise;}};
  vm.runInNewContext(client,context,{filename:'hotel-live-prices-v3.js'});
  const data=(price=9900,payment='Без питания')=>({checked_at:new Clock().toISOString(),categories:Array.from({length:9},(_,i)=>({
    category:'Номер '+i,available:1,tariffs:[{name:'Тариф',meal:payment,price,notes:''}]}))});
  const start=async(value=data())=>{
    const saved={hotel,adults:2,children:0,version:1,nights:{[night.value]:value}};
    initial.resolve({ok:true,json:async()=>saved});await flush();
  };
  const price=()=>{
    const table=output.children[0];if(!table)return null;
    return table.children[1].children[0].children[2].textContent;
  };
  return {root,form,night,adults,children,ages,meal,button,status,output,initial,requests,intervals,data,start,price,
    advance(ms){now+=ms;},change(node,value){node.value=String(value);node.emit('change');},submit(){form.emit('submit');}};
}

(async()=>{
  let passed=0;
  async function test(name,callback){await callback();passed++;console.log('OK '+name);}

  await test('Гега показывает «Без завтрака» только с 1 по 25 декабря',async()=>{
    for (const [date,expected] of [['2026-11-30',false],['2026-12-01',true],['2026-12-25',true],['2026-12-26',false]]) {
      const h=harness('gega',date);
      const data=h.data(2200,'Питание уточняется');
      data.categories.forEach(c=>{c.tariffs[0].name='Межсезонье';});
      await h.start(data);
      assert.equal(h.output.textContent.includes('Без завтрака'),expected);
      assert.match(h.price(),/2\s?200/);
    }
  });

  await test('выбранный завтрак сохраняется, когда новый состав не имеет такого тарифа',async()=>{
    const h=harness(),initial=h.data(12060,'Завтрак включён');
    initial.categories.forEach(c=>c.tariffs.push({name:'Без питания',meal:'Без питания',price:9900}));
    await h.start(initial);h.change(h.meal,'Завтрак включён');assert.match(h.price(),/12\s?060/);
    h.change(h.adults,3);assert.equal(h.output.children.length,0);h.submit();
    h.requests[0].resolve(h.data(11880,'Без питания'));await flush();
    assert.equal(h.meal.value,'Завтрак включён');
    assert.ok(h.meal.children.some(option=>option.value==='Завтрак включён'));
    assert.equal(h.price(),'Уточнить');assert.equal(h.status.hidden,false);
    assert.match(h.status.textContent,/не вернул подтверждённых/);
  });

  await test('запоздавший стартовый снимок не заменяет расчёт на троих',async()=>{
    const h=harness();h.change(h.adults,3);assert.equal(h.initial.signal.aborted,true);h.submit();
    h.requests[0].resolve(h.data(3333));await flush();assert.match(h.price(),/3\s?333/);
    await h.start(h.data(2222));assert.match(h.price(),/3\s?333/);
  });

  await test('отменённый расчёт не заменяет более новый состав гостей',async()=>{
    const h=harness();await h.start();h.change(h.adults,3);h.submit();
    assert.equal(h.requests[0].q.adults,3);h.change(h.adults,1);
    assert.equal(h.requests[0].signal.aborted,true);assert.equal(h.output.children.length,0);
    h.submit();h.requests[1].resolve(h.data(1111));await flush();
    h.requests[0].resolve(h.data(3333));await flush();assert.match(h.price(),/1\s?111/);
    assert.equal(h.button.disabled,false);
  });

  await test('изменение детей убирает старую цену и требует каждого возраста',async()=>{
    const h=harness();await h.start();assert.equal(h.output.children.length,1);
    h.change(h.children,1);assert.equal(h.output.children.length,0);
    const first=h.ages.querySelectorAll('select')[0];assert.equal(first.required,true);assert.equal(first.value,'');
    h.submit();assert.equal(h.requests.length,0);assert.match(h.status.textContent,/возраст/);
    h.change(first,0);h.submit();assert.deepEqual(h.requests[0].q.ages,[0]);
    h.requests[0].resolve(h.data(8500));await flush();assert.match(h.price(),/8\s?500/);
    h.change(h.children,2);assert.equal(h.output.children.length,0);
    const fields=h.ages.querySelectorAll('select');assert.equal(fields[0].value,'0');assert.equal(fields[1].value,'');
  });

  await test('английская сетевая ошибка заменяется русским сообщением',async()=>{
    const h=harness();await h.start();h.change(h.adults,3);h.submit();
    h.requests[0].reject(new TypeError('Failed to fetch'));await flush();
    assert.equal(h.output.children.length,0);assert.match(h.status.textContent,/Не удалось получить расчёт отеля/);
    assert.doesNotMatch(h.status.textContent,/Failed/);
  });

  await test('точное русское ограничение источника остаётся понятным гостю',async()=>{
    const h=harness();await h.start();h.change(h.adults,3);h.submit();
    h.requests[0].reject(new Error('Система Геги не даёт точный расчёт для выбранного возраста ребёнка.'));await flush();
    assert.equal(h.output.children.length,0);assert.match(h.status.textContent,/Система Геги/);
  });

  await test('в открытой вкладке просроченная цена исчезает',async()=>{
    const h=harness();await h.start();assert.equal(h.status.hidden,true);
    h.advance(3*60*60*1000);h.intervals[0]();
    assert.equal(h.output.children.length,0);assert.match(h.status.textContent,/Цены устарели/);
  });

  console.log(`Проверено сценариев клиента: ${passed}`);
})().catch(error=>{console.error(error);process.exitCode=1;});
