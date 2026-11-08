const assert = require('node:assert/strict');
const test = require('node:test');
const { responseFor } = require('./server.cjs');

const canonical = 'https://xn--80aacbklan7f0b.xn--p1ai';
const query = '?utm_source=mirror&a=1&a=2&x=%2B&empty=';
const pairs = [
  ['/tpost/kurort', '/blog/kak-vybrat-kurort-abkhaziya-pervyy-raz/'],
  ['/catalog/tproduct/104733537912-letnyaya-kvartira-3k', '/kvartira/letnyaya-kvartira-3k-suhum-1377/'],
  ['/answers/gagra-staraya-ili-novaya/', '/answers/gagra-staraya-ili-novaya/'],
  ['/pamyatka', '/blog/pamyatka-turistu-abkhazia/'],
  ['/pamyatka/', '/blog/pamyatka-turistu-abkhazia/'],
  ['/pamyatka/index.html', '/blog/pamyatka-turistu-abkhazia/'],
  ['/', '/'],
];

for (const mirror of ['ru', 'com']) {
  for (const [source, destination] of pairs) {
    test(mirror + ' ' + source, () => {
      const result = responseFor(source + query, mirror);
      assert.equal(result.status, 301);
      assert.equal(result.headers.Location, canonical + destination + query);
    });
  }
}

test('Возврат VK ID остаётся на .ru, ответ не кэшируется', () => {
  for (const params of ['code=test&state=test', 'error=access_denied&state=test']) {
    const result = responseFor('/?' + params, 'ru');
    assert.equal(result.status, 200);
    assert.equal(result.headers.Location, undefined);
    assert.equal(result.headers['Cache-Control'], 'private, no-store');
    assert.match(result.body.toString(), /id="vk-url"/);
    assert.equal(responseFor('/?' + params, 'com').status, 301);
  }
});

test('Фрагмент назначения следует после сохранённых параметров', () => {
  for (const suffix of ['', 'index.html']) {
    const result = responseFor('/hotels/bugenvilleya-otel-s-basseynom-3044/' + suffix + query, 'ru');
    assert.equal(result.headers.Location, canonical + '/' + query + '#catalog');
  }
});

test('Пустая строка запроса сохраняется', () => {
  assert.equal(responseFor('/?', 'ru').headers.Location, canonical + '/?');
});
