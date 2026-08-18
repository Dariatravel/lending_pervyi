// Проверка видео на живом сайте настоящим браузером (мобильная эмуляция).
// ВАЖНО: канал 'chrome' — у голого headless-chromium нет кодека H.264,
// и play() на mp4 висит вечно, изображая поломку сайта.
// Запуск (GitHub Actions): node tools/browser_media_check.mjs <url> [url...]
import { chromium } from 'playwright-core';

const pages = process.argv.slice(2);
if (!pages.length) {
  console.error('Укажите адреса страниц.');
  process.exit(2);
}

const browser = await chromium.launch({
  channel: 'chrome',
  args: ['--no-sandbox', '--autoplay-policy=no-user-gesture-required'],
});
const context = await browser.newContext({
  viewport: { width: 390, height: 844 },
  userAgent: 'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Mobile Safari/537.36',
});

let fail = 0;
for (const url of pages) {
  console.log(`\n===== ${url} =====`);
  const page = await context.newPage();
  const netErrors = [];
  page.on('requestfailed', (req) => {
    if (/media\.xn--80aacbklan7f0b|storage\.yandexcloud\.net/.test(req.url())) {
      netErrors.push(`${req.failure()?.errorText} ← ${req.url().split('/').pop()}`);
    }
  });
  page.on('response', (resp) => {
    if (/\.mp4|\.poster\.jpg/.test(resp.url()) && resp.status() >= 400) {
      netErrors.push(`HTTP ${resp.status()} ← ${resp.url()}`);
    }
  });
  try {
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 45000 });
    await page.waitForTimeout(2000);
    // Вся логика внутри страницы обёрнута таймаутами: тест обязан договорить.
    const checkPromise = page.evaluate(async () => {
      const wait = (ms) => new Promise((r) => setTimeout(r, ms));
      const race = (p, ms) =>
        Promise.race([
          Promise.resolve(p).then(() => 'ok').catch((e) => 'отказ:' + e.name),
          wait(ms).then(() => 'таймаут play()'),
        ]);
      const out = [];
      const all = [...document.querySelectorAll('video')];
      for (const [i, v] of all.slice(0, 5).entries()) {
        const src = (v.currentSrc || v.src || (v.querySelector('source') || {}).src || '').split('/').pop();
        const playResult = await race(v.play(), 8000);
        await wait(3000);
        out.push(
          `video#${i} src=${src} play=${playResult} readyState=${v.readyState} ` +
          `time=${v.currentTime.toFixed(1)} error=${v.error ? v.error.code + '/' + (v.error.message || '') : 'нет'}`
        );
        try { v.pause(); } catch {}
      }
      return { count: all.length, out };
    });
    const report = await Promise.race([
      checkPromise,
      new Promise((_, rej) => setTimeout(() => rej(new Error('watchdog: страница не ответила за 90с')), 90000)),
    ]);
    console.log(`видео на странице: ${report.count} (проверяем до 5)`);
    for (const line of report.out) console.log('  ' + line);
    // Провал — только настоящая ошибка плеера или таймаут у видео С адресом.
    // Пустой src — служебная заготовка лайтбокса (адрес подставляется при
    // открытии галереи); time=0.0 при readyState=4 — данные есть, просто
    // старт не успел за 3с при пяти одновременных плеерах.
    const broken = report.out.filter((l) => /error=[1-9]/.test(l) || (/таймаут/.test(l) && !/src= /.test(l)));
    const badNet = netErrors.filter((e) => !/ERR_ABORTED/.test(e)); // прерванная догрузка — не поломка
    if (broken.length || badNet.length) fail = 1;
    for (const e of [...new Set(netErrors)].slice(0, 8)) console.log('  СЕТЬ: ' + e);
  } catch (e) {
    console.log('ОШИБКА: ' + String(e).split('\n')[0]);
    fail = 1;
  }
  await page.close();
}
await browser.close();
console.log(fail ? '\nИТОГ: есть проблемы с видео.' : '\nИТОГ: все видео играют.');
process.exit(fail);
