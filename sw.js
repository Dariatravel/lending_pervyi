const APP_SHELL_CACHE = "abhazbereg-app-shell-v202607081500";
const RUNTIME_CACHE = "abhazbereg-runtime-v202607081500";

const APP_SHELL_URLS = [
  "/",
  "/styles.css?v=202607081500",
  "/image-lite.js?v=202607081500",
  "/scripts.js?v=202607081500",
  "/pwa.js?v=202606301525",
  "/app.webmanifest",
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
  return /\.(?:css|js|webmanifest|png|jpg|jpeg|webp|svg|ico)$/i.test(requestUrl.pathname);
}

async function networkFirst(request) {
  const cache = await caches.open(RUNTIME_CACHE);
  try {
    const response = await fetch(request);
    if (response && response.ok) {
      cache.put(request, response.clone()).catch(() => undefined);
    }
    return response;
  } catch (error) {
    const cached = await cache.match(request);
    if (cached) return cached;
    throw error;
  }
}

async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) return cached;

  const response = await fetch(request);
  if (response && response.ok) {
    const cache = await caches.open(APP_SHELL_CACHE);
    cache.put(request, response.clone()).catch(() => undefined);
  }
  return response;
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;

  const requestUrl = new URL(request.url);
  if (!isSameOrigin(requestUrl)) return;

  if (isHtmlRequest(request) || isJsonRequest(requestUrl)) {
    event.respondWith(networkFirst(request));
    return;
  }

  if (isStaticAsset(requestUrl)) {
    event.respondWith(cacheFirst(request));
  }
});
