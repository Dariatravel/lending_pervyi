const APP_SHELL_CACHE = "abhazbereg-app-shell-v202608111746";
const RUNTIME_CACHE = "abhazbereg-runtime-v202608111746";
const YANDEX_MEDIA_ORIGIN = "https://storage.yandexcloud.net";
const YANDEX_MEDIA_PATH_PREFIX = "/abhazbereg-media/media/";
const MAX_RUNTIME_MEDIA_ENTRIES = 80;

const APP_SHELL_URLS = [
  "/",
  "/styles.min.css?v=202608111746",
  "/scripts.min.js?v=202608111746",
  "/pwa.js?v=202608111746",
  "/vendor/fonts/manrope-cyrillic.woff2",
  "/vendor/fonts/manrope-latin.woff2",
  "/vendor/fonts/prata-cyrillic.woff2",
  "/vendor/fonts/prata-latin.woff2",
  "/vendor/leaflet/leaflet.css?v=202608111746",
  "/vendor/leaflet/leaflet.js?v=202608111746",
  "/vendor/leaflet-markercluster/MarkerCluster.css?v=202608111746",
  "/vendor/leaflet-markercluster/MarkerCluster.Default.css?v=202608111746",
  "/vendor/leaflet-markercluster/leaflet.markercluster.js?v=202608111746",
  "/app.webmanifest",
  "/404.html",
  "/app-icons/icon-192.png",
  "/app-icons/icon-512.png",
  "/app-icons/icon.svg",
  "/karta/",
  "/offline.html",
];

// Что показать, когда до сайта не достучаться и в кэше этой страницы нет:
// голая ошибка браузера выглядит как «сайт не работает», а здесь гость
// видит объяснение и ссылку на Telegram, где его забронируют без сайта.
const OFFLINE_URL = "/offline.html";

// У части российских операторов запрос к GitHub Pages не отклоняется, а зависает:
// соединение открыто, ответа нет, ошибки тоже нет. Обычный fetch будет ждать
// столько, сколько позволит браузер — гость всё это время смотрит на белый экран.
// Поэтому ждём не ответа, а времени: через FAST_MS отдаём кэш, если он есть,
// через HARD_MS — офлайн-страницу. Сам запрос при этом не обрываем: он
// продолжает грузиться и обновляет кэш к следующему заходу.
// HARD отсчитывается уже после FAST, то есть офлайн-страница появится примерно
// на пятнадцатой секунде. Раньше показывать её не стоит: у гостя может быть
// просто медленный мобильный интернет, и страница всё-таки дойдёт.
const FAST_FALLBACK_MS = 5000;
const HARD_FALLBACK_MS = 10000;

function afterDelay(ms, value) {
  return new Promise((resolve) => setTimeout(() => resolve(value), ms));
}

// Пустой или обрезанный ответ иногда приходит с кодом 200 — закэшировать такой
// значит показывать гостю белую страницу и дальше, уже без всякой сети.
async function isUsableHtml(response) {
  try {
    const text = await response.clone().text();
    return text.length > 500 && /<\/html\s*>/i.test(text);
  } catch {
    return false;
  }
}

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(APP_SHELL_CACHE)
      .then((cache) => cache.addAll(APP_SHELL_URLS))
      .catch(() => undefined)
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((key) => ![APP_SHELL_CACHE, RUNTIME_CACHE].includes(key))
            .map((key) => caches.delete(key))
        )
      )
      .then(() => self.clients.claim())
  );
});

function isSameOrigin(requestUrl) {
  return requestUrl.origin === self.location.origin;
}

function isHtmlRequest(request) {
  return request.mode === "navigate" || (request.headers.get("accept") || "").includes("text/html");
}

function isJsonRequest(requestUrl) {
  return requestUrl.pathname.endsWith(".json");
}

function isStaticAsset(requestUrl) {
  return /\.(?:css|js|webmanifest|png|jpg|jpeg|webp|svg|ico|woff2?)$/i.test(requestUrl.pathname);
}

function isYandexMediaRequest(requestUrl) {
  return requestUrl.origin === YANDEX_MEDIA_ORIGIN && requestUrl.pathname.startsWith(YANDEX_MEDIA_PATH_PREFIX);
}

function canCacheResponse(response) {
  return response && (response.ok || response.type === "opaque");
}

async function trimRuntimeCache() {
  const cache = await caches.open(RUNTIME_CACHE);
  const keys = (await cache.keys()).filter((request) => {
    try {
      return isYandexMediaRequest(new URL(request.url));
    } catch {
      return false;
    }
  });
  if (keys.length <= MAX_RUNTIME_MEDIA_ENTRIES) return;

  await Promise.all(keys.slice(0, keys.length - MAX_RUNTIME_MEDIA_ENTRIES).map((request) => cache.delete(request)));
}

async function networkFirst(request) {
  const cache = await caches.open(RUNTIME_CACHE);
  const html = isHtmlRequest(request);

  // Запрос живёт своей жизнью: даже если мы ответим гостю из кэша по таймеру,
  // он дойдёт до конца и положит свежую версию на следующий раз.
  // Ответ отдаём сразу, не дожидаясь полного тела: проверка на пустой HTML идёт
  // по отдельной копии и гостя не задерживает.
  const network = fetch(request)
    .then((response) => {
      if (canCacheResponse(response)) {
        const forCheck = response.clone();
        const forCache = response.clone();
        (html ? isUsableHtml(forCheck) : Promise.resolve(true))
          .then((usable) => (usable ? cache.put(request, forCache) : undefined))
          .catch(() => undefined);
      }
      return response;
    })
    .catch(() => undefined);

  const fast = await Promise.race([network, afterDelay(FAST_FALLBACK_MS)]);
  if (fast) return fast;

  // Сеть молчит дольше пяти секунд. Кэш этой страницы лучше белого экрана.
  const cached = await cache.match(request);
  if (cached) return cached;

  const slow = await Promise.race([network, afterDelay(HARD_FALLBACK_MS)]);
  if (slow) return slow;

  if (html) {
    const offline = await caches.match(OFFLINE_URL);
    if (offline) return offline;
  }
  // Ответа так и нет — отдаём то, чем закончится сеть, включая её ошибку.
  return network.then((response) => response || Response.error());
}

async function cacheFirst(request, cacheName = APP_SHELL_CACHE) {
  const cached = await caches.match(request);
  if (cached) return cached;

  const response = await fetch(request);
  if (canCacheResponse(response)) {
    const cache = await caches.open(cacheName);
    cache.put(request, response.clone()).catch(() => undefined);
  }
  return response;
}

async function mediaCacheFirst(request) {
  const response = await cacheFirst(request, RUNTIME_CACHE);
  trimRuntimeCache().catch(() => undefined);
  return response;
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;

  const requestUrl = new URL(request.url);
  if (isYandexMediaRequest(requestUrl)) {
    event.respondWith(mediaCacheFirst(request));
    return;
  }

  if (!isSameOrigin(requestUrl)) return;

  if (isHtmlRequest(request) || isJsonRequest(requestUrl)) {
    event.respondWith(networkFirst(request));
    return;
  }

  if (isStaticAsset(requestUrl)) {
    event.respondWith(cacheFirst(request));
  }
});
