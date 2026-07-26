const APP_SHELL_CACHE = "abhazbereg-app-shell-v202607261908";
const RUNTIME_CACHE = "abhazbereg-runtime-v202607261908";
const YANDEX_MEDIA_ORIGIN = "https://storage.yandexcloud.net";
const YANDEX_MEDIA_PATH_PREFIX = "/abhazbereg-media/media/";
const MAX_RUNTIME_MEDIA_ENTRIES = 80;

const APP_SHELL_URLS = [
  "/",
  "/styles.min.css?v=202607261908",
  "/scripts.min.js?v=202607261908",
  "/pwa.js?v=202607261908",
  "/vendor/fonts/manrope-cyrillic.woff2",
  "/vendor/fonts/manrope-latin.woff2",
  "/vendor/fonts/prata-cyrillic.woff2",
  "/vendor/fonts/prata-latin.woff2",
  "/vendor/leaflet/leaflet.css?v=202607261908",
  "/vendor/leaflet/leaflet.js?v=202607261908",
  "/vendor/leaflet-markercluster/MarkerCluster.css?v=202607261908",
  "/vendor/leaflet-markercluster/MarkerCluster.Default.css?v=202607261908",
  "/vendor/leaflet-markercluster/leaflet.markercluster.js?v=202607261908",
  "/app.webmanifest",
  "/404.html",
  "/app-icons/icon-192.png",
  "/app-icons/icon-512.png",
  "/app-icons/icon.svg",
  "/karta/",
];

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
  try {
    const response = await fetch(request);
    if (canCacheResponse(response)) {
      cache.put(request, response.clone()).catch(() => undefined);
    }
    return response;
  } catch (error) {
    const cached = await cache.match(request);
    if (cached) return cached;
    throw error;
  }
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
