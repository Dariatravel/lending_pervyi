const { readFileSync } = require('node:fs');
const { createServer } = require('node:http');
const { join } = require('node:path');

const canonical = 'https://xn--80aacbklan7f0b.xn--p1ai';
const data = join(__dirname, '../../data');
const readJson = (name) => JSON.parse(readFileSync(join(data, name), 'utf8'));
const routes = new Map();

function addRoute(from, target) {
  if (!from.startsWith('/') || !/^\/(?![\/\\])/.test(target) || /[\\\s]/.test(target)) {
    throw new Error('Некорректное соответствие маршрута: ' + from);
  }
  routes.set(from, target);
}

for (const [source, value] of Object.entries(readJson('old-site-redirects.json').redirects)) {
  addRoute(source, typeof value === 'string' ? value : value.to);
}
for (const [source, target] of Object.entries(readJson('retired-redirects.json').redirects)) {
  addRoute('/' + source.replace(/^\//, '').replace(/\/$/, '') + '/', target);
}
// Ручные короткие ссылки имеют приоритет над автоматически собранными.
for (const name of ['short-links-generated.json', 'short-links.json']) {
  for (const [key, target] of Object.entries(readJson(name).links)) {
    addRoute('/' + key, target);
    addRoute('/' + key + '/', target);
    addRoute('/' + key + '/index.html', target);
  }
}

const callbackPage = readFileSync(join(__dirname, 'vk-return.html'));

function responseFor(raw, mirror) {
  if (!raw.startsWith('/') || /[^\x21-\x7e]|#/.test(raw)) {
    return { status: 400, headers: { 'Cache-Control': 'no-store' } };
  }
  const separator = raw.indexOf('?');
  const pathname = separator === -1 ? raw : raw.slice(0, separator);
  const query = separator === -1 ? '' : raw.slice(separator + 1);
  const params = new URLSearchParams(query);
  if (mirror === 'ru' && ['/', '/index.html'].includes(pathname)
      && params.has('state') && (params.has('code') || params.has('error'))) {
    return {
      status: 200,
      headers: {
        'Content-Type': 'text/html; charset=utf-8',
        'Cache-Control': 'private, no-store',
        'Referrer-Policy': 'no-referrer',
      },
      body: callbackPage,
    };
  }
  let target = routes.get(pathname);
  if (!target && pathname.endsWith('/index.html')) {
    target = routes.get(pathname.slice(0, -'index.html'.length));
  }
  if (!target && pathname.endsWith('/')) target = routes.get(pathname.slice(0, -1));
  if (!target) target = routes.get(pathname + '/');
  const [destination, fragment] = (target || pathname).split('#', 2);
  const suffix = separator === -1 ? '' : (destination.includes('?') ? '&' : '?') + query;
  return {
    status: 301,
    headers: {
      Location: canonical + destination + suffix + (fragment ? '#' + fragment : ''),
      'Cache-Control': 'no-store',
    },
  };
}

if (require.main === module) {
  createServer((request, response) => {
    const result = responseFor(request.url, request.headers['x-abhazbereg-mirror']);
    response.writeHead(result.status, {
      ...result.headers,
      'Content-Length': result.body?.length ?? 0,
    });
    response.end(request.method === 'HEAD' ? undefined : result.body);
  }).listen(Number(process.env.PORT || 8080), '0.0.0.0');
}

module.exports = { responseFor };
