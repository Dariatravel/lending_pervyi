// Проверка видео на живом сайте настоящим браузером (мобильная эмуляция).
// Открывает страницы, жмёт play на каждом <video> и сообщает readyState /
// код ошибки плеера + все сбои сетевых запросов к медиа-хостам.
// Запуск (GitHub Actions): node tools/browser_media_check.mjs <url> [url...]
import { chromium } from 'playwright';

const pages = process.argv.slice(2);
if (!pages.length) {
  console.error('Укажите адреса страниц.');
  process.exit(2);
}

const browser = await chromium.launch({ args: ['--no-sandbox', '--autoplay-policy=no-user-gesture-required'] });
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
    const report = await page.evaluate(async () => {
      const out = [];
      const videos = [...document.querySelectorAll('video')];
      for (const [i, v] of videos.entries()) {
        const src = (v.currentSrc || v.src || (v.querySelector('source') || {}).src || '').split('/').pop();
        try { await v.play(); } catch (e) { out.push(`video#${i} play() отказ: ${e.name}`); }
        await new Promise((r) => setTimeout(r, 4000));
        out.push(`video#${i} src=${src} readyState=${v.readyState} paused=${v.paused} ` +
          `time=${v.currentTime.toFixed(1)} error=${v.error ? v.error.code + '/' + (v.error.message || '') : 'нет'}`);
        v.pause();
      }
      return { count: videos.length, out };
    });
    console.log(`видео на странице: ${report.count}`);
    for (const line of report.out) console.log('  ' + line);
    const broken = report.out.filter((l) => /error=[1-9]|readyState=0/.test(l));
    if (broken.length || netErrors.length) fail = 1;
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
